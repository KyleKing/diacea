"""D2 generator - converts IR to D2 diagram format.

D2 is a modern diagram scripting language with excellent layout and styling.

Design decisions (from Phase 4 open questions):
1. Icon integration: Not in v1, add as optional feature later
2. Theme support: Not in v1, can be added via CLI flag
3. Layout preservation: Let D2 optimize, no position constraints
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..ir import Connection, Diagram, Generator, Group, SemanticType, Shape


@dataclass
class D2Config:
    """Configuration for D2 generator."""

    direction: str | None = None  # up, down, left, right (None = auto-detect)
    sketch: bool = False  # Sketch mode for hand-drawn look
    shape_map: dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize default shape mappings."""
        if not self.shape_map:
            self.shape_map = {
                SemanticType.DATABASE: 'cylinder',
                SemanticType.PERSON: 'person',
                SemanticType.QUEUE: 'queue',
                SemanticType.STORAGE: 'cylinder',
                SemanticType.DOCUMENT: 'document',
                SemanticType.CLOUD: 'cloud',
                SemanticType.DECISION: 'diamond',
            }


class D2Generator(Generator):
    """Generate D2 from IR."""

    def __init__(self, config: D2Config | None = None) -> None:
        """Initialize generator.

        Args:
            config: D2 configuration or None for defaults
        """
        self.config = config or D2Config()
        self._element_paths: dict[str, str] = {}  # id -> D2 path

    def generate(self, diagram: Diagram) -> str:
        """Generate D2 diagram from IR.

        Args:
            diagram: IR Diagram object

        Returns:
            D2 diagram string
        """
        lines: list[str] = []

        # Direction
        direction = self.config.direction or self._detect_direction(diagram)
        if direction:
            lines.extend((f'direction: {direction}', ''))

        # Build element paths for hierarchy
        self._build_element_paths(diagram)

        # Generate all elements
        self._write_elements(diagram, lines)

        # Generate connections
        connections = diagram.get_connections()
        if connections:
            lines.append('')
            lines.extend(self._format_connection(conn) for conn in connections)

        return '\n'.join(lines)

    def _detect_direction(self, diagram: Diagram) -> str | None:
        """Auto-detect optimal direction based on layout."""
        shapes = diagram.get_shapes()
        if not shapes:
            return None

        # Calculate bounding box
        min_x = min(s.position.x for s in shapes)
        max_x = max(s.position.x + s.size.width for s in shapes)
        min_y = min(s.position.y for s in shapes)
        max_y = max(s.position.y + s.size.height for s in shapes)

        width = max_x - min_x
        height = max_y - min_y

        # If wider than tall, use right
        if width > height * 1.5:
            return 'right'
        # If taller than wide, use down
        if height > width * 1.5:
            return 'down'

        return None  # Let D2 decide

    def _build_element_paths(self, diagram: Diagram) -> None:
        """Build D2 paths for all elements."""
        self._element_paths.clear()

        # Map elements to their groups
        child_to_parent: dict[str, str] = {}
        groups = diagram.get_groups()

        for group in groups:
            for child_id in group.children:
                child_to_parent[child_id] = group.id

        # Build paths recursively
        def get_path(elem_id: str, visited: set[str]) -> str:
            if elem_id in visited:
                # Circular reference, just use sanitized ID
                return self._sanitize_id(elem_id)

            visited.add(elem_id)

            if elem_id in child_to_parent:
                parent_id = child_to_parent[elem_id]
                parent_path = get_path(parent_id, visited)
                sanitized_id = self._sanitize_id(elem_id)
                return f'{parent_path}.{sanitized_id}' if parent_path else sanitized_id
            return self._sanitize_id(elem_id)

        for elem in diagram.elements:
            self._element_paths[elem.id] = get_path(elem.id, set())

    def _write_elements(self, diagram: Diagram, lines: list[str]) -> None:
        """Write all elements (shapes and groups)."""
        groups = diagram.get_groups()
        shapes = diagram.get_shapes()

        # Write groups first (containers)
        for group in groups:
            self._write_group(group, shapes, lines)

        grouped_ids = set()
        for group in groups:
            grouped_ids.update(group.children)

        group_source_ids = {g.source_shape_id for g in groups}
        standalone_shapes = [s for s in shapes if s.id not in grouped_ids and s.id not in group_source_ids]
        lines.extend(self._format_shape(shape) for shape in standalone_shapes)

    def _write_group(self, group: Group, all_shapes: list[Shape], lines: list[str]) -> None:
        """Write a group as a D2 container."""
        group_id = self._sanitize_id(group.id)
        label = self._escape_label(group.label or group_id)

        # Start container
        lines.append(f'{group_id}: {label} {{')

        # Write child shapes
        for child_id in group.children:
            child_shape = next((s for s in all_shapes if s.id == child_id), None)
            if child_shape:
                # For children, use relative path (just the ID)
                child_line = self._format_shape(child_shape, use_relative_path=True)
                lines.extend(f'  {line}' for line in child_line.split('\n'))

        # Close container
        lines.extend(('}', ''))

    def _format_shape(self, shape: Shape, use_relative_path: bool = False) -> str:
        """Format a D2 shape declaration."""
        if use_relative_path:
            shape_id = self._sanitize_id(shape.id)
        else:
            shape_id = self._element_paths.get(shape.id, self._sanitize_id(shape.id))

        label = self._escape_label(shape.label or shape_id)

        # Determine D2 shape
        d2_shape = self._get_d2_shape(shape)
        has_style = self._has_custom_style(shape)

        # Simple declaration if no special properties
        if not d2_shape and not has_style:
            return f'{shape_id}: {label}'

        # Complex declaration with properties
        lines = [f'{shape_id}: {label} {{']

        if d2_shape:
            lines.append(f'  shape: {d2_shape}')

        if has_style:
            style_lines = self._format_style(shape)
            lines.extend(f'  {line}' for line in style_lines)

        lines.append('}')

        return '\n'.join(lines)

    def _get_d2_shape(self, shape: Shape) -> str | None:
        """Get D2 shape name based on semantic or geometric type."""
        # Check semantic type first
        if shape.semantic_type and shape.semantic_type in self.config.shape_map:
            return self.config.shape_map[shape.semantic_type]

        # Map geometric shapes
        shape_map = {
            'ellipse': 'oval',
            'diamond': 'diamond',
            'circle': 'circle',
        }

        return shape_map.get(shape.shape_type)

    def _has_custom_style(self, shape: Shape) -> bool:
        """Check if shape has custom styling."""
        style = shape.style
        return bool(style.fill_color or style.stroke_color or style.stroke_width or style.stroke_style == 'dashed')

    def _format_style(self, shape: Shape) -> list[str]:
        """Format D2 style block for a shape."""
        lines = []
        style = shape.style

        style_props = []
        if style.fill_color:
            style_props.append(f'fill: {style.fill_color}')

        if style.stroke_color:
            style_props.append(f'stroke: {style.stroke_color}')

        if style.stroke_width:
            style_props.append(f'stroke-width: {int(style.stroke_width)}')

        if style.stroke_style == 'dashed':
            style_props.append('stroke-dash: 3')

        if style_props:
            lines.append('style: {')
            lines.extend(f'  {prop}' for prop in style_props)
            lines.append('}')

        return lines

    def _format_connection(self, conn: Connection) -> str:
        """Format a D2 connection."""
        from_path = self._element_paths.get(conn.from_id, self._sanitize_id(conn.from_id))
        to_path = self._element_paths.get(conn.to_id, self._sanitize_id(conn.to_id))

        # Determine arrow type
        arrow = self._get_arrow_type(conn)

        # Format connection
        if conn.label:
            label = self._escape_label(conn.label)
            line = f'{from_path} {arrow} {to_path}: {label}'
        else:
            line = f'{from_path} {arrow} {to_path}'

        # Add styling if needed
        if self._connection_has_style(conn):
            lines = [line + ' {']
            style_lines = self._format_connection_style(conn)
            lines.extend(f'  {l}' for l in style_lines)
            lines.append('}')
            return '\n'.join(lines)

        return line

    def _get_arrow_type(self, conn: Connection) -> str:
        """Get D2 arrow type."""
        if conn.connection_type == 'bidirectional':
            return '<->'
        return '->'

    def _connection_has_style(self, conn: Connection) -> bool:
        """Check if connection has custom styling."""
        style = conn.style
        return bool(style.stroke_color or style.stroke_width or style.stroke_style == 'dashed')

    def _format_connection_style(self, conn: Connection) -> list[str]:
        """Format D2 style for connection."""
        lines = []
        style = conn.style

        style_props = []
        if style.stroke_color:
            style_props.append(f'stroke: {style.stroke_color}')

        if style.stroke_width:
            style_props.append(f'stroke-width: {int(style.stroke_width)}')

        if style.stroke_style == 'dashed':
            style_props.append('stroke-dash: 3')

        if style_props:
            lines.append('style: {')
            lines.extend(f'  {prop}' for prop in style_props)
            lines.append('}')

        return lines

    def _sanitize_id(self, id_str: str) -> str:
        """Sanitize ID for D2 format."""
        # D2 allows hyphens and underscores
        # Replace spaces and special chars
        sanitized = id_str.replace(' ', '_').replace(':', '_')

        # Escape if starts with number
        if sanitized and sanitized[0].isdigit():
            sanitized = 'n_' + sanitized

        return sanitized or 'node'

    def _escape_label(self, label: str) -> str:
        """Escape label for D2 format."""
        # D2 handles most characters well, escape special ones
        escaped = label.replace('\\', '\\\\').replace('\n', '\\n')

        # Quote if contains special characters
        if any(c in escaped for c in ['{', '}', ':', ';']):
            escaped = f'"{escaped}"'

        return escaped
