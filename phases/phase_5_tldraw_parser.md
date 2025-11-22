# Phase 5: TLDraw Input Parser

## Goals

Add TLDraw as a second input format, expanding beyond Excalidraw to support another popular diagramming tool.

**Why TLDraw:**
- Modern, actively developed infinite canvas
- Similar to Excalidraw but with different feature set
- Good API and JSON structure
- Growing user base
- Open source

## TLDraw Format Overview

### TLDraw JSON Structure

```json
{
  "document": {
    "id": "doc",
    "name": "My Diagram",
    "version": 15.5,
    "pages": {
      "page-id": {
        "id": "page-id",
        "name": "Page 1",
        "childIndex": 1,
        "shapes": {
          "shape-1": {
            "id": "shape-1",
            "type": "rectangle",
            "name": "Rectangle",
            "point": [100, 100],
            "size": [200, 100],
            "style": {
              "color": "black",
              "size": "medium",
              "isFilled": true
            },
            "label": "My Component"
          },
          "shape-2": {
            "id": "shape-2",
            "type": "arrow",
            "name": "Arrow",
            "point": [300, 150],
            "handles": {
              "start": {
                "id": "start",
                "point": [0, 0],
                "bindingId": "binding-1"
              },
              "end": {
                "id": "end",
                "point": [100, 0],
                "bindingId": "binding-2"
              }
            }
          }
        },
        "bindings": {
          "binding-1": {
            "id": "binding-1",
            "fromId": "shape-2",
            "toId": "shape-1",
            "handleId": "start"
          }
        }
      }
    }
  }
}
```

### Key Differences from Excalidraw

| Feature | Excalidraw | TLDraw |
|---------|------------|--------|
| Shape types | Limited set | Extensive (rectangle, ellipse, arrow, text, draw, etc.) |
| Coordinates | Absolute x, y | Point array [x, y] |
| Bindings | boundElements | Separate bindings object |
| Grouping | groupIds | Parent-child hierarchy |
| Styling | Inline | Structured style object |
| Multi-page | No | Yes (pages object) |

## Technical Implementation

### TLDraw Parser

```python
# diacea/parsers/tldraw.py

from typing import Any
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


class TLDrawParser(Parser):
    """Parse TLDraw JSON to IR."""

    def parse(self, tldraw_data: dict[str, Any]) -> Diagram:
        """Parse TLDraw document to IR diagram."""
        elements: list = []

        # TLDraw has pages - we'll process the first page for now
        pages = tldraw_data.get("document", {}).get("pages", {})

        if not pages:
            return Diagram(id="empty", elements=[])

        # Get first page
        first_page_id = next(iter(pages.keys()))
        page = pages[first_page_id]

        shapes = page.get("shapes", {})
        bindings = page.get("bindings", {})

        # Parse shapes first
        shape_map: dict[str, Shape | Group | Text] = {}
        for shape_id, shape_data in shapes.items():
            parsed = self._parse_shape(shape_id, shape_data)
            if parsed:
                elements.append(parsed)
                shape_map[shape_id] = parsed

        # Parse arrows/connections
        for shape_id, shape_data in shapes.items():
            if shape_data.get("type") == "arrow":
                conn = self._parse_arrow(shape_id, shape_data, bindings)
                if conn:
                    elements.append(conn)

        return Diagram(
            id=page.get("id", "diagram"),
            name=page.get("name"),
            elements=elements,
        )

    def _parse_shape(self, shape_id: str, shape_data: dict) -> Shape | Group | Text | None:
        """Parse a TLDraw shape to IR element."""
        shape_type = shape_data.get("type")

        # Skip arrows - handled separately
        if shape_type == "arrow":
            return None

        # Get position
        point = shape_data.get("point", [0, 0])
        position = Point(x=point[0], y=point[1])

        # Get size
        size_data = shape_data.get("size", [100, 100])
        size = Dimensions(width=size_data[0], height=size_data[1])

        # Get label
        label = shape_data.get("label", shape_data.get("name", ""))

        # Parse style
        style = self._parse_style(shape_data.get("style", {}))

        # Determine shape type
        ir_shape_type = self._map_shape_type(shape_type)

        # Check if it's a group
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

        return shape

    def _parse_arrow(
        self,
        arrow_id: str,
        arrow_data: dict,
        bindings: dict,
    ) -> Connection | None:
        """Parse TLDraw arrow to IR connection."""
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

        return Connection(
            id=arrow_id,
            from_id=from_id,
            to_id=to_id,
            label=label,
            connection_type=connection_type,
            style=style,
        )

    def _parse_style(self, style_data: dict) -> Style:
        """Parse TLDraw style to IR style."""
        # TLDraw uses named colors and sizes, need to map them
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

        size_map = {
            "small": 2,
            "medium": 3,
            "large": 5,
        }

        color = style_data.get("color", "black")
        stroke_color = color_map.get(color, "#000000")

        size = style_data.get("size", "medium")
        stroke_width = size_map.get(size, 3)

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

    def _map_shape_type(self, tldraw_type: str) -> str:
        """Map TLDraw shape type to IR shape type."""
        type_map = {
            "rectangle": "rectangle",
            "ellipse": "ellipse",
            "triangle": "triangle",
            "diamond": "diamond",
            "text": "text",
            "draw": "freehand",
            "sticky": "note",
        }
        return type_map.get(tldraw_type, "rectangle")


# Convenience function
def parse_tldraw(tldraw_data: dict[str, Any]) -> Diagram:
    """Parse TLDraw data to IR diagram."""
    parser = TLDrawParser()
    return parser.parse(tldraw_data)
```

