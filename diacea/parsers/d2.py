"""D2 parser - converts D2 text to IR.

Supports the structural core of D2: shapes (`key: Label`), nested
containers (`key: Label { ... }` and dotted `a.b.c` paths), connections
(`->`, `<-`, `<->`, `--`, including chains and labels), and the `shape`,
`label`, `style.*`, and root `direction` keywords. Containers become groups.

Skipped with a warning: `vars`, `classes`, globs (`*`), connection
references (`(a -> b)[0]`), imports, and the fields of `sql_table`/`class`
shapes. D2 carries no coordinates, so a layered layout is synthesized along
`direction` (see `diacea.layout`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ..ir import (
    Connection,
    Diagram,
    Dimensions,
    Group,
    Parser,
    Point,
    Shape,
    Style,
)
from ..ir.semantic import infer_semantic_type
from ..layout import estimate_label_size, layout_diagram

_Path = tuple[str, ...]

_ARROW_RE = re.compile(r'(<->|<-|->|--)')

_D2_SHAPE_TYPES = {
    'c4-person': 'person',
    'callout': 'rectangle',
    'circle': 'circle',
    'class': 'rectangle',
    'cloud': 'cloud',
    'code': 'rectangle',
    'cylinder': 'cylinder',
    'diamond': 'diamond',
    'document': 'document',
    'hexagon': 'hexagon',
    'image': 'rectangle',
    'oval': 'ellipse',
    'package': 'rectangle',
    'page': 'document',
    'parallelogram': 'parallelogram',
    'person': 'person',
    'queue': 'queue',
    'rectangle': 'rectangle',
    'sql_table': 'rectangle',
    'square': 'rectangle',
    'step': 'rectangle',
    'stored_data': 'cylinder',
    'text': 'rectangle',
}

_FIELD_SHAPES = {'class', 'sql_table'}

# Keywords that configure the shape they appear in instead of declaring a child
_ATTRIBUTE_KEYS = frozenset(
    {
        'class',
        'constraint',
        'direction',
        'font-size',
        'grid-columns',
        'grid-gap',
        'grid-rows',
        'height',
        'horizontal-gap',
        'icon',
        'label',
        'left',
        'link',
        'near',
        'shape',
        'source-arrowhead',
        'style',
        'target-arrowhead',
        'tooltip',
        'top',
        'vertical-gap',
        'width',
    }
)

_SKIPPED_ROOT_KEYS = frozenset({'classes', 'vars'})

_DIRECTIONS = {'down': 'TB', 'left': 'RL', 'right': 'LR', 'up': 'BT'}

_KEY = r'[\w."\' -]+?'
_STATEMENT_HINT_RE = re.compile(
    rf'^\s*(?:{_KEY}(?:\s*(?:<->|<-|->|--)\s*{_KEY})+(?:\s*:.*)?|{_KEY}\s*:\s*\S.*|{_KEY}\s*(?::[^{{]*)?\{{)\s*(?:\{{)?\s*$',
)


def is_d2(content: str) -> bool:
    """Weak sniff for D2, which has no header: every line must look like a D2 statement.

    Only used as a last resort when neither the content signature nor the
    file extension identifies another format.
    """
    lines = [line for line in content.splitlines() if line.strip() and not line.strip().startswith('#')]
    if not lines:
        return False
    statements = [line for line in lines if line.strip() != '}']
    has_connection = any(_ARROW_RE.search(line) for line in statements)
    has_block = any(line.rstrip().endswith('{') for line in statements)
    return (has_connection or has_block) and all(_STATEMENT_HINT_RE.match(line) for line in statements)


@dataclass
class _Node:
    path: _Path
    label: str | None = None
    shape: str = 'rectangle'
    style: dict[str, str] = field(default_factory=dict)
    children: list[_Path] = field(default_factory=list)


@dataclass
class _Edge:
    source: _Path
    target: _Path
    arrow: str
    label: str = ''
    style: dict[str, str] = field(default_factory=dict)


@dataclass
class _Statement:
    head: str
    value: str | None
    body: str | None
    line: int
    body_line: int = 0


def _strip_block_comments(text: str) -> str:
    return re.sub(
        r'^[ \t]*""".*?"""[ \t]*$',
        lambda match: '\n' * match.group(0).count('\n'),
        text,
        flags=re.DOTALL | re.MULTILINE,
    )


# A quote character only opens a string at the start of a key or value ("User's" is plain text)
_QUOTE_OPENERS = ' \t\n:.{;(><-'


def _opaque_span_end(text: str, index: int) -> int | None:
    """End index of the quoted string, block string, or comment starting at `index`, if any."""
    char = text[index]
    if char in '"\'' and (index == 0 or text[index - 1] in _QUOTE_OPENERS):
        return _closing_quote(text, index)
    if char == '#' and (index == 0 or text[index - 1].isspace()):
        newline = text.find('\n', index)
        return (len(text) if newline == -1 else newline) - 1
    if char == '|' and text[:index].rstrip(' \t').endswith(':'):
        return _closing_block_string(text, index)
    return None


def _split_statements(text: str, first_line: int) -> list[_Statement]:
    """Split a block into statements, keeping each statement's `{ ... }` body intact."""
    statements: list[_Statement] = []
    line = first_line
    start_line = line
    head: list[str] = []
    value: list[str] | None = None
    body: str | None = None
    index = 0

    body_line = line

    def flush() -> None:
        nonlocal head, value, body
        head_text = ''.join(head).strip()
        if head_text or body is not None:
            value_text = ''.join(value).strip() if value is not None else None
            statements.append(_Statement(head_text, value_text, body, start_line, body_line))
        head, value, body = [], None, None

    while index < len(text):
        char = text[index]
        target = head if value is None else value
        if not ''.join(head).strip() and value is None and body is None:
            start_line = line
        if (end := _opaque_span_end(text, index)) is not None:
            if char != '#':
                target.append(text[index : end + 1])
            line += text.count('\n', index, end + 1)
            index = end + 1
            continue
        if char == ':' and value is None:
            value = []
        elif char == '{':
            end = _closing_brace(text, index, line)
            body = text[index + 1 : end]
            body_line = line
            line += text.count('\n', index, end + 1)
            index = end + 1
            flush()
            continue
        elif char in '\n;':
            flush()
            if char == '\n':
                line += 1
        else:
            target.append(char)
        index += 1
    flush()
    return statements


