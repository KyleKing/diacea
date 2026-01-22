"""TLDraw parser - converts TLDraw JSON to IR.

TLDraw is a modern infinite canvas diagramming tool with a structured JSON format.

Design decisions:
1. Multi-page handling: Process all pages or specific page by index/id
2. Custom shapes: Map unknown types to rectangle, log warning
3. Version compatibility: Support v15+ (latest stable)
4. Freehand elements: Convert to polygon shapes with bounding box
"""

from __future__ import annotations

import logging
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
    Text,
)
from ..ir.semantic import infer_semantic_type

_logger = logging.getLogger(__name__)


class TLDrawParser(Parser):
    """Parse TLDraw JSON to IR.

    Args:
        page_index: Index of page to process (0-based), or None for all pages
        page_id: ID of specific page to process, or None for all pages
        include_freehand: Whether to convert freehand drawings to shapes
    """

    def __init__(
        self,
        page_index: int | None = 0,
        page_id: str | None = None,
        include_freehand: bool = False,
    ):
        """Initialize parser with options."""
        self.page_index = page_index
        self.page_id = page_id
        self.include_freehand = include_freehand

    def parse(self, data: Any) -> Diagram:
        """Parse TLDraw document to IR diagram.

        Args:
            data: TLDraw JSON data (full document structure)

        Returns:
            IR Diagram object (merged if multiple pages)
        """
        pages = data.get('document', {}).get('pages', {})

        if not pages:
            return Diagram(id='empty', name='Empty Diagram', elements=[])

        pages_to_process = self._select_pages(pages)

        if not pages_to_process:
            return Diagram(id='empty', name='Empty Diagram', elements=[])

        all_elements: list = []
        diagram_name = 'TLDraw Diagram'
        diagram_id = 'diagram'

        for page_id, page in pages_to_process:
            elements = self._parse_page(page)
            all_elements.extend(elements)

            if len(pages_to_process) == 1:
                diagram_name = page.get('name', 'TLDraw Diagram')
                diagram_id = page.get('id', 'diagram')

        if len(pages_to_process) > 1:
            diagram_name = f'TLDraw Diagram ({len(pages_to_process)} pages)'

        return Diagram(id=diagram_id, name=diagram_name, elements=all_elements)

    def _select_pages(self, pages: dict) -> list[tuple[str, dict]]:
        """Select pages to process based on parser options."""
        page_list = list(pages.items())

        if self.page_id:
            if self.page_id in pages:
                return [(self.page_id, pages[self.page_id])]
            _logger.warning('Page ID %s not found, processing first page', self.page_id)
            return [page_list[0]] if page_list else []

        if self.page_index is not None:
            if 0 <= self.page_index < len(page_list):
                return [page_list[self.page_index]]
            _logger.warning('Page index %d out of range, processing first page', self.page_index)
            return [page_list[0]] if page_list else []

        return page_list

    def _parse_page(self, page: dict) -> list:
        """Parse a single TLDraw page to IR elements."""
        elements: list = []

        shapes = page.get('shapes', {})
        bindings = page.get('bindings', {})

        for shape_id, shape_data in shapes.items():
            shape_type = shape_data.get('type')
            if shape_type == 'arrow':
                continue
            if shape_type == 'draw' and not self.include_freehand:
                continue

            parsed = self._parse_shape(shape_id, shape_data)
            if parsed:
                elements.append(parsed)

        for shape_id, shape_data in shapes.items():
            if shape_data.get('type') == 'arrow':
                conn = self._parse_arrow(shape_id, shape_data, bindings)
                if conn:
                    elements.append(conn)

        return elements

    def _parse_shape(
        self, shape_id: str, shape_data: dict
    ) -> Shape | Group | Text | None:
        """Parse a TLDraw shape to IR element."""
        shape_type = shape_data.get('type')

        if shape_type == 'arrow':
            return None

        if shape_type == 'draw':
            return self._parse_freehand(shape_id, shape_data)

        point = shape_data.get('point', [0.0, 0.0])
        position = Point(x=float(point[0]), y=float(point[1]))

        size_data = shape_data.get('size', [100.0, 100.0])
        size = Dimensions(width=float(size_data[0]), height=float(size_data[1]))

        label = shape_data.get('label', shape_data.get('name', ''))

        style = self._parse_style(shape_data.get('style', {}))

        ir_shape_type = self._map_shape_type(shape_type)

        children_ids = shape_data.get('children', [])
        if children_ids:
            return Group(
                id=shape_id,
                label=label,
                position=position,
                size=size,
                style=style,
                children=children_ids,
            )

        if shape_type == 'text':
            return Text(
                id=shape_id,
                content=label,
                position=position,
                size=size,
                style=style,
            )

        shape = Shape(
            id=shape_id,
            label=label,
            shape_type=ir_shape_type,
            position=position,
            size=size,
            style=style,
        )

        shape.semantic_type, shape.semantic_confidence = infer_semantic_type(
            shape_type=ir_shape_type,
            label=label,
            size=size,
            style=style,
        )

        if shape.semantic_type:
            shape.semantic_type = shape.semantic_type.value

        return shape

    def _parse_freehand(self, shape_id: str, shape_data: dict) -> Shape | None:
        """Parse TLDraw freehand drawing to IR Shape (polygon bounding box)."""
        point = shape_data.get('point', [0.0, 0.0])
        base_x, base_y = float(point[0]), float(point[1])

        points = shape_data.get('points', [])
        if not points:
            return None

        xs = [base_x + p[0] for p in points]
        ys = [base_y + p[1] for p in points]

        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        width = max_x - min_x
        height = max_y - min_y

        if width < 5 and height < 5:
            return None

        position = Point(x=min_x, y=min_y)
        size = Dimensions(width=width, height=height)
        style = self._parse_style(shape_data.get('style', {}))

        shape = Shape(
            id=shape_id,
            label='',
            shape_type='freehand',
            position=position,
            size=size,
            style=style,
        )

        shape.metadata['freehand'] = {
            'point_count': len(points),
            'is_complete': shape_data.get('isComplete', False),
        }

        return shape

    def _parse_arrow(
        self,
        arrow_id: str,
        arrow_data: dict,
        bindings: dict,
    ) -> Connection | None:
        """Parse TLDraw arrow to IR connection.

        Args:
            arrow_id: Arrow identifier
            arrow_data: Arrow data from TLDraw
            bindings: Bindings dictionary from page

        Returns:
            Parsed Connection or None if invalid
        """
        handles = arrow_data.get("handles", {})

        start_handle = handles.get("start", {})
        end_handle = handles.get("end", {})

        start_binding_id = start_handle.get("bindingId")
        end_binding_id = end_handle.get("bindingId")

        # Get bound shape IDs from bindings
        from_id = None
        to_id = None

        if start_binding_id and start_binding_id in bindings:
            from_id = bindings[start_binding_id].get("toId")

        if end_binding_id and end_binding_id in bindings:
            to_id = bindings[end_binding_id].get("toId")

        if not from_id or not to_id:
            return None  # Can't create connection without both endpoints

        # Get label
        label = arrow_data.get("label", "")

        # Parse style
        style = self._parse_style(arrow_data.get("style", {}))

        # Determine if bidirectional
        decorations = arrow_data.get("decorations", {})
        start_dec = decorations.get("start")
        end_dec = decorations.get("end")

        connection_type = "directed"
        if start_dec == "arrow" and end_dec == "arrow":
            connection_type = "bidirectional"

        # Calculate approximate position (center of arrow)
        point = arrow_data.get("point", [0.0, 0.0])
        position = Point(x=float(point[0]), y=float(point[1]))

        # Approximate size (arrows don't have meaningful size)
        size = Dimensions(width=100.0, height=0.0)

        return Connection(
            id=arrow_id,
            from_id=from_id,
            to_id=to_id,
            label=label,
            connection_type=connection_type,
            position=position,
            size=size,
            style=style,
        )

    def _parse_style(self, style_data: dict) -> Style:
        """Parse TLDraw style to IR style.

        TLDraw uses named colors and sizes that need mapping.

        Args:
            style_data: Style dictionary from TLDraw shape

        Returns:
            IR Style object
        """
        # TLDraw color mapping
        color_map = {
            "black": "#1d1d1d",
            "white": "#ffffff",
            "lightGray": "#c6cbd1",
            "gray": "#788492",
            "darkGray": "#1d1d1d",
            "red": "#ff0000",
            "orange": "#ff8800",
            "yellow": "#ffff00",
            "green": "#00ff00",
            "blue": "#0000ff",
            "indigo": "#4b0082",
            "violet": "#ee82ee",
        }

        # TLDraw size mapping
        size_map = {
            "small": 2.0,
            "medium": 3.0,
            "large": 5.0,
        }

        color = style_data.get("color", "black")
        stroke_color = color_map.get(color, "#000000")

        size = style_data.get("size", "medium")
        stroke_width = size_map.get(size, 3.0)

        is_filled = style_data.get("isFilled", False)
        fill_color = stroke_color if is_filled else None

        dash = style_data.get("dash", "solid")
        stroke_style = "dashed" if dash in ["dashed", "dotted"] else "solid"

        return Style(
            fill_color=fill_color,
            stroke_color=stroke_color,
            stroke_width=stroke_width,
            stroke_style=stroke_style,
        )

    def _map_shape_type(self, tldraw_type: str | None) -> str:
        """Map TLDraw shape type to IR shape type.

        Args:
            tldraw_type: TLDraw shape type name

        Returns:
            IR shape type name
        """
        if not tldraw_type:
            return "rectangle"

        type_map = {
            "rectangle": "rectangle",
            "ellipse": "ellipse",
            "triangle": "triangle",
            "diamond": "diamond",
            "text": "text",
            "draw": "freehand",
            "sticky": "note",
            "group": "group",
        }

        return type_map.get(tldraw_type, "rectangle")
