"""Mermaid parser - converts Mermaid flowchart/graph, sequence, and C4 text to IR.

Supports a deliberate subset of Mermaid: flowchart/graph, sequence, and C4
(C4Context, C4Container, ...) diagrams. Other Mermaid diagram types
(classDiagram, erDiagram, ...) are rejected with a ValueError. Styling
directives (classDef, style, click, linkStyle) and unrecognized lines are
skipped with a warning instead of failing. Sequence control blocks (loop,
alt, par, ...) and notes are skipped with warnings while the messages inside
them are still parsed.

Since Mermaid text has no coordinates, a layered layout is synthesized along
the declared direction (see `diacea.layout`) and flagged via
``diagram.metadata["synthesized_layout"]``.
"""

from __future__ import annotations

import re
from typing import Any

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
from ..layout import estimate_label_size, layout_diagram
from .plantuml import PlantUMLParser

_HEADER_RE = re.compile(r'^(?:flowchart|graph)\b\s*(LR|RL|TD|TB|BT)?\s*;?\s*$', re.IGNORECASE)

_SEQUENCE_HEADER_RE = re.compile(r'^sequenceDiagram\s*;?\s*$')

_FRONTMATTER_TITLE_RE = re.compile(r'^title:\s*(.+?)\s*$')

_C4_HEADER_RE = re.compile(r'^C4(?:Component|Container|Context|Deployment|Dynamic)\s*;?\s*$')

_OTHER_DIAGRAM_KEYWORDS = (
    'block-beta',
    'classDiagram',
    'erDiagram',
    'gantt',
    'gitGraph',
    'journey',
    'mindmap',
    'packet-beta',
    'pie',
    'quadrantChart',
    'requirementDiagram',
    'sankey-beta',
    'stateDiagram',
    'stateDiagram-v2',
    'timeline',
    'xychart-beta',
    'zenuml',
)

_SKIPPED_DIRECTIVES = ('class', 'classDef', 'click', 'direction', 'linkStyle')

_STYLE_RE = re.compile(r'^style\s+([\w.:,-]+)\s+(.+)$')

_SEQUENCE_BLOCK_KEYWORDS = (
    'alt',
    'and',
    'box',
    'break',
    'critical',
    'else',
    'end',
    'loop',
    'opt',
    'option',
    'par',
    'rect',
)

_SEQUENCE_SKIPPED_DIRECTIVES = (
    'activate',
    'autonumber',
    'deactivate',
    'link',
    'links',
    'note',
    'properties',
)

_SEQ_PARTICIPANT_RE = re.compile(r'^(participant|actor)\s+([\w.-]+)(?:\s+as\s+(.+))?$')

_SEQ_MESSAGE_RE = re.compile(
    r'^([\w.]+)\s*(<<-->>|<<->>|-->>|->>|--[>x)]|-[>x)])\s*([+-]?)\s*([\w.]+)\s*(?::\s*(.*))?$'
)

_LINK_RE = re.compile(
    r'\s*(<?(?:={2,}|-{2,}|-\.+-*)[>xo]?)'
    r'(?:\|([^|]*)\|)?\s*'
)

_TEXT_ARROW_SUBS = (
    (re.compile(r'--\s*([^-|>][^|]*?)\s*-->'), r'-->|\1|'),
    (re.compile(r'--\s*([^-|>][^|]*?)\s*---'), r'---|\1|'),
    (re.compile(r'-\.\s*([^-|.>][^|]*?)\s*\.->'), r'-.->|\1|'),
    (re.compile(r'==\s*([^=|>][^|]*?)\s*==>'), r'==>|\1|'),
)

_NODE_TOKEN_RE = re.compile(r'^([A-Za-z0-9_.:-]+)\s*(.*)$', re.DOTALL)

_CLASS_SUFFIX_RE = re.compile(r':::[\w-]+$')

_FA_ICON_RE = re.compile(r'fa[brs]?:fa-([A-Za-z0-9-]+)\s*')

_FA_ICON_SEMANTICS: dict[str, SemanticType] = {
    'cloud': SemanticType.CLOUD,
    'cog': SemanticType.SERVICE,
    'cogs': SemanticType.SERVICE,
    'database': SemanticType.DATABASE,
    'envelope': SemanticType.QUEUE,
    'gear': SemanticType.SERVICE,
    'gears': SemanticType.SERVICE,
    'globe': SemanticType.EXTERNAL,
    'person': SemanticType.PERSON,
    'server': SemanticType.SERVER,
    'user': SemanticType.PERSON,
    'users': SemanticType.PERSON,
}

