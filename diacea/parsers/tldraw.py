"""TLDraw parser - converts TLDraw JSON to IR.

TLDraw is a modern infinite canvas diagramming tool with a structured JSON format.

Design decisions (from Phase 5 open questions):
1. Multi-page handling: Process first page by default
2. Custom shapes: Map unknown types to rectangle, log warning
3. Version compatibility: Support v15+ (latest stable)
4. Freehand elements: Skip for now, don't map well to structured diagrams
"""

from __future__ import annotations

from typing import Any, Optional

from ..ir import (
    Connection,
    Diagram,
    Dimensions,
    Generator,
    Group,
    Parser,
    Point,
    Shape,
    Style,
    Text,
)
from ..ir.semantic import infer_semantic_type


class TLDrawParser(Parser):
    """Parse TLDraw JSON to IR."""

    def parse(self, data: Any) -> Diagram:
        """Parse TLDraw document to IR diagram.

        Args:
            data: TLDraw JSON data (full document structure)

        Returns:
            IR Diagram object
        """
        elements: list = []

        # TLDraw has pages - process the first page
        pages = data.get("document", {}).get("pages", {})

        if not pages:
            return Diagram(id="empty", name="Empty Diagram", elements=[])

        # Get first page
        first_page_id = next(iter(pages.keys()))
        page = pages[first_page_id]

        shapes = page.get("shapes", {})
        bindings = page.get("bindings", {})

        # Parse shapes first (excluding arrows)
        for shape_id, shape_data in shapes.items():
            if shape_data.get("type") != "arrow":
                parsed = self._parse_shape(shape_id, shape_data)
                if parsed:
                    elements.append(parsed)

        # Parse arrows/connections
        for shape_id, shape_data in shapes.items():
            if shape_data.get("type") == "arrow":
                conn = self._parse_arrow(shape_id, shape_data, bindings)
                if conn:
                    elements.append(conn)

        return Diagram(
            id=page.get("id", "diagram"),
            name=page.get("name", "TLDraw Diagram"),
            elements=elements,
        )

    def _parse_shape(
        self, shape_id: str, shape_data: dict
    ) -> Shape | Group | Text | None:
        """Parse a TLDraw shape to IR element.

        Args:
            shape_id: Shape identifier
            shape_data: Shape data from TLDraw

        Returns:
            Parsed IR element (Shape, Group, or Text) or None if skipped
        """
        shape_type = shape_data.get("type")

        # Skip arrows and freehand - handled separately
        if shape_type in ["arrow", "draw"]:
            return None

        # Get position (TLDraw uses point array)
        point = shape_data.get("point", [0.0, 0.0])
        position = Point(x=float(point[0]), y=float(point[1]))

        # Get size
        size_data = shape_data.get("size", [100.0, 100.0])
        size = Dimensions(width=float(size_data[0]), height=float(size_data[1]))

        # Get label
        label = shape_data.get("label", shape_data.get("name", ""))

        # Parse style
        style = self._parse_style(shape_data.get("style", {}))

        # Determine IR shape type
        ir_shape_type = self._map_shape_type(shape_type)

        # Check if it's a group (has children)
        children_ids = shape_data.get("children", [])
        if children_ids:
            return Group(
                id=shape_id,
                label=label,
                position=position,
                size=size,
                style=style,
                children=children_ids,
            )

        # Check if it's text
        if shape_type == "text":
            return Text(
                id=shape_id,
                content=label,
                position=position,
                size=size,
                style=style,
            )

        # Regular shape
        shape = Shape(
            id=shape_id,
            label=label,
            shape_type=ir_shape_type,
            position=position,
            size=size,
            style=style,
        )

        # Infer semantic type
        shape.semantic_type, shape.semantic_confidence = infer_semantic_type(
            shape_type=ir_shape_type,
            label=label,
            size=size,
            style=style,
        )

        # Store as string to avoid enum serialization issues
        if shape.semantic_type:
            shape.semantic_type = shape.semantic_type.value

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
