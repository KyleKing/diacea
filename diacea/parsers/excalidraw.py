"""Excalidraw parser - converts Excalidraw JSON to IR.

Excalidraw format: https://docs.excalidraw.com/
"""

from __future__ import annotations

import logging
from collections import defaultdict
from itertools import pairwise
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
        frames: list[dict[str, Any]] = []

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

            elif elem_type == 'frame':
                frames.append(elem)

        # Second pass: Associate text labels with shapes
        self._associate_text_labels(shapes, texts)

        # Third pass: Process arrows/connections
        for arrow_data in connections:
            connection = self._parse_arrow(arrow_data, shapes)
            if connection:
                ir_elements.append(connection)

        # Fourth pass: Detect groups from native structure, then containment
        groups = self._detect_groups(shapes, frames)
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
            'frameId': elem.get('frameId'),
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
        """Associate each text with the smallest shape containing its center."""
        grid = _ShapeGrid(shapes)

        for text in texts:
            text_center = Point(
                x=text.position.x + text.size.width / 2,
                y=text.position.y + text.size.height / 2,
            )

            containing = [shape for shape in grid.at_point(text_center) if self._point_in_shape(text_center, shape)]
            if not containing:
                continue

            shape = min(containing, key=lambda s: s.size.area)
            shape.label = text.content
            shape.semantic_type, shape.semantic_confidence = infer_semantic_type(
                shape_type=shape.shape_type,
                label=shape.label,
                size=shape.size,
                style=shape.style,
                metadata=shape.metadata,
            )

    def _detect_groups(self, shapes: list[Shape], frames: list[dict[str, Any]]) -> list[Group]:
        """Build groups from native Excalidraw structure, then geometric containment for the rest.

        Groups hold direct children only; a nested group appears in its parent's
        children as its group id, never as its source shape id.
        """
        native_groups, covered_ids = self._build_native_groups(shapes, frames)
        remaining = [shape for shape in shapes if shape.id not in covered_ids]
        return [*native_groups, *self._build_geometric_groups(remaining)]

    def _native_group_chains(self, shapes: list[Shape]) -> dict[str, list[str]]:
        """Map each shape id to its structural groupIds chain, innermost first.

        A groupId is structural only when at least two shapes share it; ids used
        solely to bundle a shape with its label or decorations are dropped.
        """
        member_ids: dict[str, set[str]] = defaultdict(set)
        raw_chains: dict[str, list[str]] = {}
        for shape in shapes:
            chain = shape.metadata.get('excalidraw', {}).get('groupIds') or []
            raw_chains.setdefault(shape.id, chain)
            for group_id in chain:
                member_ids[group_id].add(shape.id)
        structural = {group_id for group_id, ids in member_ids.items() if len(ids) >= 2}
        return {shape_id: [gid for gid in chain if gid in structural] for shape_id, chain in raw_chains.items()}

    def _build_native_groups(self, shapes: list[Shape], frames: list[dict[str, Any]]) -> tuple[list[Group], set[str]]:
        shapes_by_id: dict[str, Shape] = {}
        for shape in shapes:
            shapes_by_id.setdefault(shape.id, shape)

        chains = self._native_group_chains(shapes)
        covered: set[str] = set()
        member_ids: dict[str, list[str]] = defaultdict(list)
        direct_shape_ids: dict[str, list[str]] = defaultdict(list)
        group_parents: dict[str, str | None] = {}
        for shape in shapes:
            chain = chains[shape.id]
            if not chain:
                continue
            covered.add(shape.id)
            direct_shape_ids[chain[0]].append(shape.id)
            for group_id in chain:
                member_ids[group_id].append(shape.id)
            group_parents.update(pairwise(chain))
            group_parents.setdefault(chain[-1], None)

        groups: list[Group] = []
        claimed_by_frame: set[str] = set()
        for frame in frames:
            frame_id = frame['id']
            frame_members = [
                shape for shape in shapes if shape.metadata.get('excalidraw', {}).get('frameId') == frame_id
            ]
            if not frame_members:
                continue
            child_shape_ids = [shape.id for shape in frame_members if not chains[shape.id]]
            child_group_ids = [
                group_id
                for group_id, parent in group_parents.items()
                if parent is None
                and group_id not in claimed_by_frame
                and all(
                    shapes_by_id[member_id].metadata.get('excalidraw', {}).get('frameId') == frame_id
                    for member_id in member_ids[group_id]
                )
            ]
            claimed_by_frame.update(child_group_ids)
            covered.update(shape.id for shape in frame_members)
            groups.append(
                Group(
                    id=f'{GROUP_ID_PREFIX}{frame_id}',
                    label=frame.get('name') or '',
                    position=Point(x=float(frame.get('x', 0)), y=float(frame.get('y', 0))),
                    size=Dimensions(width=float(frame.get('width', 0)), height=float(frame.get('height', 0))),
                    style=Style(),
                    children=[*child_shape_ids, *(f'{GROUP_ID_PREFIX}{gid}' for gid in child_group_ids)],
                )
            )

        child_groups_by_parent: dict[str, list[str]] = defaultdict(list)
        for group_id, parent in group_parents.items():
            if parent is not None:
                child_groups_by_parent[parent].append(group_id)

        for group_id, shape_ids in member_ids.items():
            member_shapes = [shapes_by_id[shape_id] for shape_id in shape_ids]
            position, size = self._bounding_box(member_shapes)
            groups.append(
                Group(
                    id=f'{GROUP_ID_PREFIX}{group_id}',
                    label='',
                    position=position,
                    size=size,
                    style=Style(),
                    children=[
                        *direct_shape_ids[group_id],
                        *(f'{GROUP_ID_PREFIX}{gid}' for gid in child_groups_by_parent[group_id]),
                    ],
                )
            )

        return groups, covered

    def _bounding_box(self, shapes: list[Shape]) -> tuple[Point, Dimensions]:
        x_min = min(shape.position.x for shape in shapes)
        y_min = min(shape.position.y for shape in shapes)
        x_max = max(shape.position.x + shape.size.width for shape in shapes)
        y_max = max(shape.position.y + shape.size.height for shape in shapes)
        return Point(x=x_min, y=y_min), Dimensions(width=x_max - x_min, height=y_max - y_min)

    def _build_geometric_groups(self, shapes: list[Shape]) -> list[Group]:
        if not shapes:
            return []
        shapes_by_id: dict[str, Shape] = {}
        for shape in shapes:
            shapes_by_id.setdefault(shape.id, shape)

        grid = _ShapeGrid(shapes)
        children_by_parent: dict[str, list[str]] = defaultdict(list)
        for shape in shapes:
            parent = self._smallest_container(shape, grid)
            if parent is not None:
                children_by_parent[parent.id].append(shape.id)

        groups: list[Group] = []
        for parent_id, child_ids in children_by_parent.items():
            parent = shapes_by_id[parent_id]
            children = [
                f'{GROUP_ID_PREFIX}{child_id}' if child_id in children_by_parent else child_id
                for child_id in child_ids
            ]
            group = Group(
                id=f'{GROUP_ID_PREFIX}{parent_id}',
                label=parent.label,
                position=parent.position,
                size=parent.size,
                style=parent.style,
                children=children,
            )
            group.metadata = parent.metadata.copy()
            groups.append(group)
        return groups

    def _smallest_container(self, shape: Shape, grid: _ShapeGrid) -> Shape | None:
        """Find the smallest larger shape covering this shape's center.

        Center coverage, not full containment, so a shape sloppily straddling a
        container border still joins that container.
        """
        center = Point(
            x=shape.position.x + shape.size.width / 2,
            y=shape.position.y + shape.size.height / 2,
        )
        containers = [
            candidate
            for candidate in grid.at_point(center)
            if candidate.id != shape.id
            and candidate.size.area > shape.size.area
            and self._point_in_shape(center, candidate)
        ]
        return min(containers, key=lambda s: s.size.area) if containers else None
