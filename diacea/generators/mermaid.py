"""Mermaid generator - converts IR to Mermaid diagram formats.

Supports flowchart, C4, and sequence diagrams with auto-detection.

Design decisions (from Phase 2 open questions):
1. Default diagram type: Auto-detect from structure, fallback to flowchart
2. Style preservation: Basic colors only (fill, stroke)
3. Subgraph depth: Max 3 levels to avoid visual complexity
"""

from __future__ import annotations

import re
import warnings

from ..ir import Connection, Diagram, Generator, Group, SemanticType, Shape
from ._text import Containers, canonical_shape, readable_id, sanitize_alnum_id, top_level_groups, visual_semantic

_C4_BOUNDARY_KEYWORDS: dict[str, str] = {
    SemanticType.COMPONENT: 'Component',
    SemanticType.CONTAINER: 'Container',
    SemanticType.DATABASE: 'ContainerDb',
    SemanticType.PERSON: 'Person',
    SemanticType.QUEUE: 'ContainerQueue',
    SemanticType.STORAGE: 'ContainerDb',
    SemanticType.SYSTEM: 'System',
}

_C4_TOP_LEVEL_KEYWORDS: dict[str, str] = {
    SemanticType.COMPONENT: 'Component',
    SemanticType.CONTAINER: 'Container',
    SemanticType.DATABASE: 'SystemDb',
    SemanticType.PERSON: 'Person',
    SemanticType.QUEUE: 'SystemQueue',
    SemanticType.STORAGE: 'SystemDb',
    SemanticType.SYSTEM: 'System',
}

_LABEL_CHARS_REQUIRING_QUOTES = frozenset('"()[]{}|/\\<>;&#@`~^=%$')

_FLOWCHART_BRACKETS: dict[str, tuple[str, str]] = {
    'circle': ('((', '))'),
    'cylinder': ('[(', ')]'),
    'diamond': ('{', '}'),
    'ellipse': ('([', '])'),
    'hexagon': ('{{', '}}'),
    'parallelogram': ('[/', '/]'),
    'person': ('([', '])'),
    'rectangle': ('[', ']'),
    'rounded_rectangle': ('(', ')'),
    'stadium': ('([', '])'),
    'subroutine': ('[[', ']]'),
    'trapezoid': ('[/', '\\]'),
}

_FLOWCHART_SEMANTIC_BRACKETS: dict[str, tuple[str, str]] = {
    SemanticType.DATABASE: ('[(', ')]'),
    SemanticType.DECISION: ('{', '}'),
    SemanticType.PERSON: ('([', '])'),
    SemanticType.START_END: ('([', '])'),
}

_THICK_STROKE_WIDTH = 3.0

# Text that the flowchart grammar would read as the start of a link
_ARROW_LIKE_RE = re.compile(r'--|==|-\.|\.-|^\s|\s$')

_FLOWCHART_DIRECTIONS = {'BT': 'BT', 'LR': 'LR', 'RL': 'RL', 'TB': 'TD'}


