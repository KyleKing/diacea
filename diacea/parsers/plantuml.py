"""PlantUML parser - converts PlantUML text to IR.

Supports a deployment/component-diagram subset of PlantUML plus the
C4-PlantUML macro dialect. Sequence diagrams are rejected. Since PlantUML
text has no coordinates, a simple layered layout is synthesized and
``diagram.metadata["synthesized_layout"]`` is set to True.
"""

from __future__ import annotations

import re
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Optional

from ..ir import (
    Connection,
    Diagram,
    Dimensions,
    Element,
    Group,
    Parser,
    Point,
    Shape,
)
from ..ir.semantic import SemanticType, infer_semantic_type

_DEFAULT_WIDTH = 160.0
_DEFAULT_HEIGHT = 80.0
_GAP_X = 60.0
_GAP_Y = 100.0
_GROUP_PADDING = 20.0
_KEYWORD_CONFIDENCE = 0.9

_ACTIVITY_KEYWORDS = frozenset(
    {
        'detach',
        'end fork',
        'endif',
        'endwhile',
        'fork',
        'fork again',
        'kill',
        'repeat',
        'start',
        'stop',
    }
)

_ACTIVITY_LINE_RE = re.compile(
    r'^\(\*\)|^if\s*\(.*\)\s*then\b|^while\s*\(.*\)|^:[^;{}]*;$',
    re.IGNORECASE,
)

_SEQUENCE_KEYWORDS = frozenset(
    {
        'activate',
        'alt',
        'autonumber',
        'deactivate',
        'loop',
        'opt',
        'participant',
    }
)

_KEYWORD_INFO: dict[str, tuple[str, Optional[SemanticType]]] = {
    'actor': ('actor', SemanticType.PERSON),
    'agent': ('rectangle', None),
    'card': ('rectangle', None),
    'cloud': ('cloud', SemanticType.CLOUD),
    'component': ('rectangle', SemanticType.COMPONENT),
    'database': ('database', SemanticType.DATABASE),
    'ellipse': ('ellipse', None),
    'folder': ('rectangle', None),
    'frame': ('rectangle', None),
    'hexagon': ('hexagon', None),
    'node': ('rectangle', SemanticType.SERVER),
    'package': ('rectangle', None),
    'person': ('person', SemanticType.PERSON),
    'queue': ('queue', SemanticType.QUEUE),
    'rectangle': ('rectangle', None),
    'storage': ('rectangle', SemanticType.STORAGE),
    'usecase': ('ellipse', None),
}

_C4_ELEMENT_MACROS: dict[str, tuple[str, SemanticType]] = {
    'Component': ('rectangle', SemanticType.COMPONENT),
    'ComponentDb': ('database', SemanticType.DATABASE),
    'ComponentQueue': ('queue', SemanticType.QUEUE),
    'Container': ('rectangle', SemanticType.CONTAINER),
    'ContainerDb': ('database', SemanticType.DATABASE),
    'ContainerQueue': ('queue', SemanticType.QUEUE),
    'Person': ('person', SemanticType.PERSON),
    'System': ('rectangle', SemanticType.SYSTEM),
    'SystemDb': ('database', SemanticType.DATABASE),
    'SystemQueue': ('queue', SemanticType.QUEUE),
}

_C4_BOUNDARY_MACROS = frozenset(
    {
        'Boundary',
        'Container_Boundary',
        'Enterprise_Boundary',
        'System_Boundary',
    }
)

_C4_REL_DIRECTIONS = {
    'D': 'down',
    'Down': 'down',
    'L': 'left',
    'Left': 'left',
    'R': 'right',
    'Right': 'right',
    'U': 'up',
    'Up': 'up',
}

_QUOTED = r'"(?:[^"\\]|\\.)*"'
_IDENT = r'[\w.]+'

_STARTUML_RE = re.compile(r'^@startuml\b\s*(?P<name>.*)$')

_ELEMENT_RE = re.compile(
    r'^(?P<kw>' + '|'.join(sorted(_KEYWORD_INFO)) + r')\s+'
    r'(?:(?P<qlabel>' + _QUOTED + r')(?:\s+as\s+(?P<alias>' + _IDENT + r'))?'
    r'|(?P<bare_id>' + _IDENT + r'))'
    r'(?:\s+<<[^>]*>>)?(?:\s+#\S+)?\s*(?P<brace>\{)?\s*$'
)

