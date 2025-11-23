"""SVG parser - converts basic SVG to IR.

Supports basic SVG shapes, text, and groups. Does NOT support complex
paths, gradients, filters, or masks.

Design decisions (from Phase 6 open questions):
1. Path support: Not in v1 (too complex)
2. Transform support: Basic translate only, skip rotate/scale for v1
3. Connection detection: Low priority, spatial analysis needed
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any, Optional

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
from ..ir.semantic import SemanticType, infer_semantic_type


class SVGParser(Parser):
    """Parse basic SVG to IR.

    Supports: rect, circle, ellipse, polygon, text, groups
    Does NOT support: complex paths, gradients, transforms
    """

    # SVG namespace
    SVG_NS = "{http://www.w3.org/2000/svg}"

    def __init__(self):
        """Initialize parser."""
        self._id_counter = 0
        self._text_elements: dict[str, Text] = {}

    def parse(self, data: Any) -> Diagram:
        """Parse SVG content to IR diagram.

        Args:
            data: SVG string or ElementTree Element

        Returns:
            IR Diagram object
        """
        if isinstance(data, str):
            root = ET.fromstring(data)
        else:
            root = data

        elements: list = []

        # Process all child elements
        self._process_element(root, elements, transform=None, parent_id=None)

        # Post-process: associate text with nearby shapes
        self._associate_text_labels(elements)

        return Diagram(
            id=root.get("id", "svg-diagram"),
            name="SVG Diagram",
            elements=elements,
        )

    def _process_element(
        self,
        elem: ET.Element,
        elements: list,
        transform: Any | None,
        parent_id: str | None,
    ) -> None:
        """Process SVG element recursively.

        Args:
            elem: SVG element to process
            elements: List to append parsed elements to
            transform: Current transform matrix (not fully supported)
            parent_id: Parent element ID for grouping
        """
        tag = elem.tag.replace(self.SVG_NS, "")

        if tag == "rect":
            shape = self._parse_rect(elem, transform)
            if shape:
                elements.append(shape)

        elif tag == "circle":
            shape = self._parse_circle(elem, transform)
            if shape:
                elements.append(shape)

        elif tag == "ellipse":
            shape = self._parse_ellipse(elem, transform)
            if shape:
                elements.append(shape)

        elif tag == "polygon":
            shape = self._parse_polygon(elem, transform)
            if shape:
                elements.append(shape)

        elif tag == "text":
            text = self._parse_text(elem, transform)
            if text:
                self._text_elements[text.id] = text
                elements.append(text)

        elif tag == "g":
            self._parse_group(elem, elements, transform)

        # Process children for non-group elements
        if tag != "g":
            for child in elem:
                self._process_element(child, elements, transform, parent_id)

    def _parse_rect(self, elem: ET.Element, transform: Any | None) -> Shape | None:
        """Parse SVG rect to IR Shape.

        Args:
            elem: rect element
            transform: Transform matrix (not used in v1)

        Returns:
            Shape or None if invalid
        """
        x = float(elem.get("x", 0))
        y = float(elem.get("y", 0))
        width = float(elem.get("width", 0))
        height = float(elem.get("height", 0))

        if width == 0 or height == 0:
            return None

        position = Point(x=x, y=y)
        size = Dimensions(width=width, height=height)
        style = self._parse_style_attrs(elem)

        shape_id = elem.get("id") or self._generate_id()
        label = elem.get("data-label", "")

        shape = Shape(
            id=shape_id,
            label=label,
            shape_type="rectangle",
            position=position,
            size=size,
            style=style,
        )

        # Check for semantic hints
        semantic_hint = elem.get("data-semantic") or elem.get("class", "")
        if semantic_hint:
            shape.semantic_type = self._parse_semantic_hint(semantic_hint)
            shape.semantic_confidence = 0.9
        else:
            shape.semantic_type, shape.semantic_confidence = infer_semantic_type(
                shape_type="rectangle",
                label=label,
                size=size,
                style=style,
            )

        # Store as string to avoid enum serialization issues
        if shape.semantic_type:
            shape.semantic_type = shape.semantic_type.value

        return shape

    def _parse_circle(self, elem: ET.Element, transform: Any | None) -> Shape | None:
        """Parse SVG circle to IR Shape.

        Args:
            elem: circle element
            transform: Transform matrix (not used in v1)

        Returns:
            Shape or None if invalid
        """
        cx = float(elem.get("cx", 0))
        cy = float(elem.get("cy", 0))
        r = float(elem.get("r", 0))

        if r == 0:
            return None

        # Convert circle to bounding box
        position = Point(x=cx - r, y=cy - r)
        size = Dimensions(width=r * 2, height=r * 2)
        style = self._parse_style_attrs(elem)

        shape_id = elem.get("id") or self._generate_id()
        label = elem.get("data-label", "")

        shape = Shape(
            id=shape_id,
            label=label,
            shape_type="ellipse",
            position=position,
            size=size,
            style=style,
        )

        # Infer semantic type
        semantic_hint = elem.get("data-semantic")
        if semantic_hint:
            shape.semantic_type = self._parse_semantic_hint(semantic_hint)
            shape.semantic_confidence = 0.9
        else:
            shape.semantic_type, shape.semantic_confidence = infer_semantic_type(
                shape_type="ellipse",
                label=label,
                size=size,
                style=style,
            )

        # Store as string
        if shape.semantic_type:
            shape.semantic_type = shape.semantic_type.value

        return shape

    def _parse_ellipse(self, elem: ET.Element, transform: Any | None) -> Shape | None:
        """Parse SVG ellipse to IR Shape.

        Args:
            elem: ellipse element
            transform: Transform matrix (not used in v1)

        Returns:
            Shape or None if invalid
        """
        cx = float(elem.get("cx", 0))
        cy = float(elem.get("cy", 0))
        rx = float(elem.get("rx", 0))
        ry = float(elem.get("ry", 0))

        if rx == 0 or ry == 0:
            return None

        position = Point(x=cx - rx, y=cy - ry)
        size = Dimensions(width=rx * 2, height=ry * 2)
        style = self._parse_style_attrs(elem)

        shape_id = elem.get("id") or self._generate_id()
        label = elem.get("data-label", "")

        shape = Shape(
            id=shape_id,
            label=label,
            shape_type="ellipse",
            position=position,
            size=size,
            style=style,
        )

        semantic_hint = elem.get("data-semantic")
        if semantic_hint:
            shape.semantic_type = self._parse_semantic_hint(semantic_hint)
            shape.semantic_confidence = 0.9
        else:
            shape.semantic_type, shape.semantic_confidence = infer_semantic_type(
                shape_type="ellipse",
                label=label,
                size=size,
                style=style,
            )

        # Store as string
        if shape.semantic_type:
            shape.semantic_type = shape.semantic_type.value

        return shape

    def _parse_polygon(self, elem: ET.Element, transform: Any | None) -> Shape | None:
        """Parse SVG polygon to IR Shape.

        Simplified: 4 points → diamond, otherwise → polygon

        Args:
            elem: polygon element
            transform: Transform matrix (not used in v1)

        Returns:
            Shape or None if invalid
        """
        points_str = elem.get("points", "")
        if not points_str:
            return None

        # Parse points
        coords = [float(x) for x in points_str.replace(",", " ").split()]
        if len(coords) < 6:  # Need at least 3 points (6 coordinates)
            return None

        # Calculate bounding box
        xs = coords[0::2]
        ys = coords[1::2]

        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        position = Point(x=min_x, y=min_y)
        size = Dimensions(width=max_x - min_x, height=max_y - min_y)

        # Determine if it's a diamond (4 points = 8 coordinates)
        shape_type = "diamond" if len(coords) == 8 else "polygon"

        style = self._parse_style_attrs(elem)
        shape_id = elem.get("id") or self._generate_id()
        label = elem.get("data-label", "")

        shape = Shape(
            id=shape_id,
            label=label,
            shape_type=shape_type,
            position=position,
            size=size,
            style=style,
        )

        semantic_hint = elem.get("data-semantic")
        if semantic_hint:
            shape.semantic_type = self._parse_semantic_hint(semantic_hint)
            shape.semantic_confidence = 0.9
        else:
            shape.semantic_type, shape.semantic_confidence = infer_semantic_type(
                shape_type=shape_type,
                label=label,
                size=size,
                style=style,
            )

        # Store as string
        if shape.semantic_type:
            shape.semantic_type = shape.semantic_type.value

        return shape

    def _parse_text(self, elem: ET.Element, transform: Any | None) -> Text | None:
        """Parse SVG text to IR Text.

        Args:
            elem: text element
            transform: Transform matrix (not used in v1)

        Returns:
            Text or None if invalid
        """
        x = float(elem.get("x", 0))
        y = float(elem.get("y", 0))

        # Get text content
        content = "".join(elem.itertext()).strip()
        if not content:
            return None

        position = Point(x=x, y=y)

        # Estimate size based on font size and text length
        font_size = self._parse_font_size(elem)
        width = len(content) * font_size * 0.6  # Rough estimate
        height = font_size * 1.2

        size = Dimensions(width=width, height=height)
        style = self._parse_style_attrs(elem)
        style.font_size = font_size

        text_id = elem.get("id") or self._generate_id()

        return Text(
            id=text_id,
            content=content,
            position=position,
            size=size,
            style=style,
        )

    def _parse_group(
        self,
        elem: ET.Element,
        elements: list,
        transform: Any | None,
    ) -> Group | None:
        """Parse SVG group to IR Group.

        Args:
            elem: g element
            elements: List to append elements to
            transform: Transform matrix (not used in v1)

        Returns:
            Group or None if invalid
        """
        group_id = elem.get("id") or self._generate_id()

        # Collect child elements
        child_elements = []
        for child in elem:
            self._process_element(child, child_elements, transform, parent_id=group_id)

        child_ids = [e.id for e in child_elements]

        # Calculate bounding box
        if not child_elements:
            return None

        # Get bounds from shapes only
        shapes = [e for e in child_elements if isinstance(e, Shape)]
        if not shapes:
            # No shapes, just add children directly
            elements.extend(child_elements)
            return None

        min_x = min(s.position.x for s in shapes)
        min_y = min(s.position.y for s in shapes)
        max_x = max(s.position.x + s.size.width for s in shapes)
        max_y = max(s.position.y + s.size.height for s in shapes)

        position = Point(x=min_x, y=min_y)
        size = Dimensions(width=max_x - min_x, height=max_y - min_y)

        # Get label from data attribute
        label = elem.get("data-label", "")

        group = Group(
            id=group_id,
            label=label,
            position=position,
            size=size,
            children=child_ids,
        )

        elements.append(group)
        elements.extend(child_elements)

        return group

    def _parse_style_attrs(self, elem: ET.Element) -> Style:
        """Parse SVG style attributes to IR Style.

        Args:
            elem: SVG element

        Returns:
            Style object
        """
        fill = elem.get("fill")
        stroke = elem.get("stroke")
        stroke_width = elem.get("stroke-width")
        stroke_dasharray = elem.get("stroke-dasharray")

        # Parse style attribute if present
        style_str = elem.get("style", "")
        if style_str:
            style_dict = self._parse_style_string(style_str)
            fill = style_dict.get("fill", fill)
            stroke = style_dict.get("stroke", stroke)
            stroke_width = style_dict.get("stroke-width", stroke_width)
            stroke_dasharray = style_dict.get("stroke-dasharray", stroke_dasharray)

        return Style(
            fill_color=fill if fill and fill != "none" else None,
            stroke_color=stroke if stroke and stroke != "none" else None,
            stroke_width=float(stroke_width) if stroke_width else None,
            stroke_style="dashed" if stroke_dasharray else "solid",
        )

    def _parse_style_string(self, style_str: str) -> dict[str, str]:
        """Parse SVG style string to dict.

        Args:
            style_str: CSS-like style string

        Returns:
            Dictionary of style properties
        """
        result = {}
        for item in style_str.split(";"):
            if ":" in item:
                key, value = item.split(":", 1)
                result[key.strip()] = value.strip()
        return result

    def _parse_font_size(self, elem: ET.Element) -> float:
        """Extract font size from element.

        Args:
            elem: SVG element

        Returns:
            Font size in pixels
        """
        font_size = elem.get("font-size")
        if font_size:
            # Remove units (px, pt, etc.)
            return float("".join(c for c in font_size if c.isdigit() or c == ".") or "14")

        # Check style attribute
        style_str = elem.get("style", "")
        style_dict = self._parse_style_string(style_str)
        if "font-size" in style_dict:
            fs = style_dict["font-size"]
            return float("".join(c for c in fs if c.isdigit() or c == ".") or "14")

        return 14.0  # Default

    def _parse_semantic_hint(self, hint: str) -> SemanticType | None:
        """Parse semantic type from hint string.

        Args:
            hint: Semantic hint from data-semantic or class

        Returns:
            SemanticType or None
        """
        hint_lower = hint.lower()

        hint_map = {
            "database": SemanticType.DATABASE,
            "db": SemanticType.DATABASE,
            "person": SemanticType.PERSON,
            "user": SemanticType.PERSON,
            "actor": SemanticType.PERSON,
            "system": SemanticType.SYSTEM,
            "component": SemanticType.COMPONENT,
            "service": SemanticType.SERVICE,
            "container": SemanticType.CONTAINER,
            "queue": SemanticType.QUEUE,
            "storage": SemanticType.STORAGE,
            "external": SemanticType.EXTERNAL,
            "cloud": SemanticType.CLOUD,
        }

        return hint_map.get(hint_lower)

    def _associate_text_labels(self, elements: list) -> None:
        """Associate text elements with nearby shapes as labels.

        Args:
            elements: List of all elements
        """
        shapes = [e for e in elements if isinstance(e, Shape) and not e.label]
        texts = [e for e in elements if isinstance(e, Text)]

        for text in texts:
            # Find shapes that contain this text
            for shape in shapes:
                if self._point_in_shape(text.position, shape):
                    shape.label = text.content
                    break

    def _point_in_shape(self, point: Point, shape: Shape) -> bool:
        """Check if point is inside shape bounds.

        Args:
            point: Point to check
            shape: Shape to check against

        Returns:
            True if point is inside shape
        """
        return (
            shape.position.x <= point.x <= shape.position.x + shape.size.width
            and shape.position.y <= point.y <= shape.position.y + shape.size.height
        )

    def _generate_id(self) -> str:
        """Generate unique ID.

        Returns:
            Unique element ID
        """
        self._id_counter += 1
        return f"elem_{self._id_counter}"