_SUBGRAPH_TITLED_RE = re.compile(r'^([A-Za-z0-9_.-]+)\s*\[(.*)\]$')

_BRACKET_SHAPES = (
    ('(((', ')))', 'circle'),
    ('([', '])', 'stadium'),
    ('[[', ']]', 'subroutine'),
    ('[(', ')]', 'cylinder'),
    ('((', '))', 'circle'),
    ('[/', '\\]', 'trapezoid'),
    ('[\\', '/]', 'trapezoid'),
    ('[\\', '\\]', 'parallelogram'),
    ('>', ']', 'rectangle'),
    ('{{', '}}', 'hexagon'),
    ('[/', '/]', 'parallelogram'),
    ('[', ']', 'rectangle'),
    ('(', ')', 'rounded_rectangle'),
    ('{', '}', 'diamond'),
)

_NODE_HEIGHT_BASE = 60.0
_LAYER_PITCH = 240.0


def is_mermaid(content: str) -> bool:
    """Cheap sniff: does the first meaningful line start a Mermaid diagram?"""
    first = _first_meaningful_line(content)
    if first is None:
        return False
    if _HEADER_RE.match(first) or _SEQUENCE_HEADER_RE.match(first) or _C4_HEADER_RE.match(first):
        return True
    keyword = first.split()[0].rstrip(':;')
    return keyword in _OTHER_DIAGRAM_KEYWORDS


def is_mermaid_flowchart(content: str) -> bool:
    """Whether the content is a Mermaid flowchart/graph diagram."""
    first = _first_meaningful_line(content)
    return first is not None and _HEADER_RE.match(first) is not None


def is_mermaid_sequence(content: str) -> bool:
    """Whether the content is a Mermaid sequence diagram."""
    first = _first_meaningful_line(content)
    return first is not None and _SEQUENCE_HEADER_RE.match(first) is not None


def is_mermaid_c4(content: str) -> bool:
    """Whether the content is a Mermaid C4 diagram."""
    first = _first_meaningful_line(content)
    return first is not None and _C4_HEADER_RE.match(first) is not None


def _split_frontmatter(content: str) -> tuple[str, str | None]:
    lines = content.split('\n')
    start = next((i for i, line in enumerate(lines) if line.strip()), None)
    if start is None or lines[start].strip() != '---':
        return (content, None)
    title = None
    for end in range(start + 1, len(lines)):
        stripped = lines[end].strip()
        if stripped == '---':
            for index in range(start, end + 1):
                lines[index] = ''
            return ('\n'.join(lines), title)
        if match := _FRONTMATTER_TITLE_RE.match(stripped):
            title = match.group(1).strip('"\'')
    return (content, None)


def _first_meaningful_line(content: str) -> str | None:
    content, _ = _split_frontmatter(content)
    for raw in content.splitlines():
        line = raw.strip()
        if not line or line.startswith(('%%', '```')):
            continue
        return line
    return None


def _unescape_label(label: str) -> str:
    text = label.strip()
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        text = text[1:-1]
    text = text.replace('<br/>', '\n').replace('<br>', '\n')
    text = text.replace('#quot;', '"')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&#124;', '|')
    return text.replace('&amp;', '&')


def _extract_fa_icons(label: str) -> tuple[str, list[str]]:
    icons = _FA_ICON_RE.findall(label)
    if not icons:
        return (label, [])
    cleaned = _FA_ICON_RE.sub('', label)
    return (re.sub(r'[ \t]{2,}', ' ', cleaned).strip(), icons)


def _icon_metadata(icons: list[str]) -> dict[str, Any]:
    metadata: dict[str, Any] = {'mermaid': {'icons': icons}}
    for icon in icons:
        if (semantic := _FA_ICON_SEMANTICS.get(icon)) is not None:
            metadata['semantic_type'] = semantic.value
            break
    return metadata


def _split_arrow_attrs(arrow: str) -> tuple[str, str, float | None]:
    has_head = arrow[-1] in '>xo'
    if arrow.startswith('<') and has_head:
        connection_type = 'bidirectional'
    elif has_head:
        connection_type = 'directed'
    else:
        connection_type = 'undirected'
    stroke_style = 'dashed' if '.' in arrow else 'solid'
    stroke_width = 3.0 if '=' in arrow else None
    return (connection_type, stroke_style, stroke_width)


