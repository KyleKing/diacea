"""Mermaid parser - converts Mermaid flowchart/graph and sequence text to IR.

Supports a deliberate subset of Mermaid: flowchart/graph and sequence
diagrams. Other Mermaid diagram types (C4Context, classDiagram, ...) are
rejected with a ValueError. Styling directives (classDef, style, click,
linkStyle) and unrecognized lines are skipped with a warning instead of
failing. Sequence control blocks (loop, alt, par, ...) and notes are
skipped with warnings while the messages inside them are still parsed.

Since Mermaid text has no coordinates, a simple layered layout is
synthesized (topological layers along the declared direction) and flagged
via ``diagram.metadata["synthesized_layout"]``.
"""

from __future__ import annotations

import re
from collections import defaultdict, deque
from typing import Any, Optional

from ..ir import (
    GROUP_ID_PREFIX,
    Connection,
    Diagram,
    Dimensions,
    Group,
    Parser,
    Point,
    Shape,
    Style,
)
from ..ir.semantic import SemanticType, infer_semantic_type

_HEADER_RE = re.compile(r"^(?:flowchart|graph)\b\s*(LR|RL|TD|TB|BT)?\s*;?\s*$", re.IGNORECASE)

_SEQUENCE_HEADER_RE = re.compile(r"^sequenceDiagram\s*;?\s*$")

_FRONTMATTER_TITLE_RE = re.compile(r"^title:\s*(.+?)\s*$")

_OTHER_DIAGRAM_KEYWORDS = (
    "C4Component",
    "C4Container",
    "C4Context",
    "C4Deployment",
    "C4Dynamic",
    "block-beta",
    "classDiagram",
    "erDiagram",
    "gantt",
    "gitGraph",
    "journey",
    "mindmap",
    "packet-beta",
    "pie",
    "quadrantChart",
    "requirementDiagram",
    "sankey-beta",
    "stateDiagram",
    "stateDiagram-v2",
    "timeline",
    "xychart-beta",
    "zenuml",
)

_SKIPPED_DIRECTIVES = ("class", "classDef", "click", "direction", "linkStyle", "style")

_SEQUENCE_BLOCK_KEYWORDS = (
    "alt",
    "and",
    "box",
    "break",
    "critical",
    "else",
    "end",
    "loop",
    "opt",
    "option",
    "par",
    "rect",
)

_SEQUENCE_SKIPPED_DIRECTIVES = (
    "activate",
    "autonumber",
    "deactivate",
    "link",
    "links",
    "note",
    "properties",
)

_SEQ_PARTICIPANT_RE = re.compile(r"^(participant|actor)\s+([\w.-]+)(?:\s+as\s+(.+))?$")

_SEQ_MESSAGE_RE = re.compile(
    r"^([\w.]+)\s*(<<-->>|<<->>|-->>|->>|--[>x)]|-[>x)])\s*([+-]?)\s*([\w.]+)\s*(?::\s*(.*))?$"
)

_LINK_RE = re.compile(
    r"\s*(<?(?:={2,}|-{2,}|-\.+-*)[>xo]?)"
    r"(?:\|([^|]*)\|)?\s*"
)

_TEXT_ARROW_SUBS = (
    (re.compile(r"--\s*([^-|>][^|]*?)\s*-->"), r"-->|\1|"),
    (re.compile(r"--\s*([^-|>][^|]*?)\s*---"), r"---|\1|"),
    (re.compile(r"-\.\s*([^-|.>][^|]*?)\s*\.->"), r"-.->|\1|"),
    (re.compile(r"==\s*([^=|>][^|]*?)\s*==>"), r"==>|\1|"),
)

_NODE_TOKEN_RE = re.compile(r"^([A-Za-z0-9_.:-]+)\s*(.*)$", re.DOTALL)

_CLASS_SUFFIX_RE = re.compile(r":::[\w-]+$")

_FA_ICON_RE = re.compile(r"fa[brs]?:fa-([A-Za-z0-9-]+)\s*")

