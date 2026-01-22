# Phase 6: Basic SVG Input Parser

## Goals

Add limited SVG parsing support for basic geometric shapes, enabling import from vector drawing tools and other diagram sources.

**Why SVG:**
- Universal vector format
- Many tools export to SVG (Draw.io, Lucidchart, Visio, etc.)
- Can extract basic shapes even from complex diagrams
- Enables wider ecosystem integration

**Scope: Basic Shapes Only**
- Rectangle, ellipse, circle, polygon (limited)
- Text elements
- Simple groups
- Lines and polylines (as connections)
- **NOT** complex paths, gradients, filters, masks

## SVG Format Overview

### Supported SVG Elements

**1. Basic Shapes**
```xml
<svg xmlns="http://www.w3.org/2000/svg">
  <rect x="10" y="10" width="100" height="50" fill="blue" stroke="black"/>
  <circle cx="200" cy="35" r="30" fill="red"/>
  <ellipse cx="350" cy="35" rx="60" ry="30" fill="green"/>
  <polygon points="450,10 500,50 400,50" fill="yellow"/>
</svg>
```

**2. Text**
```xml
<text x="50" y="50" font-size="14" fill="black">Label Text</text>
```

**3. Lines/Connections**
```xml
<line x1="10" y1="10" x2="100" y2="50" stroke="black" stroke-width="2"/>
<polyline points="0,0 50,25 100,0" stroke="black" fill="none"/>
```

**4. Groups**
```xml
<g id="system1" transform="translate(100,100)">
  <rect width="200" height="100"/>
  <text x="10" y="20">System Name</text>
</g>
```

**5. Metadata for Semantic Hints**
```xml
<rect id="db1" class="database" data-semantic="database" .../>
<rect id="user1" data-semantic="person" .../>
```

## Technical Implementation

### SVG Parser