_MACRO_RE = re.compile(r'^(?P<name>\w+)\s*\(\s*(?P<args>.*)\)\s*(?P<brace>\{)?\s*$')

_REL_RE = re.compile(
    r'^(?P<src>' + _QUOTED + '|' + _IDENT + r')\s*'
    r'(?P<larrow><)?'
    r'(?P<line1>[-.]+)'
    r'(?:(?P<dir>left|right|up|down|le|ri|do|l|r|u|d)(?P<line2>[-.]+))?'
    r'(?P<rarrow>>)?\s*'
    r'(?P<dst>' + _QUOTED + '|' + _IDENT + r')'
    r'(?:\s*:\s*(?P<label>.+?))?\s*$'
)

_C4_INCLUDE_RE = re.compile(r'!include\s*\S*\bC4_\w+', re.IGNORECASE)
_C4_MACRO_HINT_RE = re.compile(
    r'^\s*(?:Person|System|Container|Component|Rel|Boundary|System_Boundary|Container_Boundary)\w*\s*\(',
    re.MULTILINE,
)

_DIRECTION_HINTS = {
    'd': 'down',
    'do': 'down',
    'down': 'down',
    'l': 'left',
    'le': 'left',
    'left': 'left',
    'r': 'right',
    'ri': 'right',
    'right': 'right',
    'u': 'up',
    'up': 'up',
}


def is_plantuml(content: str) -> bool:
    """Return True if content looks like a PlantUML document."""
    return '@startuml' in content


def is_c4_plantuml(content: str) -> bool:
    """Return True if content looks like a C4-PlantUML document."""
    if not is_plantuml(content):
        return False
    return bool(_C4_INCLUDE_RE.search(content) or _C4_MACRO_HINT_RE.search(content))


def _unescape_label(text: str) -> str:
    result: list[str] = []
    i = 0
    while i < len(text):
        char = text[i]
        if char == '\\' and i + 1 < len(text):
            nxt = text[i + 1]
            if nxt == 'n':
                result.append('\n')
                i += 2
                continue
            if nxt in ('\\', '"'):
                result.append(nxt)
                i += 2
                continue
        if char == '~' and i + 1 < len(text) and text[i + 1] in '<>':
            result.append(text[i + 1])
            i += 2
            continue
        result.append(char)
        i += 1
    return ''.join(result).replace('&amp;', '&')


def _unquote(token: str) -> str:
    if len(token) >= 2 and token.startswith('"') and token.endswith('"'):
        return _unescape_label(token[1:-1])
    return token


