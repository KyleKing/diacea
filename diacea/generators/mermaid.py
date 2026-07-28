"""Mermaid generator - converts IR to Mermaid diagram formats.

Supports flowchart, C4, and sequence diagrams with auto-detection.

Design decisions (from Phase 2 open questions):
1. Default diagram type: Auto-detect from structure, fallback to flowchart
2. Style preservation: Basic colors only (fill, stroke)
3. Subgraph depth: Max 3 levels to avoid visual complexity
"""

from __future__ import annotations

import warnings

from ..ir import Connection, Diagram, Generator, Group, SemanticType, Shape
from ._text import sanitize_alnum_id, top_level_groups

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

_LABEL_CHARS_REQUIRING_QUOTES = frozenset('"()[]{}|')


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

        if diagram_type == 'c4':
            return self._generate_c4(diagram)
        if diagram_type == 'sequence':
            return self._generate_sequence(diagram)
        # flowchart (default)  # noqa: ERA001
        return self._generate_flowchart(diagram)

    def _detect_diagram_type(self, diagram: Diagram) -> str:
        """Auto-detect best Mermaid diagram type.

        Detection logic:
        - If has Person/System/Container semantic types → C4
        - If connections form sequential flow → Sequence
        - Default → Flowchart

        A parser-provided ``metadata["mermaid"]["diagram_type"]`` wins over
        the heuristics.
        """
        source_type = diagram.metadata.get('mermaid', {}).get('diagram_type')
        if source_type in {'c4', 'flowchart', 'sequence'}:
            return source_type

        shapes = diagram.get_shapes()
        connections = diagram.get_connections()

        # Check for C4 semantic types
        c4_types = {
            SemanticType.PERSON,
            SemanticType.SYSTEM,
            SemanticType.CONTAINER,
            SemanticType.COMPONENT,
        }

        semantic_types = {s.semantic_type for s in shapes if s.semantic_type}

        if semantic_types & c4_types:  # Intersection
            return 'c4'

        # Check for sequential pattern (each shape has at most one out connection)
        # This is a simple heuristic - could be improved
        out_counts: dict[str, int] = {}
        for conn in connections:
            out_counts[conn.from_id] = out_counts.get(conn.from_id, 0) + 1

        if connections and all(count <= 1 for count in out_counts.values()):
            return 'sequence'

        # Default to flowchart
        return 'flowchart'

    def _generate_flowchart(self, diagram: Diagram) -> str:
        """Generate Mermaid flowchart."""
        lines = ['flowchart LR']  # Left-to-right by default

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
        lines.extend(self._format_flowchart_connection(conn) for conn in connections)

        # Add styling (basic colors)
        style_lines = self._generate_flowchart_styles(shapes)
        if style_lines:
            lines.append('')
            lines.extend(style_lines)

        return '\n'.join(lines)

    def _format_flowchart_node(self, shape: Shape) -> str:
        """Format a Mermaid flowchart node."""
        node_id = self._sanitize_id(shape.id)
        label = self._format_bracket_label(shape.label or node_id)
        brackets = self._get_node_brackets(shape)
        return f'    {node_id}{brackets[0]}{label}{brackets[1]}'

    def _format_bracket_label(self, label: str) -> str:
        escaped = self._escape_label(label)
        if _LABEL_CHARS_REQUIRING_QUOTES & set(label):
            return f'"{escaped}"'
        return escaped

    def _get_node_brackets(self, shape: Shape) -> tuple[str, str]:
        """Get Mermaid node brackets based on shape type.

        Returns tuple of (opening, closing) brackets.
        """
        # Check semantic type first
        if shape.semantic_type:
            semantic = shape.semantic_type
            if semantic == SemanticType.DECISION:
                return ('{', '}')  # Diamond
            if semantic == SemanticType.DATABASE:
                return ('[(', ')]')  # Cylindrical
            if semantic == SemanticType.PERSON:
                return ('([', '])')  # Stadium/rounded
            if semantic == SemanticType.START_END:
                return ('([', '])')  # Stadium

        # Fall back to geometric shape
        shape_map = {
            'rectangle': ('[', ']'),
            'ellipse': ('([', '])'),
            'diamond': ('{', '}'),
            'circle': ('((', '))'),
        }

        return shape_map.get(shape.shape_type, ('[', ']'))  # Default rectangle

    def _format_flowchart_connection(self, conn: Connection) -> str:
        """Format a Mermaid flowchart connection."""
        from_id = self._sanitize_id(conn.from_id)
        to_id = self._sanitize_id(conn.to_id)

        # Determine arrow style
        if conn.connection_type == 'bidirectional':
            arrow = '<-->'
        elif conn.style.stroke_style == 'dashed':
            arrow = '-.->'
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
        label = self._format_bracket_label(group.label or subgraph_id)
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

    def _generate_flowchart_styles(self, shapes: list[Shape]) -> list[str]:
        """Generate Mermaid style definitions for shapes."""
        lines = []

        for shape in shapes:
            if not shape.style.fill_color and not shape.style.stroke_color:
                continue  # No custom styling

            node_id = self._sanitize_id(shape.id)
            style_parts = []

            if shape.style.fill_color:
                style_parts.append(f'fill:{shape.style.fill_color}')

            if shape.style.stroke_color:
                style_parts.append(f'stroke:{shape.style.stroke_color}')

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

        source_to_group = {g.source_shape_id: g.id for g in groups}
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

        label = self._escape_quoted_label(group.label or group.source_shape_id)
        boundary_id = self._sanitize_id(group.id)
        return [f'    Boundary({boundary_id}, "{label}") {{', *body, '    }']

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
            resolved = endpoint_id
            if endpoint_id not in declared_ids:
                group_id = source_to_group.get(endpoint_id)
                resolved = group_representatives.get(group_id) if group_id else None
            if resolved is None:
                warnings.warn(f'dropping C4 Rel with unresolvable endpoint {endpoint_id!r}', stacklevel=2)
                return None
            endpoints.append(self._sanitize_id(resolved))

        label = self._escape_quoted_label(conn.label or 'uses')
        return f'    Rel({endpoints[0]}, {endpoints[1]}, "{label}")'

    def _format_c4_element(self, shape: Shape, in_boundary: bool) -> str:
        keywords = _C4_BOUNDARY_KEYWORDS if in_boundary else _C4_TOP_LEVEL_KEYWORDS
        default = 'Container' if in_boundary else 'System'
        keyword = keywords.get(shape.semantic_type or '', default)
        node_id = self._sanitize_id(shape.id)
        label = self._escape_quoted_label(shape.label or node_id)
        indent = '        ' if in_boundary else '    '
        return f'{indent}{keyword}({node_id}, "{label}")'

    def _generate_sequence(self, diagram: Diagram) -> str:
        """Generate Mermaid sequence diagram."""
        lines = ['sequenceDiagram']

        shapes = diagram.get_shapes()
        connections = diagram.get_connections()

        for shape in shapes:
            participant_id = self._sanitize_id(shape.id)
            label = self._escape_label(shape.label or participant_id)
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
        escaped = escaped.replace('<', '&lt;')
        escaped = escaped.replace('>', '&gt;')
        return escaped.replace('\n', '<br/>')