_FA_ICON_SEMANTICS: dict[str, SemanticType] = {
    "cloud": SemanticType.CLOUD,
    "cog": SemanticType.SERVICE,
    "cogs": SemanticType.SERVICE,
    "database": SemanticType.DATABASE,
    "envelope": SemanticType.QUEUE,
    "gear": SemanticType.SERVICE,
    "gears": SemanticType.SERVICE,
    "globe": SemanticType.EXTERNAL,
    "person": SemanticType.PERSON,
    "server": SemanticType.SERVER,
    "user": SemanticType.PERSON,
    "users": SemanticType.PERSON,
}

_SUBGRAPH_TITLED_RE = re.compile(r"^([A-Za-z0-9_.-]+)\s*\[(.*)\]$")

_BRACKET_SHAPES = (
    ("([", "])", "stadium"),
    ("[(", ")]", "cylinder"),
    ("((", "))", "circle"),
    ("{{", "}}", "hexagon"),
    ("[/", "/]", "parallelogram"),
    ("[", "]", "rectangle"),
    ("(", ")", "rounded_rectangle"),
    ("{", "}", "diamond"),
)

_NODE_WIDTH_MIN = 120.0
_NODE_HEIGHT_BASE = 60.0
_LAYER_PITCH = 240.0
_CROSS_PITCH = 140.0
_GROUP_PADDING = 20.0


def is_mermaid(content: str) -> bool:
    """Cheap sniff: does the first meaningful line start a Mermaid diagram?"""
    first = _first_meaningful_line(content)
    if first is None:
        return False
    if _HEADER_RE.match(first) or _SEQUENCE_HEADER_RE.match(first):
        return True
    keyword = first.split()[0].rstrip(":;")
    return keyword in _OTHER_DIAGRAM_KEYWORDS


def is_mermaid_flowchart(content: str) -> bool:
    """Whether the content is a Mermaid flowchart/graph diagram."""
    first = _first_meaningful_line(content)
    return first is not None and _HEADER_RE.match(first) is not None


def is_mermaid_sequence(content: str) -> bool:
    """Whether the content is a Mermaid sequence diagram."""
    first = _first_meaningful_line(content)
    return first is not None and _SEQUENCE_HEADER_RE.match(first) is not None


def _split_frontmatter(content: str) -> tuple[str, Optional[str]]:
    lines = content.split("\n")
    start = next((i for i, line in enumerate(lines) if line.strip()), None)
    if start is None or lines[start].strip() != "---":
        return (content, None)
    title = None
    for end in range(start + 1, len(lines)):
        stripped = lines[end].strip()
        if stripped == "---":
            for index in range(start, end + 1):
                lines[index] = ""
            return ("\n".join(lines), title)
        if match := _FRONTMATTER_TITLE_RE.match(stripped):
            title = match.group(1).strip("\"'")
    return (content, None)


def _first_meaningful_line(content: str) -> Optional[str]:
    if not isinstance(content, str):
        return None
    content, _ = _split_frontmatter(content)
    for raw in content.splitlines():
        line = raw.strip()
        if not line or line.startswith("%%") or line.startswith("```"):
            continue
        return line
    return None


def _unescape_label(label: str) -> str:
    text = label.strip()
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        text = text[1:-1]
    text = text.replace("<br/>", "\n").replace("<br>", "\n")
    text = text.replace("#quot;", '"')
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&#124;", "|")
    text = text.replace("&amp;", "&")
    return text


def _extract_fa_icons(label: str) -> tuple[str, list[str]]:
    icons = _FA_ICON_RE.findall(label)
    if not icons:
        return (label, [])
    cleaned = _FA_ICON_RE.sub("", label)
    return (re.sub(r"[ \t]{2,}", " ", cleaned).strip(), icons)


def _icon_metadata(icons: list[str]) -> dict[str, Any]:
    metadata: dict[str, Any] = {"mermaid": {"icons": icons}}
    for icon in icons:
        if (semantic := _FA_ICON_SEMANTICS.get(icon)) is not None:
            metadata["semantic_type"] = semantic.value
            break
    return metadata