def _split_macro_args(args: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    in_quotes = False
    i = 0
    while i < len(args):
        char = args[i]
        if in_quotes:
            buf.append(char)
            if char == '\\' and i + 1 < len(args):
                buf.append(args[i + 1])
                i += 1
            elif char == '"':
                in_quotes = False
        elif char == '"':
            in_quotes = True
            buf.append(char)
        elif char == ',':
            parts.append(''.join(buf).strip())
            buf = []
        else:
            buf.append(char)
        i += 1
    tail = ''.join(buf).strip()
    if tail or parts:
        parts.append(tail)
    return parts


@dataclass
class _ParseState:
    diagram_name: Optional[str] = None
    direction: str = 'top_to_bottom'
    is_c4: bool = False
    elements: list[Element] = field(default_factory=list)
    by_id: dict[str, Element] = field(default_factory=dict)
    by_label: dict[str, str] = field(default_factory=dict)
    group_stack: list[Group] = field(default_factory=list)
    connection_count: int = 0


class PlantUMLParser(Parser):
    """Parse deployment/component-style PlantUML (and C4-PlantUML) to IR."""

    def __init__(self):
        self.warnings: list[str] = []

    def parse(self, data: Any) -> Diagram:
        """Parse PlantUML text to an IR Diagram.

        Raises:
            ValueError: If input is not a string, lacks @startuml, or uses
                sequence-diagram syntax.
        """
        if not isinstance(data, str):
            raise ValueError('PlantUMLParser expects a string input')

        self.warnings = []
        state = _ParseState()
        in_diagram = False
        in_block_comment = False
        skip_until: Optional[str] = None

        for lineno, raw_line in enumerate(data.splitlines(), start=1):
            line = raw_line.strip()
            if not line:
                continue
            if in_block_comment:
                if "'/" in line:
                    in_block_comment = False
                continue
            if line.startswith("/'"):
                if "'/" not in line:
                    in_block_comment = True
                continue
            if line.startswith("'"):
                continue
            if skip_until is not None:
                if line.lower() == skip_until:
                    skip_until = None
                continue
            if not in_diagram:
                if m := _STARTUML_RE.match(line):
                    in_diagram = True
                    state.diagram_name = m.group('name').strip() or None
                continue
            if line.startswith('@enduml'):
                break
            skip_until = self._parse_line(line, lineno, state)

        if not in_diagram:
            raise ValueError('Not a PlantUML document: missing @startuml')

        return self._build_diagram(state)

    def _parse_line(self, line: str, lineno: int, state: _ParseState) -> Optional[str]:
        token = line.split()[0].lower()

        if token in _SEQUENCE_KEYWORDS:
            raise ValueError(f'Line {lineno}: sequence diagrams are not supported (found "{token}")')

        if line.lower() in _ACTIVITY_KEYWORDS or _ACTIVITY_LINE_RE.match(line):
            raise ValueError(
                f'Line {lineno}: PlantUML activity diagrams are not supported '
                f'(found "{line}"); only deployment/component and C4 diagrams '
                'are supported'
            )

        if m := re.match(r'^(left to right|top to bottom) direction$', line.lower()):
            state.direction = m.group(1).replace(' ', '_')
            return None

        if token == 'skinparam':
            self.warnings.append(f'Line {lineno}: skipped skinparam directive')
            return '}' if line.rstrip().endswith('{') else None

        if token in ('caption', 'footer', 'header', 'title'):
            self.warnings.append(f'Line {lineno}: skipped {token} directive')
            return f'end {token}' if line.lower() == token else None

        if token in ('hide', 'show'):
            self.warnings.append(f'Line {lineno}: skipped {token} directive')
            return None

        if line.startswith('!'):
            if _C4_INCLUDE_RE.search(line):
                state.is_c4 = True
                return None
            self.warnings.append(f'Line {lineno}: skipped preprocessor directive: {line}')
            return None

        if line == '}':
            if state.group_stack:
                state.group_stack.pop()
            else:
                self.warnings.append(f'Line {lineno}: unmatched closing brace')
            return None

        if m := _ELEMENT_RE.match(line):
            self._handle_element(m, state)
            return None

        if m := _MACRO_RE.match(line):
            self._handle_macro(m, lineno, state)
            return None

        if m := _REL_RE.match(line):
            self._handle_relationship(m, state)
            return None

        self.warnings.append(f'Line {lineno}: unsupported line skipped: {line}')
        return None

    def _handle_element(self, m: re.Match[str], state: _ParseState) -> None:
        keyword = m.group('kw')
        shape_type, semantic = _KEYWORD_INFO[keyword]

        if m.group('qlabel'):
            label = _unescape_label(m.group('qlabel')[1:-1])
            elem_id = m.group('alias') or self._derive_id(label, state)
        else:
            elem_id = m.group('bare_id')
            label = elem_id

        if m.group('brace'):
            self._add_group(state, elem_id, label, semantic)
        else:
            self._add_shape(state, elem_id, label, shape_type, semantic, _KEYWORD_CONFIDENCE)

    def _handle_macro(self, m: re.Match[str], lineno: int, state: _ParseState) -> None:
        name = m.group('name')
        args = _split_macro_args(m.group('args'))

        if name.startswith('LAYOUT'):
            return

        base_name = name
        is_external = False
        for suffix in ('_Ext', '_Int'):
            if base_name.endswith(suffix):
                base_name = base_name.removesuffix(suffix)
                is_external = suffix == '_Ext'
                break

        if base_name in _C4_ELEMENT_MACROS and len(args) >= 1:
            state.is_c4 = True
            shape_type, semantic = _C4_ELEMENT_MACROS[base_name]
            elem_id = args[0]
            label = _unquote(args[1]) if len(args) > 1 else elem_id
            metadata: dict[str, Any] = {}
            if len(args) > 2 and args[2]:
                metadata['technology'] = _unquote(args[2])
            if len(args) > 3 and args[3]:
                metadata['description'] = _unquote(args[3])
            if is_external:
                metadata['external'] = True
            self._add_shape(state, elem_id, label, shape_type, semantic, 1.0, metadata)
            return

        if base_name in _C4_BOUNDARY_MACROS and len(args) >= 1:
            state.is_c4 = True
            elem_id = args[0]
            label = _unquote(args[1]) if len(args) > 1 else elem_id
            self._add_group(state, elem_id, label, None)
            if not m.group('brace'):
                state.group_stack.pop()
                self.warnings.append(f'Line {lineno}: boundary "{elem_id}" without opening brace')
            return

        if (base_name == 'Rel' or base_name.startswith(('Rel_', 'BiRel'))) and len(args) >= 2:
            state.is_c4 = True
            self._add_c4_relationship(name, args, state)
            return

        self.warnings.append(f'Line {lineno}: skipped unknown macro: {name}(...)')

    def _add_c4_relationship(self, name: str, args: list[str], state: _ParseState) -> None:
        from_id = self._resolve_endpoint(args[0], state)
        to_id = self._resolve_endpoint(args[1], state)
        label = _unquote(args[2]) if len(args) > 2 else ''
        connection_type = 'bidirectional' if name.startswith('BiRel') else 'directed'

        metadata: dict[str, Any] = {}
        if name.startswith('Rel_'):
            suffix = name.removeprefix('Rel_')
            if (direction := _C4_REL_DIRECTIONS.get(suffix)) is not None:
                metadata['direction_hint'] = direction
        if len(args) > 3 and args[3]:
            metadata['technology'] = _unquote(args[3])

        self._add_connection(state, from_id, to_id, label, connection_type, metadata)

    def _handle_relationship(self, m: re.Match[str], state: _ParseState) -> None:
        from_id = self._resolve_endpoint(m.group('src'), state)
        to_id = self._resolve_endpoint(m.group('dst'), state)

        has_left = bool(m.group('larrow'))
        has_right = bool(m.group('rarrow'))
        if has_left and has_right:
            connection_type = 'bidirectional'
        elif has_left:
            from_id, to_id = to_id, from_id
            connection_type = 'directed'
        elif has_right:
            connection_type = 'directed'
        else:
            connection_type = 'undirected'

        body = m.group('line1') + (m.group('line2') or '')
        dashed = '.' in body

        label = ''
        if m.group('label'):
            label = _unquote(m.group('label').strip())

        metadata: dict[str, Any] = {}
        if (raw_dir := m.group('dir')) and (direction := _DIRECTION_HINTS.get(raw_dir)):
            metadata['direction_hint'] = direction

        conn = self._add_connection(state, from_id, to_id, label, connection_type, metadata)
        if dashed:
            conn.style.stroke_style = 'dashed'

    def _add_shape(
        self,
        state: _ParseState,
        elem_id: str,
        label: str,
        shape_type: str,
        semantic: Optional[SemanticType],
        confidence: float = _KEYWORD_CONFIDENCE,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Shape:
        shape = Shape(
            id=elem_id,
            position=Point(0.0, 0.0),
            size=Dimensions(_DEFAULT_WIDTH, _DEFAULT_HEIGHT),
            label=label,
            shape_type=shape_type,
            metadata=metadata or {},
        )
        if semantic is None:
            inferred, inferred_confidence = infer_semantic_type(shape_type, label, shape.size)
            shape.semantic_type = inferred
            shape.semantic_confidence = inferred_confidence
        else:
            shape.semantic_type = semantic
            shape.semantic_confidence = confidence
        self._register(state, shape, label)
        return shape

    def _add_group(
        self,
        state: _ParseState,
        elem_id: str,
        label: str,
        semantic: Optional[SemanticType],
    ) -> Group:
        group = Group(
            id=elem_id,
            position=Point(0.0, 0.0),
            size=Dimensions(_DEFAULT_WIDTH, _DEFAULT_HEIGHT),
            label=label,
        )
        if semantic is not None:
            group.semantic_type = semantic
            group.semantic_confidence = _KEYWORD_CONFIDENCE
        self._register(state, group, label)
        state.group_stack.append(group)
        return group

    def _add_connection(
        self,
        state: _ParseState,
        from_id: str,
        to_id: str,
        label: str,
        connection_type: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Connection:
        conn = Connection(
            id=f'conn-{state.connection_count}',
            position=Point(0.0, 0.0),
            size=Dimensions(0.0, 0.0),
            from_id=from_id,
            to_id=to_id,
            label=label,
            connection_type=connection_type,
            metadata=metadata or {},
        )
        state.connection_count += 1
        state.elements.append(conn)
        return conn

    def _register(self, state: _ParseState, element: Element, label: str) -> None:
        state.elements.append(element)
        state.by_id[element.id] = element
        state.by_label.setdefault(label, element.id)
        if state.group_stack and state.group_stack[-1].id != element.id:
            state.group_stack[-1].children.append(element.id)

    def _resolve_endpoint(self, token: str, state: _ParseState) -> str:
        if token.startswith('"'):
            label = _unescape_label(token[1:-1])
            if (existing := state.by_label.get(label)) is not None:
                return existing
            elem_id = self._derive_id(label, state)
            self._add_shape(state, elem_id, label, 'rectangle', None)
            return elem_id
        if token not in state.by_id:
            self._add_shape(state, token, token, 'rectangle', None)
        return token

    def _derive_id(self, label: str, state: _ParseState) -> str:
        base = re.sub(r'\W', '_', label).strip('_') or 'elem'
        candidate = base
        counter = 2
        while candidate in state.by_id:
            candidate = f'{base}_{counter}'
            counter += 1
        return candidate

    def _build_diagram(self, state: _ParseState) -> Diagram:
        self._synthesize_layout(state)
        diagram = Diagram(
            id='plantuml-diagram',
            name=state.diagram_name,
            elements=state.elements,
            metadata={
                'direction': state.direction,
                'synthesized_layout': True,
            },
        )
        if state.is_c4:
            diagram.metadata['c4_plantuml'] = True
        return diagram

    def _synthesize_layout(self, state: _ParseState) -> None:
        shapes = [e for e in state.elements if isinstance(e, Shape)]
        shape_ids = {s.id for s in shapes}
        connections = [e for e in state.elements if isinstance(e, Connection)]

        adjacency: dict[str, list[str]] = defaultdict(list)
        in_degree: dict[str, int] = {sid: 0 for sid in shape_ids}
        for conn in connections:
            if conn.from_id in shape_ids and conn.to_id in shape_ids and conn.from_id != conn.to_id:
                adjacency[conn.from_id].append(conn.to_id)
                in_degree[conn.to_id] += 1

        layers: dict[str, int] = {sid: 0 for sid in shape_ids}
        queue = deque(s.id for s in shapes if in_degree[s.id] == 0)
        visited: set[str] = set()
        while queue:
            current = queue.popleft()
            visited.add(current)
            for target in adjacency[current]:
                layers[target] = max(layers[target], layers[current] + 1)
                in_degree[target] -= 1
                if in_degree[target] == 0:
                    queue.append(target)

        if unvisited := shape_ids - visited:
            overflow_layer = max(layers.values(), default=0) + 1
            for sid in unvisited:
                layers[sid] = overflow_layer

        buckets: dict[int, list[Shape]] = defaultdict(list)
        for shape in shapes:
            buckets[layers[shape.id]].append(shape)

        horizontal = state.direction == 'left_to_right'
        for layer_index in sorted(buckets):
            for position_index, shape in enumerate(buckets[layer_index]):
                along = layer_index * ((_DEFAULT_WIDTH + _GAP_X) if horizontal else (_DEFAULT_HEIGHT + _GAP_Y))
                across = position_index * ((_DEFAULT_HEIGHT + _GAP_Y) if horizontal else (_DEFAULT_WIDTH + _GAP_X))
                if horizontal:
                    shape.position = Point(along, across)
                else:
                    shape.position = Point(across, along)

        for group in (e for e in state.elements if isinstance(e, Group)):
            descendants = self._descendant_shapes(group, state, set())
            if not descendants:
                continue
            min_x = min(s.position.x for s in descendants) - _GROUP_PADDING
            min_y = min(s.position.y for s in descendants) - _GROUP_PADDING
            max_x = max(s.position.x + s.size.width for s in descendants) + _GROUP_PADDING
            max_y = max(s.position.y + s.size.height for s in descendants) + _GROUP_PADDING
            group.position = Point(min_x, min_y)
            group.size = Dimensions(max_x - min_x, max_y - min_y)

    def _descendant_shapes(self, group: Group, state: _ParseState, seen: set[str]) -> list[Shape]:
        result: list[Shape] = []
        for child_id in group.children:
            if child_id in seen:
                continue
            seen.add(child_id)
            child = state.by_id.get(child_id)
            if isinstance(child, Shape):
                result.append(child)
            elif isinstance(child, Group):
                result.extend(self._descendant_shapes(child, state, seen))
        return result