```python
# diacea/parsers/svg.py

from typing import Any
import xml.etree.ElementTree as ET
from ..ir.elements import (
    Diagram,
    Shape,
    Connection,
    Group,
    Text,
    Point,
    Dimensions,
    Style,
)
from ..ir.semantic import SemanticType, infer_semantic_type
from .base import Parser


class SVGParser(Parser):
    """Parse basic SVG to IR."""

    # SVG namespace
    SVG_NS = "{http://www.w3.org/2000/svg}"

    def __init__(self):
        self._id_counter = 0
        self._text_elements: dict[str, Text] = {}

    def parse(self, svg_content: str | ET.Element) -> Diagram:
        """Parse SVG content to IR diagram."""
        if isinstance(svg_content, str):
            root = ET.fromstring(svg_content)
        else:
            root = svg_content

        elements: list = []

        # Process all child elements
        self._process_element(root, elements, transform=None, parent_id=None)

        # Post-process: associate text with nearby shapes
        self._associate_text_labels(elements)

        return Diagram(
            id=root.get("id", "svg-diagram"),
            elements=elements,
        )

    def _process_element(
        self,
        elem: ET.Element,
        elements: list,
        transform: Any | None,
        parent_id: str | None,
    ) -> None:
        """Process SVG element recursively."""
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

        elif tag == "line":
            conn = self._parse_line(elem, transform)
            if conn:
                elements.append(conn)

        elif tag == "polyline":
            conn = self._parse_polyline(elem, transform)
            if conn:
                elements.append(conn)

        elif tag == "text":
            text = self._parse_text(elem, transform)
            if text:
                self._text_elements[text.id] = text
                elements.append(text)

        elif tag == "g":
            group = self._parse_group(elem, elements, transform)
            # Group processing adds children directly to elements

        # Process children
        for child in elem:
            self._process_element(child, elements, transform, parent_id)

    def _parse_rect(self, elem: ET.Element, transform: Any | None) -> Shape | None:
        """Parse SVG rect to IR Shape."""
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

        # Get label from data attribute or nearby text
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
            shape.semantic_confidence = 0.9  # High confidence from explicit hint
        else:
            shape.semantic_type, shape.semantic_confidence = infer_semantic_type(
                shape_type="rectangle",
                label=label,
                size=size,
                style=style,
            )

        return shape

    def _parse_circle(self, elem: ET.Element, transform: Any | None) -> Shape | None:
        """Parse SVG circle to IR Shape."""
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

        return shape

    def _parse_ellipse(self, elem: ET.Element, transform: Any | None) -> Shape | None:
        """Parse SVG ellipse to IR Shape."""
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

        return shape

    def _parse_polygon(self, elem: ET.Element, transform: Any | None) -> Shape | None:
        """Parse SVG polygon to IR Shape (simplified as diamond if 4 points)."""
        points_str = elem.get("points", "")
        if not points_str:
            return None

        # Parse points
        coords = [float(x) for x in points_str.replace(",", " ").split()]
        if len(coords) < 6:  # Need at least 3 points
            return None

        # Calculate bounding box
        xs = coords[0::2]
        ys = coords[1::2]

        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        position = Point(x=min_x, y=min_y)
        size = Dimensions(width=max_x - min_x, height=max_y - min_y)

        # Determine if it's a diamond (4 points)
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

        return shape

    def _parse_line(self, elem: ET.Element, transform: Any | None) -> Connection | None:
        """Parse SVG line to IR Connection (if it connects shapes)."""
        x1 = float(elem.get("x1", 0))
        y1 = float(elem.get("y1", 0))
        x2 = float(elem.get("x2", 0))
        y2 = float(elem.get("y2", 0))

        # We can't determine connections without shape binding info
        # For now, create a placeholder - will be resolved in post-processing
        conn_id = elem.get("id") or self._generate_id()
        style = self._parse_style_attrs(elem)

        # Store line endpoints for later connection resolution
        # This is a simplified approach - production code would need
        # spatial matching to find nearby shapes
        return None  # Skip for basic implementation

    def _parse_polyline(self, elem: ET.Element, transform: Any | None) -> Connection | None:
        """Parse SVG polyline (simplified)."""
        # Similar to line - would need connection resolution
        return None

    def _parse_text(self, elem: ET.Element, transform: Any | None) -> Text | None:
        """Parse SVG text to IR Text."""
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
        """Parse SVG group to IR Group."""
        group_id = elem.get("id") or self._generate_id()

        # Collect child IDs
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
        """Parse SVG style attributes to IR Style."""
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
        """Parse SVG style string to dict."""
        result = {}
        for item in style_str.split(";"):
            if ":" in item:
                key, value = item.split(":", 1)
                result[key.strip()] = value.strip()
        return result

    def _parse_font_size(self, elem: ET.Element) -> float:
        """Extract font size from element."""
        font_size = elem.get("font-size")
        if font_size:
            # Remove units (px, pt, etc.)
            return float("".join(c for c in font_size if c.isdigit() or c == "."))

        # Check style attribute
        style_str = elem.get("style", "")
        style_dict = self._parse_style_string(style_str)
        if "font-size" in style_dict:
            fs = style_dict["font-size"]
            return float("".join(c for c in fs if c.isdigit() or c == "."))

        return 14.0  # Default

    def _parse_semantic_hint(self, hint: str) -> SemanticType | None:
        """Parse semantic type from hint string."""
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
        }

        return hint_map.get(hint_lower)

    def _associate_text_labels(self, elements: list) -> None:
        """Associate text elements with nearby shapes as labels."""
        shapes = [e for e in elements if isinstance(e, Shape) and not e.label]
        texts = [e for e in elements if isinstance(e, Text)]

        for text in texts:
            # Find shapes that contain this text
            for shape in shapes:
                if self._point_in_shape(text.position, shape):
                    shape.label = text.content
                    break

    def _point_in_shape(self, point: Point, shape: Shape) -> bool:
        """Check if point is inside shape bounds."""
        return (
            shape.position.x <= point.x <= shape.position.x + shape.size.width
            and shape.position.y <= point.y <= shape.position.y + shape.size.height
        )

    def _generate_id(self) -> str:
        """Generate unique ID."""
        self._id_counter += 1
        return f"elem_{self._id_counter}"


# Convenience function
def parse_svg(svg_content: str | ET.Element) -> Diagram:
    """Parse SVG content to IR diagram."""
    parser = SVGParser()
    return parser.parse(svg_content)
```

## CLI Integration

```python
# Update diacea/cli.py

parser.add_argument(
    '--input-format',
    default='auto',
    choices=['auto', 'excalidraw', 'tldraw', 'svg'],
    help='Input format (default: auto-detect)',
)

# Detection
def detect_input_format(data: dict | str) -> str:
    """Detect input format."""
    if isinstance(data, str):
        # Check if it's XML/SVG
        if data.strip().startswith('<svg'):
            return 'svg'

    if isinstance(data, dict):
        if "document" in data and "pages" in data.get("document", {}):
            return "tldraw"
        if "elements" in data or data.get("type") == "excalidraw/clipboard":
            return "excalidraw"

    raise ValueError("Unknown input format")

# In main():
# Read file as text first to detect SVG
with open(args.input) as f:
    content = f.read()

if content.strip().startswith('<?xml') or content.strip().startswith('<svg'):
    input_format = 'svg'
    from diacea.parsers.svg import parse_svg
    diagram = parse_svg(content)
else:
    input_data = json.loads(content)
    # ... existing logic
```