def _split_on_ampersand(segment: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    in_quote = False
    current: list[str] = []
    for char in segment:
        if char == '"':
            in_quote = not in_quote
        elif char in '[({' and not in_quote:
            depth += 1
        elif char in '])}' and not in_quote:
            depth -= 1
        if char == '&' and depth == 0 and not in_quote:
            parts.append(''.join(current))
            current = []
        else:
            current.append(char)
    parts.append(''.join(current))
    return [part.strip() for part in parts if part.strip()]


class MermaidParser(Parser):
    """Parse Mermaid flowchart/graph, sequence, and C4 text into the IR."""

    def __init__(self) -> None:
        self.warnings: list[str] = []

    def parse(self, data: Any) -> Diagram:
        """Parse Mermaid flowchart, sequence, or C4 text to an IR Diagram."""
        if not isinstance(data, str):
            raise ValueError('Mermaid parser expects a string input')

        self.warnings = []
        data, title = _split_frontmatter(data)
        if is_mermaid_sequence(data):
            return self._parse_sequence(data, title)
        if is_mermaid_c4(data):
            return self._parse_c4(data, title)
        self._shapes: dict[str, Shape] = {}
        self._shape_order: list[Shape] = []
        self._connections: list[Connection] = []
        self._groups: list[Group] = []
        self._group_stack: list[Group] = []
        self._direction = 'TD'
        self._styles: list[tuple[int, list[str], dict[str, str]]] = []
        self._bare_ids: set[str] = set()  # nodes only ever referenced by id, never given a shape or label

        statements = self._collect_statements(data)
        for line_number, statement in statements:
            self._parse_statement(statement, line_number)
        self._apply_styles()
        self._retarget_subgraph_endpoints()

        if self._group_stack:
            self.warnings.append(f"unclosed subgraph '{self._group_stack[-1].id}': missing 'end'")
            self._group_stack = []

        for shape in self._shape_order:
            shape.semantic_type, shape.semantic_confidence = infer_semantic_type(
                shape_type=shape.shape_type,
                label=shape.label,
                size=None,
                style=shape.style,
                metadata=shape.metadata,
            )

        diagram = Diagram(
            id='mermaid-flowchart',
            name=title,
            metadata={
                'mermaid': {'diagram_type': 'flowchart', 'direction': self._direction},
                'direction': self._direction,
                'explicit_shapes': True,
            },
        )
        for shape in self._shape_order:
            diagram.add_element(shape)
        for connection in self._connections:
            diagram.add_element(connection)
        for group in self._groups:
            diagram.add_element(group)
        layout_diagram(diagram, diagram.direction or 'TB')
        return diagram

    def _parse_c4(self, data: str, title: str | None) -> Diagram:
        """Parse a Mermaid C4 diagram, which shares the C4-PlantUML macro dialect."""
        lines = data.splitlines()
        header_index = next(
            index for index, line in enumerate(lines) if line.strip() and not line.strip().startswith(('%%', '```'))
        )
        c4_level = lines[header_index].strip().rstrip(';').strip()
        lines[header_index] = '@startuml'
        body: list[str] = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(('%%', '```')):
                body.append('')
            elif stripped.lower().startswith('title ') and title is None:
                title = stripped[len('title ') :].strip()
                body.append('')
            else:
                body.append(line)

        macro_parser = PlantUMLParser()
        diagram = macro_parser.parse('\n'.join(body))
        self.warnings.extend(macro_parser.warnings)
        for element in diagram.elements:
            if isinstance(element, (Shape, Group, Connection)):
                element.label = _unescape_label(element.label.replace('\\"', '"').replace('\\\\', '\\'))
        diagram.id = 'mermaid-c4'
        diagram.name = title
        diagram.metadata['mermaid'] = {'diagram_type': 'c4', 'c4_level': c4_level}
        return diagram

    def _collect_statements(self, data: str) -> list[tuple[int, str]]:
        header_seen = False
        statements: list[tuple[int, str]] = []
        for line_number, raw in enumerate(data.splitlines(), start=1):
            line = raw.strip()
            if not line or line.startswith('```'):
                continue
            if line.startswith('%%'):
                self.warnings.append(f'line {line_number}: skipped comment')
                continue
            if not header_seen:
                parts = line.split(';')
                self._parse_header(parts[0].strip(), line_number)
                header_seen = True
                statements.extend((line_number, part.strip()) for part in parts[1:] if part.strip())
                continue
            statements.append((line_number, line.rstrip(';').strip()))
        if not header_seen:
            raise ValueError('Empty input: no Mermaid diagram found')
        return statements

    def _parse_header(self, line: str, line_number: int) -> None:
        if match := _HEADER_RE.match(line.split(';', maxsplit=1)[0].strip()):
            self._direction = (match.group(1) or 'TD').upper()
            return
        keyword = line.split(maxsplit=1)[0].rstrip(':;')
        if keyword in _OTHER_DIAGRAM_KEYWORDS:
            msg = (
                f"Unsupported Mermaid diagram type '{keyword}': "
                'only flowchart/graph, sequence, and C4 diagrams are supported'
            )
            raise ValueError(msg)
        msg = f"line {line_number}: not a Mermaid flowchart (expected 'flowchart' or 'graph' header)"
        raise ValueError(msg)

    def _parse_sequence(self, data: str, title: str | None) -> Diagram:
        self._shapes = {}
        self._shape_order = []
        self._connections = []
        self._groups = []
        self._group_stack = []
        self._sequence_title: str | None = None

        header_seen = False
        for line_number, raw in enumerate(data.splitlines(), start=1):
            line = raw.strip()
            if not line or line.startswith('```'):
                continue
            if line.startswith('%%'):
                self.warnings.append(f'line {line_number}: skipped comment')
                continue
            if not header_seen:
                header_seen = True
                continue
            self._parse_sequence_statement(line.rstrip(';').strip(), line_number)

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
            id='mermaid-sequence',
            name=title or self._sequence_title,
            metadata={
                'mermaid': {'diagram_type': 'sequence'},
                'synthesized_layout': True,
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
                is_actor=kind == 'actor',
            )
            return
        if match := _SEQ_MESSAGE_RE.match(statement):
            from_id, arrow, _activation, to_id, label = match.groups()
            self._declare_participant(from_id)
            self._declare_participant(to_id)
            connection_type = 'bidirectional' if arrow.startswith('<<') else 'directed'
            stroke_style = 'dashed' if '--' in arrow else 'solid'
            self._connections.append(
                Connection(
                    id=f'message-{len(self._connections)}',
                    position=Point(0.0, 0.0),
                    size=Dimensions(1.0, 1.0),
                    from_id=from_id,
                    to_id=to_id,
                    label=_unescape_label(label) if label else '',
                    connection_type=connection_type,
                    style=Style(stroke_style=stroke_style),
                    metadata={'mermaid': {'arrow': arrow}},
                )
            )
            return

        keyword = statement.split(maxsplit=1)[0].rstrip(':').lower()
        if keyword == 'title':
            self._sequence_title = statement.split(maxsplit=1)[1].strip() if ' ' in statement else None
            return
        if keyword in _SEQUENCE_BLOCK_KEYWORDS or keyword in _SEQUENCE_SKIPPED_DIRECTIVES:
            self.warnings.append(f"line {line_number}: skipped '{keyword}' sequence directive")
            return
        self.warnings.append(f'line {line_number}: unrecognized line skipped: {statement!r}')

    def _declare_participant(
        self,
        participant_id: str,
        label: str | None = None,
        is_actor: bool = False,
    ) -> None:
        if (shape := self._shapes.get(participant_id)) is not None:
            if label is not None:
                shape.label = label
            if is_actor:
                shape.metadata['semantic_type'] = SemanticType.PERSON.value
            return
        metadata = {'semantic_type': SemanticType.PERSON.value} if is_actor else None
        self._create_shape(
            participant_id,
            label=label or participant_id,
            shape_type='rectangle',
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

        if keyword == 'end' and statement == 'end':
            if self._group_stack:
                self._group_stack.pop()
            else:
                self.warnings.append(f"line {line_number}: 'end' without matching subgraph")
            return
        if keyword == 'subgraph':
            self._parse_subgraph(statement, line_number)
            return
        if keyword in _SKIPPED_DIRECTIVES:
            self.warnings.append(f"line {line_number}: skipped '{keyword}' directive")
            return
        if match := _STYLE_RE.match(statement):
            pairs = (part.split(':', 1) for part in match.group(2).rstrip(';').split(',') if ':' in part)
            properties = {name.strip(): value.strip() for name, value in pairs}
            self._styles.append((line_number, match.group(1).split(','), properties))
            return

        if self._parse_node_or_edges(statement, line_number):
            return
        self.warnings.append(f'line {line_number}: unrecognized line skipped: {statement!r}')

    def _retarget_subgraph_endpoints(self) -> None:
        """Point edges written against a subgraph id at the group, not at a node of the same name.

        `subgraph api ... end` followed by `api --> db` links the subgraph
        itself. The edge parser only sees a bare id and declares a node for
        it, so that placeholder is removed again here.
        """
        groups_by_raw_id = {re.sub(r'\W', '_', group.id): group for group in self._groups}
        groups_by_raw_id.update({group.source_shape_id: group for group in self._groups})
        placeholders = {
            shape.id for shape in self._shape_order if shape.id in groups_by_raw_id and shape.id in self._bare_ids
        }
        if not placeholders:
            return
        for connection in self._connections:
            if connection.from_id in placeholders:
                connection.from_id = groups_by_raw_id[connection.from_id].id
            if connection.to_id in placeholders:
                connection.to_id = groups_by_raw_id[connection.to_id].id
        self._shape_order = [shape for shape in self._shape_order if shape.id not in placeholders]
        for shape_id in placeholders:
            del self._shapes[shape_id]
        for group in self._groups:
            group.children = [child_id for child_id in group.children if child_id not in placeholders]

    def _apply_styles(self) -> None:
        """Apply `style <id> fill:...,stroke:...` directives to the nodes and subgraphs they name."""
        groups_by_raw_id = {re.sub(r'\W', '_', group.id): group for group in self._groups}
        for line_number, target_ids, properties in self._styles:
            for target_id in target_ids:
                target = self._shapes.get(target_id) or groups_by_raw_id.get(target_id)
                if target is None:
                    self.warnings.append(f"line {line_number}: style for unknown node '{target_id}' skipped")
                    continue
                style = target.style
                style.fill_color = properties.get('fill', style.fill_color)
                style.stroke_color = properties.get('stroke', style.stroke_color)
                if (width := re.match(r'[\d.]+', properties.get('stroke-width', ''))) is not None:
                    style.stroke_width = float(width.group(0))
                if 'stroke-dasharray' in properties:
                    style.stroke_style = 'dashed'

    def _parse_subgraph(self, statement: str, line_number: int) -> None:
        rest = statement[len('subgraph') :].strip()
        if not rest:
            self.warnings.append(f'line {line_number}: subgraph without an id skipped')
            return
        if match := _SUBGRAPH_TITLED_RE.match(rest):
            group_id, label = match.group(1), _unescape_label(match.group(2))
        else:
            label = _unescape_label(rest)
            group_id = re.sub(r'\W', '_', label)
        group_id = GROUP_ID_PREFIX + re.sub(r'^group[-_]', '', group_id)
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

        for index, (arrow, label) in enumerate(zip(arrows, labels, strict=False)):
            connection_type, stroke_style, stroke_width = _split_arrow_attrs(arrow)
            for from_id in resolved[index]:
                for to_id in resolved[index + 1]:
                    self._connections.append(
                        Connection(
                            id=f'edge-{len(self._connections)}',
                            position=Point(0.0, 0.0),
                            size=Dimensions(1.0, 1.0),
                            from_id=from_id,
                            to_id=to_id,
                            label=_unescape_label(label) if label else '',
                            connection_type=connection_type,
                            style=Style(stroke_style=stroke_style, stroke_width=stroke_width),
                            metadata={'mermaid': {'arrow': arrow}},
                        )
                    )
        return True

    def _declare_node(self, token: str, line_number: int) -> str | None:
        match = _NODE_TOKEN_RE.match(_CLASS_SUFFIX_RE.sub('', token.strip()))
        if not match:
            return None
        node_id, body = match.group(1), match.group(2).strip()

        if not body:
            if node_id not in self._shapes:
                self._create_shape(node_id, label=node_id, shape_type='rectangle')
                self._bare_ids.add(node_id)
            else:
                self._adopt_into_group(node_id)
            return node_id

        for opening, closing, shape_type in _BRACKET_SHAPES:
            if body.startswith(opening) and body.endswith(closing):
                label = _unescape_label(body[len(opening) : -len(closing)])
                label, icons = _extract_fa_icons(label)
                self._bare_ids.discard(node_id)
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

        self.warnings.append(f'line {line_number}: unsupported node syntax skipped: {token.strip()!r}')
        return None

    def _create_shape(
        self,
        node_id: str,
        label: str,
        shape_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        shape = Shape(
            id=node_id,
            position=Point(0.0, 0.0),
            size=estimate_label_size(label),
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
