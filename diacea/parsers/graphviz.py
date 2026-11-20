"""GraphViz DOT parser - converts DOT text to IR.

Supports the DOT language proper: `graph`/`digraph` (optionally `strict`),
node and edge statements with attribute lists, edge chains and `{a b}`
endpoint sets, `node`/`edge`/`graph` default attributes scoped to their
subgraph, and `cluster` subgraphs (which become groups). Ports and
compass points are dropped, and HTML or record labels are flattened to
plain text with a warning.

DOT carries no coordinates, so a layered layout is synthesized along
`rankdir` (see `diacea.layout`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
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

_HEADER_RE = re.compile(
    r'^\s*(?:strict\s+)?(?:di)?graph\b\s*(?:"(?:[^"\\]|\\.)*"|[\w.]+)?\s*\{',
    re.IGNORECASE,
)

_COMMENT_RE = re.compile(r'/\*.*?\*/|//[^\n]*|^\s*#[^\n]*', re.DOTALL | re.MULTILINE)

_TOKEN_RE = re.compile(
    r"""
    (?P<space>\s+)
    | (?P<comment>/\*.*?\*/ | //[^\n]* | \#[^\n]*)
    | (?P<quoted>"(?:[^"\\]|\\.)*")
    | (?P<edge>->|--)
    | (?P<punct>[{}\[\];,=:+])
    | (?P<bare>[A-Za-z_\u0080-\uffff][\w\u0080-\uffff]* | -?(?:\.\d+|\d+(?:\.\d*)?))
    """,
    re.VERBOSE | re.DOTALL,
)

_CLUSTER_PREFIX = 'cluster'

_DOT_SHAPE_TYPES = {
    'box': 'rectangle',
    'box3d': 'rectangle',
    'circle': 'circle',
    'cloud': 'cloud',
    'component': 'rectangle',
    'cylinder': 'cylinder',
    'diamond': 'diamond',
    'doublecircle': 'circle',
    'egg': 'ellipse',
    'ellipse': 'ellipse',
    'folder': 'queue',
    'hexagon': 'hexagon',
    'mrecord': 'rounded_rectangle',
    'none': 'rectangle',
    'note': 'document',
    'octagon': 'rectangle',
    'oval': 'ellipse',
    'parallelogram': 'parallelogram',
    'plain': 'rectangle',
    'plaintext': 'rectangle',
    'point': 'circle',
    'rect': 'rectangle',
    'record': 'rectangle',
    'rectangle': 'rectangle',
    'square': 'rectangle',
    'tab': 'rectangle',
}

# DOT shapes that state what a node is rather than only how it looks
_DOT_SHAPE_SEMANTICS: dict[str, SemanticType] = {
    'box3d': SemanticType.SYSTEM,
    'component': SemanticType.CONTAINER,
    'octagon': SemanticType.EXTERNAL,
}

_SHAPE_CONFIDENCE = 0.9

_RANKDIRS = {'BT', 'LR', 'RL', 'TB'}


def is_dot(content: str) -> bool:
    """Cheap sniff: does the content open a DOT `graph`/`digraph` block?"""
    return _HEADER_RE.match(_COMMENT_RE.sub('', content)) is not None


@dataclass
class _Token:
    kind: str  # id, edge, punct, eof
    value: str
    line: int
    quoted: bool = False
    html: bool = False


@dataclass
class _Scope:
    """Defaults and membership for one `{ ... }` block."""

    node_attrs: dict[str, str] = field(default_factory=dict)
    edge_attrs: dict[str, str] = field(default_factory=dict)
    group: Group | None = None
    owns_group: bool = False
    mentioned: list[str] = field(default_factory=list)

    def child(self, group: Group | None) -> _Scope:
        return _Scope(dict(self.node_attrs), dict(self.edge_attrs), group or self.group, owns_group=group is not None)


@dataclass
class _Endpoint:
    node_id: str | None
    ids: list[str]


def _tokenize(text: str) -> list[_Token]:
    tokens: list[_Token] = []
    position = 0
    line = 1
    while position < len(text):
        if text[position] == '<':
            end = _html_end(text, position)
            if end is not None:
                tokens.append(_Token('id', text[position + 1 : end], line, html=True))
                line += text.count('\n', position, end + 1)
                position = end + 1
                continue
        match = _TOKEN_RE.match(text, position)
        if not match:
            msg = f'Line {line}: unexpected character {text[position]!r} in DOT input'
            raise ValueError(msg)
        raw = match.group(0)
        if match.lastgroup == 'quoted':
            tokens.append(_Token('id', _unquote(raw), line, quoted=True))
        elif match.lastgroup == 'bare':
            tokens.append(_Token('id', raw, line))
        elif match.lastgroup in {'edge', 'punct'}:
            tokens.append(_Token(match.lastgroup, raw, line))
        line += raw.count('\n')
        position = match.end()
    tokens.append(_Token('eof', '', line))
    return tokens


def _html_end(text: str, start: int) -> int | None:
    depth = 0
    for index in range(start, len(text)):
        if text[index] == '<':
            depth += 1
        elif text[index] == '>':
            depth -= 1
            if depth == 0:
                return index
    return None


def _unquote(raw: str) -> str:
    body = raw[1:-1].replace('\\\n', '')
    return body.replace('\\"', '"')


def _unescape_label(label: str) -> str:
    text = re.sub(r'\\[nlr]', '\n', label)
    return text.replace('\\\\', '\\').rstrip('\n')


def _strip_html(label: str) -> str:
    text = re.sub(r'<br\s*/?>', '\n', label, flags=re.IGNORECASE)
    text = re.sub(r'</tr\s*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"').replace('&amp;', '&')
    return '\n'.join(line.strip() for line in text.splitlines() if line.strip())


def _flatten_record(label: str) -> str:
    text = re.sub(r'<[^>]*>', '', label)
    fields = [part.strip() for part in re.split(r'[{}|]', text)]
    return '\n'.join(part for part in fields if part)


class GraphVizParser(Parser):
    """Parse GraphViz DOT text into the IR."""

    def __init__(self) -> None:
        self.warnings: list[str] = []

    def parse(self, data: Any) -> Diagram:
        """Parse DOT text to an IR Diagram.

        Raises:
            ValueError: If the input is not a string or not valid DOT.
        """
        if not isinstance(data, str):
            raise ValueError('GraphViz parser expects a string input')

        self.warnings = []
        self._tokens = _tokenize(data)
        self._index = 0
        self._shapes: dict[str, Shape] = {}
        self._groups: dict[str, Group] = {}
        self._connections: list[Connection] = []
        self._graph_attrs: dict[str, str] = {}
        self._anonymous_clusters = 0
        self._cluster_ids: dict[str, str] = {}  # DOT subgraph name -> group id

        if self._peek().value.lower() == 'strict':
            self._next()
        keyword = self._next()
        if keyword.kind != 'id' or keyword.value.lower() not in {'graph', 'digraph'}:
            msg = f"Line {keyword.line}: not a DOT document (expected 'graph' or 'digraph')"
            raise ValueError(msg)
        self._directed = keyword.value.lower() == 'digraph'
        name = self._next().value if self._peek().kind == 'id' else None
        self._expect('{')
        self._parse_statements(_Scope(), is_root=True)
        self._separate_group_ids()

        rankdir = self._graph_attrs.get('rankdir', 'TB').upper()
        diagram = Diagram(
            id='graphviz-diagram',
            name=name or self._graph_attrs.get('label') or None,
            metadata={
                'direction': rankdir if rankdir in _RANKDIRS else 'TB',
                'explicit_shapes': True,
                'graphviz': {'graph_type': 'digraph' if self._directed else 'graph'},
            },
        )
        for shape in self._shapes.values():
            diagram.add_element(shape)
        for connection in self._connections:
            diagram.add_element(connection)
        for group in self._groups.values():
            diagram.add_element(group)
        layout_diagram(diagram, diagram.direction or 'TB')
        return diagram

    def _separate_group_ids(self) -> None:
        """Rename clusters that share a name with a node so neither hides the other."""
        renames = {
            group.id: f'{GROUP_ID_PREFIX}cluster_{group.source_shape_id}'
            for group in self._groups.values()
            if group.source_shape_id in self._shapes
        }
        if not renames:
            return
        for group in self._groups.values():
            group.children = [renames.get(child_id, child_id) for child_id in group.children]
            group.id = renames.get(group.id, group.id)
        for connection in self._connections:
            connection.from_id = renames.get(connection.from_id, connection.from_id)
            connection.to_id = renames.get(connection.to_id, connection.to_id)
        self._groups = {group.id: group for group in self._groups.values()}

    def _peek(self, offset: int = 0) -> _Token:
        return self._tokens[min(self._index + offset, len(self._tokens) - 1)]

    def _next(self) -> _Token:
        token = self._peek()
        self._index = min(self._index + 1, len(self._tokens) - 1)
        return token

    def _accept(self, value: str) -> bool:
        token = self._peek()
        if token.kind in {'punct', 'edge'} and token.value == value:
            self._next()
            return True
        return False

    def _expect(self, value: str) -> None:
        token = self._peek()
        if not self._accept(value):
            found = token.value or 'end of input'
            msg = f'Line {token.line}: expected {value!r} but found {found!r}'
            raise ValueError(msg)

    def _parse_statements(self, scope: _Scope, is_root: bool = False) -> None:
        while True:
            token = self._peek()
            if token.kind == 'eof':
                msg = f"Line {token.line}: unclosed '{{' in DOT input"
                raise ValueError(msg)
            if self._accept('}'):
                return
            if self._accept(';'):
                continue
            self._parse_statement(scope, is_root)

    def _parse_statement(self, scope: _Scope, is_root: bool) -> None:
        token = self._peek()
        following = self._peek(1)
        keyword = token.value.lower() if token.kind == 'id' and not token.quoted else ''

        if keyword in {'graph', 'node', 'edge'} and following.value == '[':
            self._next()
            attrs = self._parse_attr_lists()
            if keyword == 'node':
                scope.node_attrs.update(attrs)
            elif keyword == 'edge':
                scope.edge_attrs.update(attrs)
            else:
                self._apply_graph_attrs(attrs, scope, is_root)
            return

        if token.kind == 'id' and following.kind == 'punct' and following.value == '=':
            self._next()
            self._next()
            self._apply_graph_attrs({token.value.lower(): self._parse_id().value}, scope, is_root)
            return

        endpoints = [self._parse_endpoint(scope)]
        operators: list[str] = []
        while self._peek().kind == 'edge':
            operators.append(self._next().value)
            endpoints.append(self._parse_endpoint(scope))
        attrs = self._parse_attr_lists()

        if not operators:
            if endpoints[0].node_id is not None:
                self._update_node(endpoints[0].node_id, attrs)
            return
        for index, operator in enumerate(operators):
            for from_id in endpoints[index].ids:
                for to_id in endpoints[index + 1].ids:
                    self._add_connection(from_id, to_id, operator, {**scope.edge_attrs, **attrs})

    def _apply_graph_attrs(self, attrs: dict[str, str], scope: _Scope, is_root: bool) -> None:
        if is_root:
            self._graph_attrs.update(attrs)
        elif scope.group is not None and scope.owns_group and 'label' in attrs:
            scope.group.label = _unescape_label(attrs['label'])

    def _parse_id(self) -> _Token:
        token = self._next()
        if token.kind != 'id':
            found = token.value or 'end of input'
            msg = f'Line {token.line}: expected an identifier but found {found!r}'
            raise ValueError(msg)
        value = token.value
        while token.quoted and self._peek().value == '+' and self._peek(1).quoted:
            self._next()
            value += self._next().value
        token.value = value
        return token

    def _parse_endpoint(self, scope: _Scope) -> _Endpoint:
        token = self._peek()
        is_subgraph_keyword = token.kind == 'id' and not token.quoted and token.value.lower() == 'subgraph'
        if is_subgraph_keyword or (token.kind == 'punct' and token.value == '{'):
            return _Endpoint(None, self._parse_subgraph(scope))

        node_id = self._parse_id().value
        while self._accept(':'):
            self._parse_id()
        self._declare_node(node_id, scope)
        return _Endpoint(node_id, [node_id])

    def _parse_subgraph(self, scope: _Scope) -> list[str]:
        name: str | None = None
        if self._peek().value.lower() == 'subgraph' and not self._peek().quoted:
            self._next()
            if self._peek().kind == 'id':
                name = self._parse_id().value
        group: Group | None = None
        if name is not None and name.lower().startswith(_CLUSTER_PREFIX):
            group = self._declare_group(name, scope)
        child_scope = scope.child(group)
        self._expect('{')
        self._parse_statements(child_scope)
        scope.mentioned.extend(child_scope.mentioned)
        return list(dict.fromkeys(child_scope.mentioned))

    def _declare_group(self, name: str, scope: _Scope) -> Group:
        suffix = name[len(_CLUSTER_PREFIX) :].lstrip('_')
        if not suffix:
            self._anonymous_clusters += 1
            suffix = f'cluster_{self._anonymous_clusters}'
        group_id = GROUP_ID_PREFIX + re.sub(r'^group[-_]', '', suffix)
        self._cluster_ids[name] = group_id
        if (existing := self._groups.get(group_id)) is not None:
            return existing
        group = Group(
            id=group_id,
            position=Point(0.0, 0.0),
            size=Dimensions(1.0, 1.0),
            label=suffix,
        )
        self._groups[group_id] = group
        if scope.group is not None:
            scope.group.children.append(group.id)
        return group

    def _declare_node(self, node_id: str, scope: _Scope) -> None:
        scope.mentioned.append(node_id)
        if node_id in self._shapes:
            return
        shape = Shape(
            id=node_id,
            position=Point(0.0, 0.0),
            size=estimate_label_size(node_id),
            label=node_id,
            shape_type='ellipse',
            metadata={'graphviz': {}},
        )
        self._shapes[node_id] = shape
        if scope.group is not None:
            scope.group.children.append(node_id)
        self._apply_node_attrs(shape, scope.node_attrs)

    def _update_node(self, node_id: str, attrs: dict[str, str]) -> None:
        if attrs:
            self._apply_node_attrs(self._shapes[node_id], attrs)

    def _apply_node_attrs(self, shape: Shape, attrs: dict[str, str]) -> None:
        dot_attrs: dict[str, str] = shape.metadata['graphviz']
        dot_attrs.update(attrs)
        dot_shape = dot_attrs.get('shape', 'ellipse').lower()

        if 'label' in dot_attrs:
            shape.label = self._plain_label(dot_attrs['label'], dot_shape, shape.id)
            shape.size = estimate_label_size(shape.label)

        if dot_shape not in _DOT_SHAPE_TYPES:
            self.warnings.append(f"node '{shape.id}': unsupported shape '{dot_shape}' treated as a box")
        shape.shape_type = _DOT_SHAPE_TYPES.get(dot_shape, 'rectangle')
        styles = {part.strip().lower() for part in dot_attrs.get('style', '').split(',')}
        if shape.shape_type == 'rectangle' and 'rounded' in styles:
            shape.shape_type = 'rounded_rectangle'

        shape.style = Style(
            fill_color=dot_attrs.get('fillcolor') or (dot_attrs.get('color') if 'filled' in styles else None),
            stroke_color=dot_attrs.get('color'),
            stroke_width=_to_float(dot_attrs.get('penwidth')),
            stroke_style=_stroke_style(styles),
        )

        if dot_shape in _DOT_SHAPE_SEMANTICS:
            shape.semantic_type, shape.semantic_confidence = _DOT_SHAPE_SEMANTICS[dot_shape], _SHAPE_CONFIDENCE
        else:
            shape.semantic_type, shape.semantic_confidence = infer_semantic_type(
                shape_type=shape.shape_type,
                label=shape.label,
                size=None,
                style=shape.style,
            )

    def _plain_label(self, label: str, dot_shape: str, node_id: str) -> str:
        if '<' in label and re.search(r'</?\w+[^>]*>', label):
            self.warnings.append(f"node '{node_id}': HTML label flattened to plain text")
            return _strip_html(label)
        if dot_shape in {'record', 'mrecord'}:
            self.warnings.append(f"node '{node_id}': record label flattened to plain text")
            return _flatten_record(label)
        return _unescape_label(label).replace('\\N', node_id)

    def _add_connection(self, from_id: str, to_id: str, operator: str, attrs: dict[str, str]) -> None:
        # An edge clipped at a cluster border (lhead/ltail) links the cluster, not the node it is anchored to
        from_id = self._cluster_ids.get(attrs.get('ltail', ''), from_id)
        to_id = self._cluster_ids.get(attrs.get('lhead', ''), to_id)
        direction = attrs.get('dir', 'forward' if operator == '->' else 'none').lower()
        if direction == 'back':
            from_id, to_id = to_id, from_id
        connection_type = {'both': 'bidirectional', 'none': 'undirected'}.get(direction, 'directed')
        styles = {part.strip().lower() for part in attrs.get('style', '').split(',')}
        label = attrs.get('label') or attrs.get('xlabel') or ''
        self._connections.append(
            Connection(
                id=f'edge-{len(self._connections)}',
                position=Point(0.0, 0.0),
                size=Dimensions(1.0, 1.0),
                from_id=from_id,
                to_id=to_id,
                label=_strip_html(label) if re.search(r'</?\w+[^>]*>', label) else _unescape_label(label),
                connection_type=connection_type,
                style=Style(
                    stroke_color=attrs.get('color'),
                    stroke_width=_to_float(attrs.get('penwidth')),
                    stroke_style=_stroke_style(styles),
                ),
            )
        )

    def _parse_attr_lists(self) -> dict[str, str]:
        attrs: dict[str, str] = {}
        while self._accept('['):
            while not self._accept(']'):
                if self._accept(';') or self._accept(','):
                    continue
                key = self._parse_id().value.lower()
                if self._accept('='):
                    attrs[key] = self._parse_id().value
                else:
                    attrs[key] = 'true'
        return attrs


def _stroke_style(styles: set[str]) -> str:
    if 'dashed' in styles:
        return 'dashed'
    if 'dotted' in styles:
        return 'dotted'
    return 'solid'


def _to_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


__all__ = ['GraphVizParser', 'is_dot']