## Tests

```python
# tests/test_svg_parser.py

import pytest
from diacea.parsers.svg import SVGParser, parse_svg
from diacea.ir.elements import Shape, Text, Group


class TestSVGParser:
    """Test SVG parser."""

    def test_parse_rectangle(self):
        """Test parsing SVG rectangle."""
        svg = '''
        <svg xmlns="http://www.w3.org/2000/svg">
            <rect id="rect1" x="10" y="20" width="100" height="50"
                  fill="blue" stroke="black" data-label="Component"/>
        </svg>
        '''

        diagram = parse_svg(svg)

        shapes = [e for e in diagram.elements if isinstance(e, Shape)]
        assert len(shapes) == 1
        assert shapes[0].id == "rect1"
        assert shapes[0].position.x == 10
        assert shapes[0].size.width == 100

    def test_parse_circle(self):
        """Test parsing SVG circle."""
        svg = '''
        <svg xmlns="http://www.w3.org/2000/svg">
            <circle cx="100" cy="100" r="50" fill="red"/>
        </svg>
        '''

        diagram = parse_svg(svg)

        shapes = [e for e in diagram.elements if isinstance(e, Shape)]
        assert len(shapes) == 1
        assert shapes[0].shape_type == "ellipse"
        assert shapes[0].size.width == 100  # diameter

    def test_semantic_hints(self):
        """Test semantic type hints."""
        svg = '''
        <svg xmlns="http://www.w3.org/2000/svg">
            <rect x="0" y="0" width="100" height="50" data-semantic="database"/>
            <circle cx="200" cy="25" r="25" data-semantic="person"/>
        </svg>
        '''

        diagram = parse_svg(svg)

        shapes = [e for e in diagram.elements if isinstance(e, Shape)]
        assert len(shapes) == 2

        from diacea.ir.semantic import SemanticType
        db_shape = shapes[0]
        assert db_shape.semantic_type == SemanticType.DATABASE

        person_shape = shapes[1]
        assert person_shape.semantic_type == SemanticType.PERSON

    def test_text_association(self):
        """Test text label association with shapes."""
        svg = '''
        <svg xmlns="http://www.w3.org/2000/svg">
            <rect id="r1" x="0" y="0" width="100" height="50"/>
            <text x="20" y="30">Label Text</text>
        </svg>
        '''

        diagram = parse_svg(svg)

        shapes = [e for e in diagram.elements if isinstance(e, Shape)]
        assert len(shapes) == 1
        assert shapes[0].label == "Label Text"

    def test_group_parsing(self):
        """Test SVG group parsing."""
        svg = '''
        <svg xmlns="http://www.w3.org/2000/svg">
            <g id="system1" data-label="System">
                <rect id="comp1" x="10" y="10" width="80" height="40"/>
                <rect id="comp2" x="100" y="10" width="80" height="40"/>
            </g>
        </svg>
        '''

        diagram = parse_svg(svg)

        groups = [e for e in diagram.elements if isinstance(e, Group)]
        assert len(groups) == 1
        assert groups[0].label == "System"
        assert len(groups[0].children) == 2
```

## Success Criteria

- [ ] Parse basic SVG shapes (rect, circle, ellipse, polygon)
- [ ] Parse text elements
- [ ] Parse groups
- [ ] Support semantic hints (data-semantic attribute)
- [ ] Associate text labels with shapes
- [ ] Parse SVG style attributes
- [ ] Handle malformed SVG gracefully
- [ ] All tests pass (8+ test cases)

## Open Questions

1. **Path Support**: Should we attempt to parse simple SVG paths?
   - Suggestion: Not for v1, too complex

2. **Transform Support**: Should we apply SVG transform matrices?
   - Suggestion: Basic translate only, skip rotate/scale for v1

3. **Connection Detection**: How to detect connections from lines?
   - Suggestion: Spatial analysis to find nearest shapes, but low priority

## Estimated Effort

- Implementation: 1.5 weeks
- Testing: 0.5 weeks
- Documentation: 0.5 weeks
- **Total: 2.5 weeks**

## Dependencies

- Phase 1 (Rich IR) must be complete
- Python standard library only (xml.etree.ElementTree)