### Multi-Page Support

```python
# Extension for multi-page support

class TLDrawMultiPageParser(TLDrawParser):
    """Parse all pages from TLDraw document."""

    def parse_all_pages(self, tldraw_data: dict[str, Any]) -> list[Diagram]:
        """Parse all pages to separate diagrams."""
        pages = tldraw_data.get("document", {}).get("pages", {})

        diagrams = []
        for page_id, page_data in pages.items():
            # Create modified structure with single page
            single_page_data = {
                "document": {
                    "id": tldraw_data["document"]["id"],
                    "pages": {page_id: page_data},
                }
            }

            diagram = self.parse(single_page_data)
            diagrams.append(diagram)

        return diagrams
```

## CLI Integration

Update `diacea/cli.py`:

```python
parser.add_argument(
    '-i',
    '--input',
    required=True,
    help='Input file (Excalidraw or TLDraw JSON)',
)

parser.add_argument(
    '--input-format',
    default='auto',
    choices=['auto', 'excalidraw', 'tldraw'],
    help='Input format (default: auto-detect)',
)

# Detection logic
def detect_input_format(data: dict) -> str:
    """Detect input format from JSON structure."""
    # TLDraw has "document" -> "pages" structure
    if "document" in data and "pages" in data.get("document", {}):
        return "tldraw"

    # Excalidraw has "elements" or "type": "excalidraw/clipboard"
    if "elements" in data or data.get("type") == "excalidraw/clipboard":
        return "excalidraw"

    raise ValueError("Unknown input format")

# In main():
with open(args.input) as f:
    input_data = json.load(f)

# Detect or use specified format
if args.input_format == 'auto':
    input_format = detect_input_format(input_data)
else:
    input_format = args.input_format

# Parse based on format
if input_format == 'tldraw':
    from diacea.parsers.tldraw import parse_tldraw
    elements_key = None  # TLDraw parser handles full document
    diagram = parse_tldraw(input_data)
elif input_format == 'excalidraw':
    from diacea.ir.parser import ExcalidrawParser
    elements = input_data.get('elements', [])
    parser = ExcalidrawParser()
    diagram = parser.parse(elements)
```

## New Tests