class MermaidGenerator(Generator):
    """Generate Mermaid diagrams from IR with auto-detection."""

    def __init__(self, diagram_type: str | None = None) -> None:
        """Initialize generator.

        Args:
            diagram_type: Force specific type ('flowchart', 'c4', 'sequence')
                         or None for auto-detection
        """
        self.diagram_type = diagram_type
        self.detected_type: str | None = None
        self.max_subgraph_depth = 3

    def generate(self, diagram: Diagram) -> str:
        """Generate Mermaid diagram from IR.

        Args:
            diagram: IR Diagram object

        Returns:
            Mermaid diagram string
        """
        # Auto-detect diagram type if not specified
        diagram_type = self.diagram_type or self._detect_diagram_type(diagram)
        self.detected_type = diagram_type
        self._diagram = diagram

        if diagram_type == 'c4':
            return self._generate_c4(diagram)
        if diagram_type == 'sequence':
            return self._generate_sequence(diagram)
        # flowchart (default)  # noqa: ERA001
        return self._generate_flowchart(diagram)

    def _detect_diagram_type(self, diagram: Diagram) -> str:
        """Auto-detect the best Mermaid diagram type.

        The source's own diagram type wins: a parser-provided
        ``metadata["mermaid"]["diagram_type"]`` or the C4-PlantUML flag.
        Otherwise a drawing whose shapes were recognized as C4 elements
        (person, system, container, component) becomes a C4 diagram, and
        everything else a flowchart. Sequence diagrams are only produced on
        request or from a sequence source, since a drawn chain of boxes is
        far more often a pipeline than a message exchange.
        """
        source_type = diagram.metadata.get('mermaid', {}).get('diagram_type')
        if source_type in {'c4', 'flowchart', 'sequence'}:
            return source_type
        if diagram.metadata.get('c4_plantuml'):
            return 'c4'
        if diagram.has_explicit_shapes:
            return 'flowchart'

        c4_types = {
            SemanticType.PERSON,
            SemanticType.SYSTEM,
            SemanticType.CONTAINER,
            SemanticType.COMPONENT,
        }
        if {shape.semantic_type for shape in diagram.get_shapes()} & c4_types:
            return 'c4'
        return 'flowchart'

    def _generate_flowchart(self, diagram: Diagram) -> str:
        """Generate Mermaid flowchart."""
        lines = [f'flowchart {_FLOWCHART_DIRECTIONS.get(diagram.direction or "", "LR")}']

        shapes = diagram.get_shapes()
        connections = diagram.get_connections()
        groups = diagram.get_groups()

        group_source_ids = {g.source_shape_id for g in groups}
        child_ids = {child_id for g in groups for child_id in g.children}
        top_level_shapes = [s for s in shapes if s.id not in child_ids and s.id not in group_source_ids]

        lines.extend(self._format_flowchart_node(shape) for shape in top_level_shapes)

        shapes_by_id = {s.id: s for s in shapes}
        groups_by_id = {g.id: g for g in groups}
        for group in top_level_groups(groups):
            subgraph_lines = self._generate_subgraph(group, shapes_by_id, groups_by_id, depth=1)
            lines.extend(subgraph_lines)

        # Generate connections
        self._containers = Containers(diagram)
        for conn in connections:
            if self._containers.links_container_to_own_content(conn):
                warnings.warn(
                    f'Dropping connection between container and its own content: {conn.from_id} -> {conn.to_id}',
                    stacklevel=2,
                )
                continue
            lines.append(self._format_flowchart_connection(conn))

        # Add styling (basic colors)
        style_lines = self._generate_flowchart_styles(
            [*shapes, *(g for g in groups if g.source_shape_id not in shapes_by_id)]
        )
        if style_lines:
            lines.append('')
            lines.extend(style_lines)

        return '\n'.join(lines)

    def _format_flowchart_node(self, shape: Shape) -> str:
        """Format a Mermaid flowchart node."""
        node_id = self._sanitize_id(shape.id)
        label = self._format_bracket_label(shape.label or readable_id(node_id))
        brackets = self._get_node_brackets(shape)
        return f'    {node_id}{brackets[0]}{label}{brackets[1]}'

    def _format_bracket_label(self, label: str) -> str:
        escaped = self._escape_label(label)
        if _LABEL_CHARS_REQUIRING_QUOTES & set(label) or _ARROW_LIKE_RE.search(label) or not label.strip():
            return f'"{escaped}"'
        return escaped

    def _get_node_brackets(self, shape: Shape) -> tuple[str, str]:
        """Get Mermaid node brackets based on shape type.

        Returns tuple of (opening, closing) brackets.
        """
        semantic = visual_semantic(shape, self._diagram)
        if semantic in _FLOWCHART_SEMANTIC_BRACKETS:
            return _FLOWCHART_SEMANTIC_BRACKETS[semantic]
        return _FLOWCHART_BRACKETS.get(canonical_shape(shape.shape_type), ('[', ']'))

    def _format_flowchart_connection(self, conn: Connection) -> str:
        """Format a Mermaid flowchart connection."""
        from_group = self._containers.group_for(conn.from_id)
        to_group = self._containers.group_for(conn.to_id)
        from_id = self._sanitize_id(from_group.id if from_group else conn.from_id)
        to_id = self._sanitize_id(to_group.id if to_group else conn.to_id)

        # Determine arrow style
        dashed = conn.style.stroke_style in {'dashed', 'dotted'}
        thick = bool(conn.style.stroke_width and conn.style.stroke_width >= _THICK_STROKE_WIDTH)
        if conn.connection_type == 'bidirectional':
            arrow = '<-.->' if dashed else '<-->'
        elif conn.connection_type == 'undirected':
            arrow = '-.-' if dashed else '---'
        elif dashed:
            arrow = '-.->'
        elif thick:
            arrow = '==>'
        else:
            arrow = '-->'

        if conn.label:
            label = self._escape_pipe_label(conn.label)
            return f'    {from_id} {arrow}|{label}| {to_id}'
        return f'    {from_id} {arrow} {to_id}'

    def _generate_subgraph(
        self,
        group: Group,
        shapes_by_id: dict[str, Shape],
        groups_by_id: dict[str, Group],
        depth: int,
    ) -> list[str]:
        """Generate Mermaid subgraph for a group, recursing into child groups."""
        if depth > self.max_subgraph_depth:
            warnings.warn(
                f'group {group.id!r} exceeds max subgraph depth {self.max_subgraph_depth}; truncating',
                stacklevel=2,
            )
            return []

        lines = []
        indent = '    ' * depth
        subgraph_id = self._sanitize_id(group.id)
        label = self._format_bracket_label(group.label or readable_id(subgraph_id))
        lines.append(f'{indent}subgraph {subgraph_id}[{label}]')

        for child_id in group.children:
            child_group = groups_by_id.get(child_id)
            if child_group:
                lines.extend(self._generate_subgraph(child_group, shapes_by_id, groups_by_id, depth + 1))
                continue
            child_shape = shapes_by_id.get(child_id)
            if child_shape:
                node_line = self._format_flowchart_node(child_shape)
                lines.append(indent + node_line)

        lines.append(f'{indent}end')
        return lines

    def _generate_flowchart_styles(self, shapes: list[Shape | Group]) -> list[str]:
        """Generate Mermaid style definitions for shapes."""
        lines = []

        for shape in shapes:
            if not shape.style.fill_color and not shape.style.stroke_color:
                continue  # No custom styling

            # A container shape is declared as a subgraph, under its group id
            group = self._containers.group_for(shape.id)
            node_id = self._sanitize_id(group.id if group else shape.id)
            style_parts = []

            if shape.style.fill_color:
                style_parts.append(f'fill:{shape.style.fill_color}')

            if shape.style.stroke_color:
                style_parts.append(f'stroke:{shape.style.stroke_color}')

            if shape.style.stroke_style == 'dashed':
                style_parts.append('stroke-dasharray:5 5')

            if style_parts:
                style_str = ','.join(style_parts)
                lines.append(f'    style {node_id} {style_str}')

        return lines

    def _generate_c4(self, diagram: Diagram) -> str:
        """Generate Mermaid C4 diagram."""
        lines = ['C4Context']  # Start with Context level
        lines.append('    title ' + (diagram.name or 'Architecture Diagram'))

        shapes = diagram.get_shapes()
        connections = diagram.get_connections()
        groups = diagram.get_groups()

        group_source_ids = {g.source_shape_id for g in groups}
        child_ids = {cid for g in groups for cid in g.children}
        shapes_by_id = {s.id: s for s in shapes}
        groups_by_id = {g.id: g for g in groups}
        declared_ids: set[str] = set()
        group_representatives: dict[str, str] = {}

        for shape in shapes:
            if shape.id in child_ids or shape.id in group_source_ids:
                continue
            if shape.id in declared_ids:
                continue
            lines.append(self._format_c4_element(shape, in_boundary=False))
            declared_ids.add(shape.id)

        for group in top_level_groups(groups):
            lines.extend(
                self._generate_c4_boundary(group, shapes_by_id, groups_by_id, declared_ids, group_representatives)
            )

        for shape in shapes:
            if shape.id in declared_ids or shape.id in group_source_ids:
                continue
            lines.append(self._format_c4_element(shape, in_boundary=False))
            declared_ids.add(shape.id)

        source_to_group = {g.source_shape_id: g.id for g in groups} | {g.id: g.id for g in groups}
        for conn in connections:
            rel_line = self._format_c4_rel(conn, declared_ids, source_to_group, group_representatives)
            if rel_line:
                lines.append(rel_line)

        return '\n'.join(lines)

    def _generate_c4_boundary(
        self,
        group: Group,
        shapes_by_id: dict[str, Shape],
        groups_by_id: dict[str, Group],
        declared_ids: set[str],
        group_representatives: dict[str, str],
    ) -> list[str]:
        """Generate a C4 boundary, recursing into child groups and skipping empty groups."""
        body: list[str] = []
        for child_id in group.children:
            child_group = groups_by_id.get(child_id)
            if child_group:
                body.extend(
                    self._generate_c4_boundary(
                        child_group, shapes_by_id, groups_by_id, declared_ids, group_representatives
                    )
                )
                if child_group.id in group_representatives:
                    group_representatives.setdefault(group.id, group_representatives[child_group.id])
                continue
            child_shape = shapes_by_id.get(child_id)
            if child_shape and child_shape.id not in declared_ids:
                body.append(self._format_c4_element(child_shape, in_boundary=True))
                declared_ids.add(child_shape.id)
                group_representatives.setdefault(group.id, child_shape.id)

        if not body:
            warnings.warn(f'group {group.id!r} has no resolvable children; skipping empty C4 boundary', stacklevel=2)
            return []

        label = self._escape_quoted_label(group.label or readable_id(group.source_shape_id))
        boundary_id = self._sanitize_id(group.id)
        nested = [f'    {line}' for line in body]
        return [f'    Boundary({boundary_id}, "{label}") {{', *nested, '    }']

    def _format_c4_rel(
        self,
        conn: Connection,
        declared_ids: set[str],
        source_to_group: dict[str, str],
        group_representatives: dict[str, str],
    ) -> str | None:
        """Format a C4 Rel, remapping endpoints suppressed as group source shapes.

        Mermaid C4 rejects boundary ids as Rel endpoints, so a suppressed endpoint
        maps to a declared element inside that group's boundary.
        """
        endpoints = []
        for endpoint_id in (conn.from_id, conn.to_id):
            resolved: str | None = endpoint_id
            if endpoint_id not in declared_ids:
                group_id = source_to_group.get(endpoint_id)
                resolved = group_representatives.get(group_id) if group_id else None
            if resolved is None:
                warnings.warn(f'dropping C4 Rel with unresolvable endpoint {endpoint_id!r}', stacklevel=2)
                return None
            if resolved != endpoint_id:
                warnings.warn(
                    f'Re-pointing C4 Rel from boundary {endpoint_id!r} to {resolved!r} inside it: '
                    'Mermaid C4 cannot link a boundary',
                    stacklevel=2,
                )
            endpoints.append(self._sanitize_id(resolved))

        macro = 'BiRel' if conn.connection_type == 'bidirectional' else 'Rel'
        label = self._escape_quoted_label(conn.label or ' ')
        return f'    {macro}({endpoints[0]}, {endpoints[1]}, "{label}")'

    def _format_c4_element(self, shape: Shape, in_boundary: bool) -> str:
        keywords = _C4_BOUNDARY_KEYWORDS if in_boundary else _C4_TOP_LEVEL_KEYWORDS
        default = 'Container' if in_boundary else 'System'
        keyword = keywords.get(shape.semantic_type or '', default)
        node_id = self._sanitize_id(shape.id)
        label = self._escape_quoted_label(shape.label or readable_id(node_id))
        return f'    {keyword}({node_id}, "{label}")'

    def _generate_sequence(self, diagram: Diagram) -> str:
        """Generate Mermaid sequence diagram."""
        lines = ['sequenceDiagram']

        shapes = diagram.get_shapes()
        connections = diagram.get_connections()

        for shape in shapes:
            participant_id = self._sanitize_id(shape.id)
            label = self._escape_label(shape.label or readable_id(participant_id))
            lines.append(f'    participant {participant_id} as {label}')

        for conn in connections:
            from_id = self._sanitize_id(conn.from_id)
            to_id = self._sanitize_id(conn.to_id)

            if conn.connection_type == 'bidirectional':
                arrow = '->>'
            elif conn.style.stroke_style == 'dashed':
                arrow = '-->'
            else:
                arrow = '->>'

            label = self._escape_label(conn.label or '')
            lines.append(f'    {from_id}{arrow}{to_id}: {label}')

        return '\n'.join(lines)

    _sanitize_id = staticmethod(sanitize_alnum_id)

    def _escape_label(self, label: str) -> str:
        """Escape label for Mermaid flowchart node syntax."""
        escaped = label.replace('&', '&amp;')
        escaped = escaped.replace('"', '#quot;')
        escaped = escaped.replace('<', '&lt;')
        escaped = escaped.replace('>', '&gt;')
        return escaped.replace('\n', '<br/>')

    def _escape_quoted_label(self, label: str) -> str:
        """Escape label for Mermaid quoted string contexts (C4, sequence)."""
        escaped = label.replace('\\', '\\\\')
        escaped = escaped.replace('"', '\\"')
        escaped = escaped.replace('&', '&amp;')
        escaped = escaped.replace('<', '&lt;')
        escaped = escaped.replace('>', '&gt;')
        return escaped.replace('\n', '<br/>')

    def _escape_pipe_label(self, label: str) -> str:
        """Escape label for Mermaid pipe-delimited connection labels."""
        escaped = label.replace('&', '&amp;')
        escaped = escaped.replace('|', '&#124;')
        escaped = escaped.replace('"', '#quot;')
        escaped = escaped.replace('<', '&lt;')
        escaped = escaped.replace('>', '&gt;')
        escaped = escaped.replace('\n', '<br/>')
        if _LABEL_CHARS_REQUIRING_QUOTES & set(label) or _ARROW_LIKE_RE.search(label):
            return f'"{escaped}"'
        return escaped