def _closing_quote(text: str, start: int) -> int:
    quote = text[start]
    index = start + 1
    while index < len(text):
        if text[index] == '\\':
            index += 2
            continue
        if text[index] == quote:
            return index
        index += 1
    return len(text) - 1


def _closing_block_string(text: str, start: int) -> int:
    opener = re.match(r'\|+`*', text[start:])
    fence = opener.group(0) if opener else '|'
    closer = fence[::-1]
    end = text.find(closer, start + len(fence))
    return len(text) - 1 if end == -1 else end + len(closer) - 1


def _closing_brace(text: str, start: int, line: int) -> int:
    depth = 0
    index = start
    while index < len(text):
        char = text[index]
        if (end := _opaque_span_end(text, index)) is not None:
            index = end
        elif char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                return index
        index += 1
    msg = f"Line {line}: unclosed '{{' in D2 input"
    raise ValueError(msg)


def _split_outside_quotes(text: str, pattern: re.Pattern[str]) -> list[str]:
    """Split on a pattern, ignoring matches inside quotes; separators are kept at odd indexes."""
    parts: list[str] = []
    current: list[str] = []
    index = 0
    while index < len(text):
        if text[index] in '"\'' and (index == 0 or text[index - 1] in _QUOTE_OPENERS):
            end = _closing_quote(text, index)
            current.append(text[index : end + 1])
            index = end + 1
            continue
        if match := pattern.match(text, index):
            parts.extend((''.join(current), match.group(0)))
            current = []
            index = match.end()
            continue
        current.append(text[index])
        index += 1
    parts.append(''.join(current))
    return parts


_DOT_RE = re.compile(r'\.')


_QUOTED_ESCAPE_RE = re.compile(r'\\([\\"\'$n])')
_UNQUOTED_ESCAPE_RE = re.compile(r'\\([\\n])')


def _unquote(text: str, *, newlines: bool = False) -> str:
    text = text.strip()
    quoted = len(text) >= 2 and text[0] == text[-1] and text[0] in '"\''
    pattern = _QUOTED_ESCAPE_RE if quoted else _UNQUOTED_ESCAPE_RE

    def resolve(match: re.Match[str]) -> str:
        char = match.group(1)
        if char == 'n':
            return '\n' if newlines else match.group(0)
        return char

    return pattern.sub(resolve, text[1:-1] if quoted else text)