```python
# tests/test_tldraw_parser.py

import pytest
from diacea.parsers.tldraw import TLDrawParser, parse_tldraw
from diacea.ir.elements import Shape, Connection, Group


class TestTLDrawParser:
    """Test TLDraw parser."""

    def test_parse_simple_shape(self):
        """Test parsing simple rectangle."""
        tldraw_data = {
            "document": {
                "pages": {
                    "page1": {
                        "id": "page1",
                        "shapes": {
                            "rect1": {
                                "id": "rect1",
                                "type": "rectangle",
                                "point": [100, 100],
                                "size": [200, 100],
                                "label": "My Component",
                                "style": {
                                    "color": "blue",
                                    "isFilled": True,
                                },
                            }
                        },
                        "bindings": {},
                    }
                }
            }
        }

        diagram = parse_tldraw(tldraw_data)

        assert len(diagram.elements) == 1
        shape = diagram.elements[0]
        assert isinstance(shape, Shape)
        assert shape.label == "My Component"
        assert shape.position.x == 100
        assert shape.position.y == 100
        assert shape.size.width == 200
        assert shape.size.height == 100

    def test_parse_arrow_with_bindings(self):
        """Test parsing arrow with bindings."""
        tldraw_data = {
            "document": {
                "pages": {
                    "page1": {
                        "id": "page1",
                        "shapes": {
                            "rect1": {
                                "id": "rect1",
                                "type": "rectangle",
                                "point": [0, 0],
                                "size": [100, 50],
                                "label": "A",
                            },
                            "rect2": {
                                "id": "rect2",
                                "type": "rectangle",
                                "point": [200, 0],
                                "size": [100, 50],
                                "label": "B",
                            },
                            "arrow1": {
                                "id": "arrow1",
                                "type": "arrow",
                                "point": [100, 25],
                                "handles": {
                                    "start": {"id": "start", "bindingId": "bind1"},
                                    "end": {"id": "end", "bindingId": "bind2"},
                                },
                                "label": "connects",
                            },
                        },
                        "bindings": {
                            "bind1": {
                                "id": "bind1",
                                "fromId": "arrow1",
                                "toId": "rect1",
                            },
                            "bind2": {
                                "id": "bind2",
                                "fromId": "arrow1",
                                "toId": "rect2",
                            },
                        },
                    }
                }
            }
        }

        diagram = parse_tldraw(tldraw_data)

        # Should have 2 shapes and 1 connection
        shapes = [e for e in diagram.elements if isinstance(e, Shape)]
        connections = [e for e in diagram.elements if isinstance(e, Connection)]

        assert len(shapes) == 2
        assert len(connections) == 1

        conn = connections[0]
        assert conn.from_id == "rect1"
        assert conn.to_id == "rect2"
        assert conn.label == "connects"

    def test_parse_group(self):
        """Test parsing grouped shapes."""
        tldraw_data = {
            "document": {
                "pages": {
                    "page1": {
                        "id": "page1",
                        "shapes": {
                            "group1": {
                                "id": "group1",
                                "type": "group",
                                "point": [0, 0],
                                "size": [300, 200],
                                "label": "System",
                                "children": ["child1", "child2"],
                            },
                            "child1": {
                                "id": "child1",
                                "type": "rectangle",
                                "point": [10, 10],
                                "size": [100, 50],
                                "label": "Component 1",
                            },
                            "child2": {
                                "id": "child2",
                                "type": "rectangle",
                                "point": [150, 10],
                                "size": [100, 50],
                                "label": "Component 2",
                            },
                        },
                        "bindings": {},
                    }
                }
            }
        }

        diagram = parse_tldraw(tldraw_data)

        groups = [e for e in diagram.elements if isinstance(e, Group)]
        assert len(groups) == 1
        assert groups[0].label == "System"
        assert len(groups[0].children) == 2

    def test_style_parsing(self):
        """Test style conversion."""
        tldraw_data = {
            "document": {
                "pages": {
                    "page1": {
                        "id": "page1",
                        "shapes": {
                            "rect1": {
                                "id": "rect1",
                                "type": "rectangle",
                                "point": [0, 0],
                                "size": [100, 50],
                                "style": {
                                    "color": "red",
                                    "size": "large",
                                    "isFilled": True,
                                    "dash": "dashed",
                                },
                            }
                        },
                        "bindings": {},
                    }
                }
            }
        }

        diagram = parse_tldraw(tldraw_data)

        shape = diagram.elements[0]
        assert shape.style.stroke_color == "#ff0000"
        assert shape.style.fill_color == "#ff0000"
        assert shape.style.stroke_width == 5
        assert shape.style.stroke_style == "dashed"

    def test_empty_document(self):
        """Test parsing empty document."""
        tldraw_data = {"document": {"pages": {}}}

        diagram = parse_tldraw(tldraw_data)

        assert len(diagram.elements) == 0


class TestTLDrawCLI:
    """Test TLDraw CLI integration."""

    def test_auto_detect_tldraw(self):
        """Test auto-detection of TLDraw format."""
        from diacea.cli import detect_input_format

        tldraw_data = {"document": {"pages": {}}}
        format_type = detect_input_format(tldraw_data)
        assert format_type == "tldraw"

    def test_auto_detect_excalidraw(self):
        """Test auto-detection of Excalidraw format."""
        from diacea.cli import detect_input_format

        excalidraw_data = {"elements": []}
        format_type = detect_input_format(excalidraw_data)
        assert format_type == "excalidraw"


# Fixture
@pytest.fixture
def sample_tldraw_architecture():
    """Sample TLDraw architecture diagram."""
    return {
        "document": {
            "id": "doc1",
            "pages": {
                "page1": {
                    "id": "page1",
                    "name": "Architecture",
                    "shapes": {
                        "user": {
                            "id": "user",
                            "type": "ellipse",
                            "point": [50, 50],
                            "size": [80, 80],
                            "label": "User",
                        },
                        "system": {
                            "id": "system",
                            "type": "rectangle",
                            "point": [300, 50],
                            "size": [500, 400],
                            "label": "System",
                            "children": ["api", "db"],
                            "style": {"color": "blue", "isFilled": False},
                        },
                        "api": {
                            "id": "api",
                            "type": "rectangle",
                            "point": [350, 100],
                            "size": [150, 100],
                            "label": "API",
                        },
                        "db": {
                            "id": "db",
                            "type": "cylinder",
                            "point": [550, 100],
                            "size": [120, 100],
                            "label": "Database",
                        },
                        "arrow1": {
                            "id": "arrow1",
                            "type": "arrow",
                            "point": [130, 90],
                            "handles": {
                                "start": {"bindingId": "b1"},
                                "end": {"bindingId": "b2"},
                            },
                            "label": "uses",
                        },
                        "arrow2": {
                            "id": "arrow2",
                            "type": "arrow",
                            "point": [500, 150],
                            "handles": {
                                "start": {"bindingId": "b3"},
                                "end": {"bindingId": "b4"},
                            },
                            "label": "queries",
                        },
                    },
                    "bindings": {
                        "b1": {"fromId": "arrow1", "toId": "user"},
                        "b2": {"fromId": "arrow1", "toId": "api"},
                        "b3": {"fromId": "arrow2", "toId": "api"},
                        "b4": {"fromId": "arrow2", "toId": "db"},
                    },
                }
            },
        }
    }
```