def _split_arrow_attrs(arrow: str) -> tuple[str, str, Optional[float]]:
    has_head = arrow[-1] in ">xo"
    if arrow.startswith("<") and has_head:
        connection_type = "bidirectional"
    elif has_head:
        connection_type = "directed"
    else:
        connection_type = "undirected"
    stroke_style = "dashed" if "." in arrow else "solid"
    stroke_width = 3.0 if "=" in arrow else None
    return (connection_type, stroke_style, stroke_width)


def _split_on_ampersand(segment: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    in_quote = False
    current: list[str] = []
    for char in segment:
        if char == '"':
            in_quote = not in_quote
        elif char in "[({" and not in_quote:
            depth += 1
        elif char in "])}" and not in_quote:
            depth -= 1
        if char == "&" and depth == 0 and not in_quote:
            parts.append("".join(current))
            current = []
        else:
            current.append(char)
    parts.append("".join(current))
    return [part.strip() for part in parts if part.strip()]


class MermaidParser(Parser):
    """Parse Mermaid flowchart/graph text into the IR."""

    def __init__(self):
        self.warnings: list[str] = []

    def parse(self, data: Any) -> Diagram:
        """Parse Mermaid flowchart or sequence text to an IR Diagram."""
        if not isinstance(data, str):
            raise ValueError("Mermaid parser expects a string input")

        self.warnings = []
        data, title = _split_frontmatter(data)
        if is_mermaid_sequence(data):
            return self._parse_sequence(data, title)
        self._shapes: dict[str, Shape] = {}
        self._shape_order: list[Shape] = []
        self._connections: list[Connection] = []
        self._groups: list[Group] = []
        self._group_stack: list[Group] = []
        self._direction = "TD"

        statements = self._collect_statements(data)
        for line_number, statement in statements:
            self._parse_statement(statement, line_number)

        if self._group_stack:
            self.warnings.append(
                f"unclosed subgraph '{self._group_stack[-1].id}': missing 'end'"
            )
            self._group_stack = []

        for shape in self._shape_order:
            shape.semantic_type, shape.semantic_confidence = infer_semantic_type(
                shape_type=shape.shape_type,
                label=shape.label,
                size=None,
                style=shape.style,
                metadata=shape.metadata,
            )

        self._synthesize_layout()

        diagram = Diagram(
            id="mermaid-flowchart",
            name=title,
            metadata={
                "mermaid": {"direction": self._direction},
                "synthesized_layout": True,
            },
        )
        for shape in self._shape_order:
            diagram.add_element(shape)
        for connection in self._connections:
            diagram.add_element(connection)
        for group in self._groups:
            diagram.add_element(group)
        return diagram

    def _collect_statements(self, data: str) -> list[tuple[int, str]]:
        header_seen = False
        statements: list[tuple[int, str]] = []
        for line_number, raw in enumerate(data.splitlines(), start=1):
            line = raw.strip()
            if not line or line.startswith("```"):
                continue
            if line.startswith("%%"):
                self.warnings.append(f"line {line_number}: skipped comment")
                continue
            if not header_seen:
                parts = line.split(";")
                self._parse_header(parts[0].strip(), line_number)
                header_seen = True
                for part in parts[1:]:
                    if part.strip():
                        statements.append((line_number, part.strip()))
                continue
            statements.append((line_number, line.rstrip(";").strip()))
        if not header_seen:
            raise ValueError("Empty input: no Mermaid diagram found")
        return statements

    def _parse_header(self, line: str, line_number: int) -> None:
        if match := _HEADER_RE.match(line.split(";")[0].strip()):
            self._direction = (match.group(1) or "TD").upper()
            return
        keyword = line.split()[0].rstrip(":;")
        if keyword in _OTHER_DIAGRAM_KEYWORDS:
            raise ValueError(
                f"Unsupported Mermaid diagram type '{keyword}': "
                "only flowchart/graph and sequence diagrams are supported"
            )
        raise ValueError(
            f"line {line_number}: not a Mermaid flowchart (expected 'flowchart' or 'graph' header)"
        )

    def _parse_sequence(self, data: str, title: Optional[str]) -> Diagram:
        self._shapes = {}
        self._shape_order = []
        self._connections = []
        self._groups = []
        self._group_stack = []
        self._sequence_title: Optional[str] = None

        header_seen = False
        for line_number, raw in enumerate(data.splitlines(), start=1):
            line = raw.strip()
            if not line or line.startswith("```"):
                continue
            if line.startswith("%%"):
                self.warnings.append(f"line {line_number}: skipped comment")
                continue
            if not header_seen:
                header_seen = True
                continue
            self._parse_sequence_statement(line.rstrip(";").strip(), line_number)

        for shape in self._shape_order:
            shape.semantic_type, shape.semantic_confidence = infer_semantic_type(
                shape_type=shape.shape_type,
                label=shape.label,
                size=None,
                style=shape.style,
                metadata=shape.metadata,
            )

        self._layout_sequence()

        diagram = Diagram(
            id="mermaid-sequence",
            name=title or self._sequence_title,
            metadata={
                "mermaid": {"diagram_type": "sequence"},
                "synthesized_layout": True,
            },
        )
        for shape in self._shape_order:
            diagram.add_element(shape)
        for connection in self._connections:
            diagram.add_element(connection)
        return diagram

    def _parse_sequence_statement(self, statement: str, line_number: int) -> None:
        if not statement:
            return
        if match := _SEQ_PARTICIPANT_RE.match(statement):
            kind, participant_id, label = match.groups()
            self._declare_participant(
                participant_id,
                label=_unescape_label(label) if label else None,
                is_actor=kind == "actor",
            )
            return
        if match := _SEQ_MESSAGE_RE.match(statement):
            from_id, arrow, _activation, to_id, label = match.groups()
            self._declare_participant(from_id)
            self._declare_participant(to_id)
            connection_type = "bidirectional" if arrow.startswith("<<") else "directed"
            stroke_style = "dashed" if "--" in arrow else "solid"
            self._connections.append(
                Connection(
                    id=f"message-{len(self._connections)}",
                    position=Point(0.0, 0.0),
                    size=Dimensions(1.0, 1.0),
                    from_id=from_id,
                    to_id=to_id,
                    label=_unescape_label(label) if label else "",
                    connection_type=connection_type,
                    style=Style(stroke_style=stroke_style),
                    metadata={"mermaid": {"arrow": arrow}},
                )
            )
            return

        keyword = statement.split(maxsplit=1)[0].rstrip(":").lower()
        if keyword == "title":
            self._sequence_title = statement.split(maxsplit=1)[1].strip() if " " in statement else None
            return
        if keyword in _SEQUENCE_BLOCK_KEYWORDS or keyword in _SEQUENCE_SKIPPED_DIRECTIVES:
            self.warnings.append(f"line {line_number}: skipped '{keyword}' sequence directive")
            return
        self.warnings.append(f"line {line_number}: unrecognized line skipped: {statement!r}")

    def _declare_participant(
        self,
        participant_id: str,
        label: Optional[str] = None,
        is_actor: bool = False,
    ) -> None:
        if (shape := self._shapes.get(participant_id)) is not None:
            if label is not None:
                shape.label = label
            if is_actor:
                shape.metadata["semantic_type"] = SemanticType.PERSON.value
            return
        metadata = {"semantic_type": SemanticType.PERSON.value} if is_actor else None
        self._create_shape(
            participant_id,
            label=label or participant_id,
            shape_type="rectangle",
            metadata=metadata,
        )

    def _layout_sequence(self) -> None:
        for index, shape in enumerate(self._shape_order):
            shape.position = Point(index * _LAYER_PITCH, 0.0)

        for order, connection in enumerate(self._connections):
            source = self._shapes.get(connection.from_id)
            target = self._shapes.get(connection.to_id)
            if not source or not target:
                continue
            message_y = _NODE_HEIGHT_BASE + (order + 1) * 40.0
            start = Point(source.position.x + source.size.width / 2, message_y)
            end = Point(target.position.x + target.size.width / 2, message_y)
            connection.start_point = start
            connection.end_point = end
            connection.position = Point(min(start.x, end.x), min(start.y, end.y))
            connection.size = Dimensions(max(abs(end.x - start.x), 1.0), 1.0)

    def _parse_statement(self, statement: str, line_number: int) -> None:
        if not statement:
            return
        keyword = statement.split(maxsplit=1)[0]

        if keyword == "end" and statement == "end":
            if self._group_stack:
                self._group_stack.pop()
            else:
                self.warnings.append(f"line {line_number}: 'end' without matching subgraph")
            return
        if keyword == "subgraph":
            self._parse_subgraph(statement, line_number)
            return
        if keyword in _SKIPPED_DIRECTIVES:
            self.warnings.append(f"line {line_number}: skipped '{keyword}' directive")
            return

        if self._parse_node_or_edges(statement, line_number):
            return
        self.warnings.append(f"line {line_number}: unrecognized line skipped: {statement!r}")

    def _parse_subgraph(self, statement: str, line_number: int) -> None:
        rest = statement[len("subgraph"):].strip()
        if not rest:
            self.warnings.append(f"line {line_number}: subgraph without an id skipped")
            return
        if match := _SUBGRAPH_TITLED_RE.match(rest):
            group_id, label = match.group(1), _unescape_label(match.group(2))
        else:
            label = _unescape_label(rest)
            group_id = re.sub(r"\W", "_", label)
        group_id = GROUP_ID_PREFIX + re.sub(r"^group[-_]", "", group_id)
        group = Group(
            id=group_id,
            position=Point(0.0, 0.0),
            size=Dimensions(1.0, 1.0),
            label=label,
        )
        if self._group_stack:
            self._group_stack[-1].children.append(group.id)
        self._groups.append(group)
        self._group_stack.append(group)

    def _parse_node_or_edges(self, statement: str, line_number: int) -> bool:
        normalized = statement
        for pattern, replacement in _TEXT_ARROW_SUBS:
            normalized = pattern.sub(replacement, normalized)

        parts = _LINK_RE.split(normalized)
        segments = parts[0::3]
        arrows = parts[1::3]
        labels = parts[2::3]

        if any(not segment.strip() for segment in segments):
            return False

        resolved: list[list[str]] = []
        for segment in segments:
            node_ids: list[str] = []
            for token in _split_on_ampersand(segment):
                node_id = self._declare_node(token, line_number)
                if node_id is None:
                    return False
                node_ids.append(node_id)
            if not node_ids:
                return False
            resolved.append(node_ids)

        for index, (arrow, label) in enumerate(zip(arrows, labels)):
            connection_type, stroke_style, stroke_width = _split_arrow_attrs(arrow)
            for from_id in resolved[index]:
                for to_id in resolved[index + 1]:
                    self._connections.append(
                        Connection(
                            id=f"edge-{len(self._connections)}",
                            position=Point(0.0, 0.0),
                            size=Dimensions(1.0, 1.0),
                            from_id=from_id,
                            to_id=to_id,
                            label=_unescape_label(label) if label else "",
                            connection_type=connection_type,
                            style=Style(stroke_style=stroke_style, stroke_width=stroke_width),
                            metadata={"mermaid": {"arrow": arrow}},
                        )
                    )
        return True

    def _declare_node(self, token: str, line_number: int) -> Optional[str]:
        match = _NODE_TOKEN_RE.match(_CLASS_SUFFIX_RE.sub("", token.strip()))
        if not match:
            return None
        node_id, body = match.group(1), match.group(2).strip()

        if not body:
            if node_id not in self._shapes:
                self._create_shape(node_id, label=node_id, shape_type="rectangle")
            else:
                self._adopt_into_group(node_id)
            return node_id

        for opening, closing, shape_type in _BRACKET_SHAPES:
            if body.startswith(opening) and body.endswith(closing):
                label = _unescape_label(body[len(opening):-len(closing)])
                label, icons = _extract_fa_icons(label)
                if node_id in self._shapes:
                    shape = self._shapes[node_id]
                    shape.label = label
                    shape.shape_type = shape_type
                    if icons:
                        shape.metadata.update(_icon_metadata(icons))
                    self._adopt_into_group(node_id)
                else:
                    self._create_shape(
                        node_id,
                        label=label,
                        shape_type=shape_type,
                        metadata=_icon_metadata(icons) if icons else None,
                    )
                return node_id

        self.warnings.append(
            f"line {line_number}: unsupported node syntax skipped: {token.strip()!r}"
        )
        return None

    def _create_shape(
        self,
        node_id: str,
        label: str,
        shape_type: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        label_lines = label.splitlines() or [""]
        width = max(_NODE_WIDTH_MIN, 12.0 * max(len(line) for line in label_lines) + 40.0)
        height = _NODE_HEIGHT_BASE + 30.0 * (len(label_lines) - 1)
        shape = Shape(
            id=node_id,
            position=Point(0.0, 0.0),
            size=Dimensions(width, height),
            label=label,
            shape_type=shape_type,
            metadata=metadata or {},
        )
        self._shapes[node_id] = shape
        self._shape_order.append(shape)
        if self._group_stack:
            self._group_stack[-1].children.append(node_id)

    def _adopt_into_group(self, node_id: str) -> None:
        if not self._group_stack:
            return
        if any(node_id in group.children for group in self._groups):
            return
        self._group_stack[-1].children.append(node_id)

    def _synthesize_layout(self) -> None:
        layers = self._assign_layers()
        max_layer = max(layers.values(), default=0)
        cross_counters: dict[int, int] = defaultdict(int)

        for shape in self._shape_order:
            layer = layers[shape.id]
            cross = cross_counters[layer]
            cross_counters[layer] += 1
            match self._direction:
                case "LR":
                    shape.position = Point(layer * _LAYER_PITCH, cross * _CROSS_PITCH)
                case "RL":
                    shape.position = Point((max_layer - layer) * _LAYER_PITCH, cross * _CROSS_PITCH)
                case "BT":
                    shape.position = Point(cross * _LAYER_PITCH, (max_layer - layer) * _CROSS_PITCH)
                case _:
                    shape.position = Point(cross * _LAYER_PITCH, layer * _CROSS_PITCH)

        for connection in self._connections:
            source = self._shapes.get(connection.from_id)
            target = self._shapes.get(connection.to_id)
            if not source or not target:
                continue
            start = Point(
                source.position.x + source.size.width / 2,
                source.position.y + source.size.height / 2,
            )
            end = Point(
                target.position.x + target.size.width / 2,
                target.position.y + target.size.height / 2,
            )
            connection.start_point = start
            connection.end_point = end
            connection.position = Point(min(start.x, end.x), min(start.y, end.y))
            connection.size = Dimensions(
                max(abs(end.x - start.x), 1.0), max(abs(end.y - start.y), 1.0)
            )

        for group in reversed(self._groups):
            self._fit_group_box(group)

    def _assign_layers(self) -> dict[str, int]:
        successors: dict[str, list[str]] = defaultdict(list)
        in_degree: dict[str, int] = {shape.id: 0 for shape in self._shape_order}
        for connection in self._connections:
            if connection.from_id in in_degree and connection.to_id in in_degree:
                successors[connection.from_id].append(connection.to_id)
                in_degree[connection.to_id] += 1

        layers = {node_id: 0 for node_id in in_degree}
        queue = deque(node_id for node_id, degree in in_degree.items() if degree == 0)
        remaining = dict(in_degree)
        while queue:
            node_id = queue.popleft()
            for successor in successors[node_id]:
                layers[successor] = max(layers[successor], layers[node_id] + 1)
                remaining[successor] -= 1
                if remaining[successor] == 0:
                    queue.append(successor)
        return layers

    def _fit_group_box(self, group: Group) -> None:
        boxes: list[tuple[float, float, float, float]] = []
        for child_id in group.children:
            child = self._shapes.get(child_id) or next(
                (g for g in self._groups if g.id == child_id), None
            )
            if child:
                boxes.append(
                    (
                        child.position.x,
                        child.position.y,
                        child.position.x + child.size.width,
                        child.position.y + child.size.height,
                    )
                )
        if not boxes:
            return
        min_x = min(box[0] for box in boxes) - _GROUP_PADDING
        min_y = min(box[1] for box in boxes) - _GROUP_PADDING
        max_x = max(box[2] for box in boxes) + _GROUP_PADDING
        max_y = max(box[3] for box in boxes) + _GROUP_PADDING
        group.position = Point(min_x, min_y)
        group.size = Dimensions(max_x - min_x, max_y - min_y)