def _parse_label(value: str) -> str:
    value = value.strip()
    if value.startswith('|'):
        opener = re.match(r'\|+`*\w*', value)
        fence = re.match(r'\|+`*', value)
        if opener and fence:
            inner = value[len(opener.group(0)) : len(value) - len(fence.group(0))]
            lines = [line.strip().lstrip('#').strip() for line in inner.strip().splitlines()]
            return '\n'.join(line for line in lines if line)
    return _unquote(value, newlines=True)


def _parse_key(text: str) -> _Path:
    return tuple(_unquote(part) for part in _split_outside_quotes(text.strip(), _DOT_RE)[0::2] if part.strip())


class D2Parser(Parser):
    """Parse D2 text into the IR."""

    def __init__(self) -> None:
        self.warnings: list[str] = []

    def parse(self, data: Any) -> Diagram:
        """Parse D2 text to an IR Diagram.

        Raises:
            ValueError: If the input is not a string or has unbalanced braces.
        """
        if not isinstance(data, str):
            raise ValueError('D2 parser expects a string input')

        self.warnings = []
        self._nodes: dict[_Path, _Node] = {}
        self._edges: list[_Edge] = []
        self._direction: str | None = None
        self._title: str | None = None

        self._parse_block(_strip_block_comments(data), (), first_line=1)
        return self._build_diagram()

    def _parse_block(self, text: str, container: _Path, first_line: int) -> None:
        for statement in _split_statements(text, first_line):
            self._parse_statement(statement, container)

    def _parse_statement(self, statement: _Statement, container: _Path) -> None:
        head = statement.head
        if not head:
            return
        if head.startswith(('...', '@')) or (statement.value or '').startswith(('@', '...@')):
            self.warnings.append(f'line {statement.line}: skipped import: {head}')
            return
        if '*' in head:
            self.warnings.append(f'line {statement.line}: skipped glob: {head}')
            return
        if head.startswith('('):
            self.warnings.append(f'line {statement.line}: skipped connection reference: {head}')
            return

        segments = _split_outside_quotes(head, _ARROW_RE)
        if len(segments) > 1:
            self._parse_connections(segments, statement, container)
            return

        key = _parse_key(head)
        if not key:
            return
        if not container and key[0] in _SKIPPED_ROOT_KEYS:
            self.warnings.append(f"line {statement.line}: skipped '{key[0]}' block")
            return
        if not container and key == ('direction',):
            self._direction = _DIRECTIONS.get((statement.value or '').strip().lower())
            return
        if not container and key == ('title',):
            self._title = _parse_label(statement.value or '') or None
            return

        attribute_index = next((index for index, part in enumerate(key) if part in _ATTRIBUTE_KEYS), None)
        if attribute_index is not None:
            owner = container + key[:attribute_index]
            if owner:
                self._apply_attribute(owner, key[attribute_index:], statement)
            return

        path = container + key
        node = self._declare(path)
        if statement.value:
            node.label = _parse_label(statement.value)
        if statement.body is not None:
            self._parse_block(statement.body, path, statement.body_line)

    def _apply_attribute(self, owner: _Path, key: _Path, statement: _Statement) -> None:
        node = self._declare(owner)
        value = _unquote(statement.value or '')
        match key:
            case ('shape',):
                node.shape = value.lower()
            case ('label',):
                node.label = _parse_label(statement.value or '')
            case ('style',) if statement.body is not None:
                for nested in _split_statements(statement.body, statement.line):
                    node.style[nested.head.strip()] = _unquote(nested.value or '')
            case ('style', name):
                node.style[name] = value
            case _:
                pass

    def _parse_connections(self, segments: list[str], statement: _Statement, container: _Path) -> None:
        endpoints = [self._resolve(_parse_key(segment), container) for segment in segments[0::2]]
        if any(endpoint is None for endpoint in endpoints):
            self.warnings.append(f'line {statement.line}: skipped malformed connection: {statement.head}')
            return
        label = _parse_label(statement.value) if statement.value else ''
        style: dict[str, str] = {}
        if statement.body is not None:
            for nested in _split_statements(statement.body, statement.line):
                key = _parse_key(nested.head)
                if key == ('style',) and nested.body is not None:
                    for entry in _split_statements(nested.body, nested.line):
                        style[entry.head.strip()] = _unquote(entry.value or '')
                elif len(key) == 2 and key[0] == 'style':
                    style[key[1]] = _unquote(nested.value or '')
                elif key == ('label',):
                    label = _parse_label(nested.value or '')
        for index, arrow in enumerate(segments[1::2]):
            source, target = endpoints[index], endpoints[index + 1]
            if source is None or target is None:
                continue
            self._declare(source)
            self._declare(target)
            self._edges.append(_Edge(source, target, arrow, label, dict(style)))

    def _resolve(self, key: _Path, container: _Path) -> _Path | None:
        """Resolve a connection endpoint relative to its container (`_` is the parent)."""
        scope = container
        while key and key[0] == '_':
            scope = scope[:-1]
            key = key[1:]
        return scope + key if key else None

    def _declare(self, path: _Path) -> _Node:
        for depth in range(1, len(path) + 1):
            prefix = path[:depth]
            if prefix not in self._nodes:
                self._nodes[prefix] = _Node(prefix)
                if depth > 1:
                    self._nodes[prefix[:-1]].children.append(prefix)
        return self._nodes[path]

    def _build_diagram(self) -> Diagram:
        ids = self._assign_ids()
        diagram = Diagram(
            id='d2-diagram',
            name=self._title,
            metadata={'explicit_shapes': True},
        )
        if self._direction is not None:
            diagram.metadata['direction'] = self._direction

        groups: list[Group] = []
        for path, node in self._nodes.items():
            label = node.label if node.label is not None else path[-1]
            if node.shape not in _D2_SHAPE_TYPES:
                self.warnings.append(f"'{'.'.join(path)}': unsupported shape '{node.shape}' treated as a rectangle")
            if node.children and node.shape in _FIELD_SHAPES:
                self.warnings.append(f"'{'.'.join(path)}': fields of {node.shape} shape dropped")
            if node.children and node.shape not in _FIELD_SHAPES:
                groups.append(
                    Group(
                        id=ids[path],
                        position=Point(0.0, 0.0),
                        size=Dimensions(1.0, 1.0),
                        label=label,
                        children=[ids[child] for child in node.children],
                        style=_to_style(node.style),
                    )
                )
                continue
            if len(path) > 1 and self._nodes[path[:-1]].shape in _FIELD_SHAPES:
                continue
            shape = Shape(
                id=ids[path],
                position=Point(0.0, 0.0),
                size=estimate_label_size(label),
                label=label,
                shape_type=_D2_SHAPE_TYPES.get(node.shape, 'rectangle'),
                style=_to_style(node.style),
            )
            shape.semantic_type, shape.semantic_confidence = infer_semantic_type(
                shape_type=shape.shape_type,
                label=shape.label,
                size=None,
                style=shape.style,
            )
            diagram.add_element(shape)

        for index, edge in enumerate(self._edges):
            source, target = (edge.target, edge.source) if edge.arrow == '<-' else (edge.source, edge.target)
            if source not in ids or target not in ids:
                continue
            connection_type = {'<->': 'bidirectional', '--': 'undirected'}.get(edge.arrow, 'directed')
            diagram.add_element(
                Connection(
                    id=f'edge-{index}',
                    position=Point(0.0, 0.0),
                    size=Dimensions(1.0, 1.0),
                    from_id=ids[source],
                    to_id=ids[target],
                    label=edge.label,
                    connection_type=connection_type,
                    style=_to_style(edge.style),
                )
            )
        for group in groups:
            diagram.add_element(group)

        layout_diagram(diagram, diagram.direction or 'TB')
        return diagram

    def _assign_ids(self) -> dict[_Path, str]:
        """Use the last path segment as the id, falling back to the full path on clashes."""
        counts: dict[str, int] = {}
        for path in self._nodes:
            counts[path[-1]] = counts.get(path[-1], 0) + 1
        return {path: path[-1] if counts[path[-1]] == 1 else '_'.join(path) for path in self._nodes}


def _to_style(style: dict[str, str]) -> Style:
    dash = _to_float(style.get('stroke-dash'))
    return Style(
        fill_color=style.get('fill') or None,
        stroke_color=style.get('stroke') or None,
        stroke_width=_to_float(style.get('stroke-width')),
        stroke_style='dashed' if dash else 'solid',
        opacity=_to_float(style.get('opacity')),
        font_size=_to_float(style.get('font-size')),
    )


def _to_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


__all__ = ['D2Parser', 'is_d2']