## Success Criteria

### Functional Requirements

- [ ] Parse TLDraw JSON to IR
- [ ] Handle shapes, arrows, groups
- [ ] Convert bindings to connections
- [ ] Map TLDraw styles to IR styles
- [ ] Support text elements
- [ ] Auto-detect TLDraw format
- [ ] Handle empty/malformed documents

### Technical Requirements

- [ ] All tests pass (10+ test cases)
- [ ] Type hints throughout
- [ ] Follows parser pattern
- [ ] CLI integration with auto-detection
- [ ] Documentation updated

### Quality Checks

- [ ] Works with real TLDraw exports
- [ ] No data loss in conversion
- [ ] Handles edge cases gracefully

## Migration Notes

No breaking changes - adds new input format.

### CLI Usage

```bash
# Auto-detect format
diacea -i tldraw_diagram.tldr -o output.puml

# Explicit format
diacea -i diagram.tldr --input-format tldraw -f c4

# Works with all output formats
diacea -i diagram.tldr -f mermaid
diacea -i diagram.tldr -f graphviz
diacea -i diagram.tldr -f d2
```

### Python API

```python
from diacea.parsers.tldraw import parse_tldraw
from diacea.generators.mermaid import generate_mermaid

# Load TLDraw file
with open('diagram.tldr') as f:
    tldraw_data = json.load(f)

# Parse to IR
diagram = parse_tldraw(tldraw_data)

# Generate any output format
mermaid = generate_mermaid(diagram)
```

## Open Questions

1. **Multi-Page Handling**: Should we process all pages or just the first?
   - Suggestion: First page by default, add flag for all pages later

2. **TLDraw Extensions**: TLDraw supports custom shapes - how should we handle them?
   - Suggestion: Map unknown types to generic rectangle, log warning

3. **Version Compatibility**: TLDraw format has changed over versions - which should we support?
   - Suggestion: Support latest stable (v15+), add version detection

4. **Draw/Freehand Elements**: How should we handle freehand drawings?
   - Suggestion: Skip for now, they don't map well to structured diagrams

## Estimated Effort

- Implementation: 1 week
- Testing: 0.5 weeks
- Documentation: 0.5 weeks
- **Total: 2 weeks**

## Dependencies

- Phase 1 (Rich IR) must be complete
- No new external dependencies
