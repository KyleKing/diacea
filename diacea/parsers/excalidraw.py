"""Excalidraw parser - converts Excalidraw JSON to IR.

Excalidraw format: https://docs.excalidraw.com/
"""

from __future__ import annotations

import logging
from collections import defaultdict
from math import floor
from typing import Any

from ..ir import (
    GROUP_ID_PREFIX,
    Connection,
    Diagram,
    Dimensions,
    Element,
    Group,
    Parser,
    Point,
    Shape,
    Style,
    Text,
    infer_semantic_type,
)

_logger = logging.getLogger(__name__)

_MIN_CELL_SIZE = 1.0
"""Smallest grid cell, so degenerate zero-size shapes cannot collapse the index."""

_MAX_CELLS_PER_SHAPE = 64
"""A shape spanning more cells than this is held aside instead of indexed."""

_MAX_CELLS_PER_QUERY = 4096
"""A region query spanning more cells than this falls back to a full scan."""


class _ShapeGrid:
    """Uniform bucket grid over shape bounding boxes.

    Queries return a superset of the true hits in the order shapes were indexed,
    so callers must still apply the exact geometric test to each candidate.
    """

    def __init__(self, shapes: list[Shape]) -> None:
        self._shapes = shapes
        dimensions = sorted(d for shape in shapes for d in (shape.size.width, shape.size.height) if d > 0)
        median = dimensions[len(dimensions) // 2] if dimensions else _MIN_CELL_SIZE
        self._cell = max(median, _MIN_CELL_SIZE)
        self._cells: dict[tuple[int, int], list[int]] = defaultdict(list)
        self._oversized: list[int] = []
        for index, shape in enumerate(shapes):
            x_min, y_min, x_max, y_max = self._cell_bounds(shape)
            if (x_max - x_min + 1) * (y_max - y_min + 1) > _MAX_CELLS_PER_SHAPE:
                self._oversized.append(index)
                continue
            for cell_x in range(x_min, x_max + 1):
                for cell_y in range(y_min, y_max + 1):
                    self._cells[cell_x, cell_y].append(index)

    def _cell_bounds(self, shape: Shape) -> tuple[int, int, int, int]:
        cell = self._cell
        return (
            floor(shape.position.x / cell),
            floor(shape.position.y / cell),
            floor((shape.position.x + shape.size.width) / cell),
            floor((shape.position.y + shape.size.height) / cell),
        )

    def _resolve(self, indexes: list[int]) -> list[Shape]:
        if self._oversized:
            indexes = sorted({*indexes, *self._oversized})
        return [self._shapes[index] for index in indexes]

    def at_point(self, point: Point) -> list[Shape]:
        """Return shapes whose bounding box may contain the point."""
        key = (floor(point.x / self._cell), floor(point.y / self._cell))
        return self._resolve(self._cells.get(key, []))

    def within(self, shape: Shape) -> list[Shape]:
        """Return shapes whose bounding box may be enclosed by the given shape."""
        x_min, y_min, x_max, y_max = self._cell_bounds(shape)
        if (x_max - x_min + 1) * (y_max - y_min + 1) > _MAX_CELLS_PER_QUERY:
            return self._shapes
        indexes: set[int] = set()
        for cell_x in range(x_min, x_max + 1):
            for cell_y in range(y_min, y_max + 1):
                indexes.update(self._cells.get((cell_x, cell_y), []))
        return self._resolve(sorted(indexes))


class ExcalidrawParser(Parser):
    """Parse Excalidraw JSON format to IR."""

    def __init__(self) -> None:
        """Initialize parser."""
        self.warnings: list[str] = []

    def parse(self, data: Any) -> Diagram:
        """Parse Excalidraw JSON to IR Diagram.

        Args:
            data: Excalidraw JSON dict (with 'elements' key) or list of elements

        Returns:
            Diagram object

        Raises:
            ValueError: If data format is invalid
        """
        self.warnings = []

        # Handle both full Excalidraw format and just elements list
        if isinstance(data, dict):
            elements = data.get('elements', [])
            excalidraw_metadata = {k: v for k, v in data.items() if k != 'elements'}
        elif isinstance(data, list):
            elements = data
            excalidraw_metadata = {}
        else:
            raise ValueError('Invalid Excalidraw data format')

        # Parse elements by type
        ir_elements: list[Element] = []
        shapes: list[Shape] = []
        connections: list[dict[str, Any]] = []
        texts: list[Text] = []

        # First pass: Parse all elements
        for elem in elements:
            elem_type = elem.get('type', '')

            if elem_type in {'rectangle', 'ellipse', 'diamond'}:
                shape = self._parse_shape(elem)
                ir_elements.append(shape)
                shapes.append(shape)

            elif elem_type == 'arrow':
                # Store arrows for second pass (need shapes first)
                connections.append(elem)

            elif elem_type == 'text':
                text = self._parse_text(elem)
                ir_elements.append(text)
                texts.append(text)

        # Second pass: Associate text labels with shapes
        self._associate_text_labels(shapes, texts)

        # Third pass: Process arrows/connections
        for arrow_data in connections:
            connection = self._parse_arrow(arrow_data, shapes)
            if connection:
                ir_elements.append(connection)

        # Fourth pass: Detect groups based on containment
        groups = self._detect_groups(shapes)
        ir_elements.extend(groups)

        # Create diagram
        return Diagram(
            id='excalidraw-diagram',
            elements=ir_elements,
            metadata={'excalidraw': excalidraw_metadata},
        )

    def _parse_shape(self, elem: dict[str, Any]) -> Shape:
        """Parse Excalidraw shape to IR Shape."""
        # Position and size
        position = Point(x=float(elem.get('x', 0)), y=float(elem.get('y', 0)))
        size = Dimensions(width=float(elem.get('width', 0)), height=float(elem.get('height', 0)))

        # Style
        stroke_width = elem.get('strokeWidth')
        style = Style(
            fill_color=elem.get('backgroundColor') if elem.get('backgroundColor') != 'transparent' else None,
            stroke_color=elem.get('strokeColor'),
            stroke_width=float(stroke_width) if stroke_width is not None else None,
            stroke_style='dashed' if elem.get('strokeStyle') == 'dashed' else 'solid',
            opacity=float(elem.get('opacity', 100)) / 100.0,
        )

        # Map Excalidraw type to IR shape type
        shape_type = elem.get('type', 'rectangle')

        # Create shape
        shape = Shape(
            id=elem['id'],
            label='',  # Will be filled in by text association
            shape_type=shape_type,
            position=position,
            size=size,
            style=style,
            z_index=0,  # Could use groupIds order if needed
        )

        # Preserve Excalidraw-specific metadata for round-tripping
        excalidraw_metadata = {
            'roughness': elem.get('roughness'),
            'fillStyle': elem.get('fillStyle'),
            'roundness': elem.get('roundness'),
            'seed': elem.get('seed'),
            'groupIds': elem.get('groupIds', []),
            'boundElements': elem.get('boundElements', []),
        }
        shape.metadata['excalidraw'] = excalidraw_metadata

        # Infer semantic type
        shape.semantic_type, shape.semantic_confidence = infer_semantic_type(
            shape_type=shape_type,
            label=shape.label,  # Empty for now, will update after text association
            size=size,
            style=style,
            metadata=shape.metadata,
        )

        return shape

    def _parse_text(self, elem: dict[str, Any]) -> Text:
        """Parse Excalidraw text to IR Text."""
        position = Point(x=float(elem.get('x', 0)), y=float(elem.get('y', 0)))
        size = Dimensions(width=float(elem.get('width', 0)), height=float(elem.get('height', 0)))

        font_size = elem.get('fontSize')
        style = Style(
            stroke_color=elem.get('strokeColor'),
            font_family=str(elem.get('fontFamily', 'default')),
            font_size=float(font_size) if font_size is not None else None,
        )

        text = Text(
            id=elem['id'],
            content=elem.get('text', ''),
            alignment=elem.get('textAlign', 'left'),
            position=position,
            size=size,
            style=style,
        )

        # Preserve Excalidraw metadata
        text.metadata['excalidraw'] = {
            'originalText': elem.get('originalText'),
            'containerId': elem.get('containerId'),
            'autoResize': elem.get('autoResize'),
        }

        return text

    def _parse_arrow(self, elem: dict[str, Any], shapes: list[Shape]) -> Connection | None:
        """Parse Excalidraw arrow to IR Connection."""
        arrow_id = elem.get('id', 'unknown')

        # Get arrow points
        points = elem.get('points', [])
        if len(points) < 2:
            _logger.debug("Dropping arrow '%s': insufficient points (%d < 2)", arrow_id, len(points))
            self.warnings.append(f"Dropped arrow '{arrow_id}': fewer than 2 points")
            return None

        # Calculate absolute start and end points
        arrow_x = float(elem.get('x', 0))
        arrow_y = float(elem.get('y', 0))
        start_point = Point(x=arrow_x + float(points[0][0]), y=arrow_y + float(points[0][1]))
        end_point = Point(x=arrow_x + float(points[-1][0]), y=arrow_y + float(points[-1][1]))

        # Find connected shapes using bindings or nearest rectangle
        from_id, to_id = self._find_arrow_connections(elem, shapes, start_point, end_point)

        if not from_id or not to_id:
            _logger.debug(
                "Dropping arrow '%s': missing endpoint(s) (from_id=%s, to_id=%s)",
                arrow_id,
                from_id,
                to_id,
            )
            self.warnings.append(f"Dropped arrow '{arrow_id}': could not resolve both endpoints")
            return None

        # Determine connection type
        start_arrowhead = elem.get('startArrowhead')
        end_arrowhead = elem.get('endArrowhead')

        connection_type = 'bidirectional' if start_arrowhead == 'arrow' and end_arrowhead == 'arrow' else 'directed'

        # Style
        stroke_width = elem.get('strokeWidth')
        style = Style(
            stroke_color=elem.get('strokeColor'),
            stroke_width=float(stroke_width) if stroke_width is not None else None,
            stroke_style='dashed' if elem.get('strokeStyle') == 'dashed' else 'solid',
        )

        # Create connection
        # Use center of arrow for position (approximate)
        center_x = (start_point.x + end_point.x) / 2
        center_y = (start_point.y + end_point.y) / 2
        width = abs(end_point.x - start_point.x)
        height = abs(end_point.y - start_point.y)

        connection = Connection(
            id=elem['id'],
            from_id=from_id,
            to_id=to_id,
            label='',  # Arrows typically don't have labels in Excalidraw
            connection_type=connection_type,
            position=Point(x=center_x, y=center_y),
            size=Dimensions(width=width, height=height),
            style=style,
            start_point=start_point,
            end_point=end_point,
        )

        # Preserve waypoints for complex routing
        waypoints = [Point(x=arrow_x + float(p[0]), y=arrow_y + float(p[1])) for p in points[1:-1]]
        connection.waypoints = waypoints

        # Preserve Excalidraw metadata
        connection.metadata['excalidraw'] = {
            'points': points,
            'startBinding': elem.get('startBinding'),
            'endBinding': elem.get('endBinding'),
            'elbowed': elem.get('elbowed'),
        }

        return connection

    def _find_arrow_connections(
        self, arrow: dict[str, Any], shapes: list[Shape], start_point: Point, end_point: Point
    ) -> tuple[str | None, str | None]:
        """Find which shapes an arrow connects to.

        Uses bindings first, falls back to spatial proximity.
        """
        # Try using Excalidraw bindings first
        start_binding = arrow.get('startBinding')
        end_binding = arrow.get('endBinding')

        from_id = start_binding.get('elementId') if start_binding else None
        to_id = end_binding.get('elementId') if end_binding else None

        # If no bindings, use spatial proximity
        if not from_id:
            from_shape = self._find_nearest_shape(start_point, shapes)
            from_id = from_shape.id if from_shape else None

        if not to_id:
            to_shape = self._find_nearest_shape(end_point, shapes)
            to_id = to_shape.id if to_shape else None

        return (from_id, to_id)

    def _find_nearest_shape(self, point: Point, shapes: list[Shape]) -> Shape | None:
        """Find the nearest shape to a point."""
        if not shapes:
            return None

        # First check if point is inside any shape
        inside_shapes = [shape for shape in shapes if self._point_in_shape(point, shape)]

        # If inside multiple shapes, return the smallest
        if inside_shapes:
            return min(inside_shapes, key=lambda s: s.size.area)

        # Otherwise, return nearest shape by distance
        def distance(shape: Shape) -> float:
            center_x = shape.position.x + shape.size.width / 2
            center_y = shape.position.y + shape.size.height / 2
            return ((center_x - point.x) ** 2 + (center_y - point.y) ** 2) ** 0.5

        return min(shapes, key=distance)

    def _point_in_shape(self, point: Point, shape: Shape) -> bool:
        """Check if a point is inside a shape's bounding box."""
        return (
            shape.position.x <= point.x <= shape.position.x + shape.size.width
            and shape.position.y <= point.y <= shape.position.y + shape.size.height
        )

    def _associate_text_labels(self, shapes: list[Shape], texts: list[Text]) -> None:
        """Associate text elements with shapes as labels."""
        grid = _ShapeGrid(shapes)

        for text in texts:
            text_center = Point(
                x=text.position.x + text.size.width / 2,
                y=text.position.y + text.size.height / 2,
            )

            # Find shapes that contain this text
            for shape in grid.at_point(text_center):
                if self._point_in_shape(text_center, shape):
                    # Assign text content as shape label
                    shape.label = text.content

                    # Re-run semantic inference with label
                    shape.semantic_type, shape.semantic_confidence = infer_semantic_type(
                        shape_type=shape.shape_type,
                        label=shape.label,
                        size=shape.size,
                        style=shape.style,
                        metadata=shape.metadata,
                    )

                    break  # Each text belongs to at most one shape

    def _detect_groups(self, shapes: list[Shape]) -> list[Group]:
        """Detect groups based on containment relationships.

        Shapes that contain other shapes become groups.
        """
        groups = []

        # Sort shapes by area (largest first)
        sorted_shapes = sorted(shapes, key=lambda s: s.size.area, reverse=True)
        shapes_by_id: dict[str, Shape] = {}
        for shape in shapes:
            shapes_by_id.setdefault(shape.id, shape)
        grid = _ShapeGrid(sorted_shapes)

        for outer_shape in sorted_shapes:
            # Find shapes inside this one
            children = []
            for inner_shape in grid.within(outer_shape):
                if outer_shape.id == inner_shape.id:
                    continue

                # Check if inner is completely inside outer
                if self._shape_contains_shape(outer_shape, inner_shape):
                    children.append(inner_shape.id)

            # If this shape contains others, create a group
            if children:
                # Only create group if it's the smallest container for these children
                # (avoid duplicate groups for nested containment)
                # TODO: every candidate is itself a child, so the `all` below always compares a
                # shape against itself and this check can never fire; decide the intended rule
                is_smallest_container = True
                for child_id_ in children:
                    other_shape = shapes_by_id[child_id_]
                    if other_shape.id == outer_shape.id:
                        continue
                    # If another smaller shape also contains all children, skip this one
                    if (
                        other_shape.size.area < outer_shape.size.area
                        and self._shape_contains_shape(outer_shape, other_shape)
                        and all(
                            self._shape_contains_shape(other_shape, shapes_by_id[child_id]) for child_id in children
                        )
                    ):
                        is_smallest_container = False
                        break

                if is_smallest_container:
                    group = Group(
                        id=f'{GROUP_ID_PREFIX}{outer_shape.id}',
                        label=outer_shape.label,
                        position=outer_shape.position,
                        size=outer_shape.size,
                        style=outer_shape.style,
                        children=children,
                    )
                    group.metadata = outer_shape.metadata.copy()
                    groups.append(group)

        return groups

    def _shape_contains_shape(self, outer: Shape, inner: Shape) -> bool:
        """Check if outer shape completely contains inner shape."""
        return (
            outer.position.x < inner.position.x
            and outer.position.y < inner.position.y
            and outer.position.x + outer.size.width > inner.position.x + inner.size.width
            and outer.position.y + outer.size.height > inner.position.y + inner.size.height
        )
