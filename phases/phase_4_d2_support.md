# Phase 4: D2 Output Support

## Goals

Add D2 diagram generation, targeting modern architecture diagrams with excellent layout and styling.

**Why D2:**
- Modern, actively developed (2022+)
- Excellent automatic layout engine
- Clean, human-readable syntax
- Strong styling capabilities
- Built-in support for connections, shapes, containers
- Good for architecture diagrams and documentation

## D2 Format Overview

### D2 Syntax Basics

**1. Simple Connections**
```d2
A -> B: connection label
B -> C
```

**2. Nested Containers**
```d2
system: System A {
  component1: Component 1
  component2: Component 2

  component1 -> component2
}
```

**3. Shapes and Styling**
```d2
database: Database {
  shape: cylinder
  style: {
    fill: lightblue
    stroke: blue
  }
}

user: User {
  shape: person
}

user -> database: queries
```

**4. Advanced Features**
```d2
# Directions
direction: right

# Icons
server: Server {
  icon: https://icons.example.com/server.svg
}

# Multiple connections
A -> B
A -> C
A -> D
```

## Technical Implementation

### D2 Generator

```python
# diacea/generators/d2.py

from dataclasses import dataclass, field
from typing import TextIO
from ..ir.elements import Diagram, Element, Connection, Group, Shape, Text
from ..ir.semantic import SemanticType
from .base import Generator


@dataclass
class D2Config:
    """Configuration for D2 generator."""

    direction: str | None = None  # up, down, left, right
    theme: str = "Neutral default"  # D2 theme ID
    sketch: bool = False  # Sketch mode
    use_icons: bool = False  # Use icon URLs
    icon_map: dict[SemanticType, str] = field(default_factory=dict)
    indent: str = "  "

    shape_map: dict[SemanticType, str] = None

    def __post_init__(self):
        if self.shape_map is None:
            self.shape_map = {
                SemanticType.DATABASE: "cylinder",
                SemanticType.PERSON: "person",
                SemanticType.QUEUE: "queue",
                SemanticType.STORAGE: "cylinder",
                SemanticType.DOCUMENT: "document",
                SemanticType.CLOUD: "cloud",
                SemanticType.HEXAGON: "hexagon",
                SemanticType.DECISION: "diamond",
                # Defaults to rectangle for others
            }


class D2Generator(Generator):
    """Generate D2 from IR."""

    def __init__(self, config: D2Config | None = None):
        self.config = config or D2Config()
        self._element_paths: dict[str, str] = {}  # id -> D2 path

    def generate(self, diagram: Diagram) -> str:
        """Generate complete D2 file."""
        lines = []

        # Direction
        if self.config.direction:
            lines.append(f"direction: {self.config.direction}")
            lines.append("")

        # Process groups first to establish hierarchy
        self._build_element_paths(diagram)

        # Write all elements
        self._write_elements(diagram, lines, level=0)

        # Write connections after all elements defined
        lines.append("")
        self._write_connections(diagram, lines)

        return "\n".join(lines)

    def _build_element_paths(self, diagram: Diagram) -> None:
        """Build D2 paths for all elements."""
        self._element_paths.clear()

        # Map elements to their groups
        child_to_parent: dict[str, str] = {}
        for elem in diagram.elements:
            if isinstance(elem, Group):
                for child_id in elem.children:
                    child_to_parent[child_id] = elem.id

        # Build paths
        def get_path(elem_id: str) -> str:
            if elem_id in child_to_parent:
                parent_id = child_to_parent[elem_id]
                parent_path = get_path(parent_id)
                sanitized_id = self._sanitize_id(elem_id)
                return f"{parent_path}.{sanitized_id}" if parent_path else sanitized_id
            else:
                return self._sanitize_id(elem_id)

        for elem in diagram.elements:
            self._element_paths[elem.id] = get_path(elem.id)

    def _write_elements(self, diagram: Diagram, lines: list[str], level: int) -> None:
        """Write all elements with proper nesting."""
        indent = self.config.indent * level

        # Write groups
        groups = [elem for elem in diagram.elements if isinstance(elem, Group)]
        for group in groups:
            self._write_group(group, diagram, lines, level)

        # Write standalone shapes (not in any group)
        grouped_ids = set()
        for group in groups:
            grouped_ids.update(group.children)

        standalone_shapes = [
            elem for elem in diagram.elements
            if isinstance(elem, Shape) and elem.id not in grouped_ids
        ]

        for shape in standalone_shapes:
            self._write_shape(shape, lines, level)

    def _write_group(self, group: Group, diagram: Diagram, lines: list[str], level: int) -> None:
        """Write a group as a D2 container."""
        indent = self.config.indent * level
        sanitized_id = self._sanitize_id(group.id)

        # Start container
        if group.label:
            lines.append(f"{indent}{sanitized_id}: {self._escape_label(group.label)} {{")
        else:
            lines.append(f"{indent}{sanitized_id} {{")

        # Write children
        for child_id in group.children:
            child = diagram.get_element(child_id)
            if child:
                if isinstance(child, Shape):
                    self._write_shape(child, lines, level + 1)
                elif isinstance(child, Group):
                    self._write_group(child, diagram, lines, level + 1)

        # Close container
        lines.append(f"{indent}}}")
        lines.append("")

    def _write_shape(self, shape: Shape, lines: list[str], level: int) -> None:
        """Write a shape element."""
        indent = self.config.indent * level
        sanitized_id = self._sanitize_id(shape.id)

        # Start definition
        if shape.label:
            line = f"{indent}{sanitized_id}: {self._escape_label(shape.label)}"
        else:
            line = f"{indent}{sanitized_id}"

        # Add inline shape if needed
        d2_shape = self._get_d2_shape(shape)
        has_style = self._has_custom_style(shape)
        has_icon = self.config.use_icons and self._get_icon_url(shape)

        if d2_shape or has_style or has_icon:
            lines.append(line + " {")

            if d2_shape:
                lines.append(f"{indent}{self.config.indent}shape: {d2_shape}")

            if has_icon:
                icon_url = self._get_icon_url(shape)
                lines.append(f"{indent}{self.config.indent}icon: {icon_url}")

            if has_style:
                self._write_style(shape, lines, level + 1)

            lines.append(f"{indent}}}")
        else:
            lines.append(line)

    def _write_style(self, shape: Shape, lines: list[str], level: int) -> None:
        """Write style block for a shape."""
        indent = self.config.indent * level
        style = shape.style

        style_props = []
        if style.fill_color:
            style_props.append(f"fill: {style.fill_color}")
        if style.stroke_color:
            style_props.append(f"stroke: {style.stroke_color}")
        if style.stroke_width:
            style_props.append(f"stroke-width: {style.stroke_width}")
        if style.stroke_style == "dashed":
            style_props.append("stroke-dash: 3")

        if style_props:
            lines.append(f"{indent}style: {{")
            for prop in style_props:
                lines.append(f"{indent}{self.config.indent}{prop}")
            lines.append(f"{indent}}}")

    def _write_connections(self, diagram: Diagram, lines: list[str]) -> None:
        """Write all connections."""
        connections = [elem for elem in diagram.elements if isinstance(elem, Connection)]

        for conn in connections:
            from_path = self._element_paths.get(conn.from_id)
            to_path = self._element_paths.get(conn.to_id)

            if not from_path or not to_path:
                continue  # Skip invalid connections

            # Build connection line
            arrow = self._get_arrow_type(conn)

            if conn.label:
                line = f"{from_path} {arrow} {to_path}: {self._escape_label(conn.label)}"
            else:
                line = f"{from_path} {arrow} {to_path}"

            # Add styling if needed
            if self._connection_has_style(conn):
                lines.append(line + " {")
                self._write_connection_style(conn, lines, level=1)
                lines.append("}")
            else:
                lines.append(line)

    def _write_connection_style(self, conn: Connection, lines: list[str], level: int) -> None:
        """Write style for connection."""
        indent = self.config.indent * level
        style = conn.style

        style_props = []
        if style.stroke_color:
            style_props.append(f"stroke: {style.stroke_color}")
        if style.stroke_width:
            style_props.append(f"stroke-width: {style.stroke_width}")
        if style.stroke_style == "dashed":
            style_props.append("stroke-dash: 3")

        if style_props:
            lines.append(f"{indent}style: {{")
            for prop in style_props:
                lines.append(f"{indent}{self.config.indent}{prop}")
            lines.append(f"{indent}}}")

    def _get_arrow_type(self, conn: Connection) -> str:
        """Get D2 arrow type."""
        if conn.connection_type == "bidirectional":
            return "<->"
        return "->"

    def _get_d2_shape(self, shape: Shape) -> str | None:
        """Get D2 shape name for element."""
        if shape.semantic_type:
            d2_shape = self.config.shape_map.get(shape.semantic_type)
            if d2_shape:
                return d2_shape

        # Map generic shapes
        shape_map = {
            "ellipse": "oval",
            "diamond": "diamond",
            "hexagon": "hexagon",
        }
        return shape_map.get(shape.shape_type)

    def _has_custom_style(self, shape: Shape) -> bool:
        """Check if shape has custom styling."""
        style = shape.style
        return bool(
            style.fill_color or
            style.stroke_color or
            style.stroke_width or
            style.stroke_style == "dashed"
        )

    def _connection_has_style(self, conn: Connection) -> bool:
        """Check if connection has custom styling."""
        style = conn.style
        return bool(
            style.stroke_color or
            style.stroke_width or
            style.stroke_style == "dashed"
        )

    def _get_icon_url(self, shape: Shape) -> str | None:
        """Get icon URL for semantic type."""
        if not self.config.use_icons or not shape.semantic_type:
            return None
        return self.config.icon_map.get(shape.semantic_type)

    def _sanitize_id(self, id_str: str) -> str:
        """Sanitize ID for D2 format."""
        # D2 allows hyphens and underscores
        # Replace spaces and special chars
        sanitized = id_str.replace(" ", "_").replace(":", "_")

        # Escape if starts with number
        if sanitized and sanitized[0].isdigit():
            sanitized = "n_" + sanitized

        return sanitized or "node"

    def _escape_label(self, label: str) -> str:
        """Escape label for D2 format."""
        # D2 handles most characters well, but escape special ones
        return label.replace("\\", "\\\\").replace("\n", "\\n")


# Convenience functions
def generate_d2(diagram: Diagram, config: D2Config | None = None) -> str:
    """Generate D2 from diagram IR."""
    generator = D2Generator(config)
    return generator.generate(diagram)


def generate_d2_to_file(
    diagram: Diagram,
    file: TextIO,
    config: D2Config | None = None,
) -> None:
    """Generate D2 to file."""
    d2_content = generate_d2(diagram, config)
    file.write(d2_content)
```

### Auto-Detection Logic

```python
# In diacea/generators/d2.py

def detect_optimal_direction(diagram: Diagram) -> str | None:
    """Detect optimal direction based on diagram layout."""
    shapes = [elem for elem in diagram.elements if isinstance(elem, Shape)]

    if not shapes:
        return None  # Let D2 decide

    # Calculate aspect ratio
    min_x = min(s.position.x for s in shapes)
    max_x = max(s.position.x + s.size.width for s in shapes)
    min_y = min(s.position.y for s in shapes)
    max_y = max(s.position.y + s.size.height for s in shapes)

    width = max_x - min_x
    height = max_y - min_y

    if width > height * 1.5:
        return "right"
    elif height > width * 1.5:
        return "down"

    return None  # Let D2 auto-layout
```

## CLI Integration

Update `diacea/cli.py`:

```python
parser.add_argument(
    '-f',
    '--format',
    default='c4',
    choices=['basic', 'c4', 'mermaid', 'graphviz', 'd2'],  # Add d2
    help='Output format',
)

parser.add_argument(
    '--d2-direction',
    default=None,
    choices=['up', 'down', 'left', 'right'],
    help='D2 layout direction (default: auto-detect)',
)

parser.add_argument(
    '--d2-sketch',
    action='store_true',
    help='Use D2 sketch mode',
)

# In main():
elif args.format == 'd2':
    from diacea.ir.parser import ExcalidrawParser
    from diacea.generators.d2 import (
        generate_d2,
        detect_optimal_direction,
        D2Config,
    )

    parser = ExcalidrawParser()
    diagram = parser.parse(elements)

    direction = args.d2_direction or detect_optimal_direction(diagram)
    config = D2Config(direction=direction, sketch=args.d2_sketch)
    output_content = generate_d2(diagram, config)
```

## New Tests

```python
# tests/test_d2.py

import pytest
from diacea.ir.elements import (
    Diagram,
    Shape,
    Connection,
    Group,
    Point,
    Dimensions,
    Style,
)
from diacea.ir.semantic import SemanticType
from diacea.generators.d2 import (
    generate_d2,
    D2Config,
    D2Generator,
    detect_optimal_direction,
)


class TestD2Basics:
    """Test basic D2 generation."""

    def test_simple_connection(self):
        """Test simple two-node connection."""
        diagram = Diagram(
            id="test",
            elements=[
                Shape(id="A", label="Node A", position=Point(0, 0), size=Dimensions(100, 50)),
                Shape(id="B", label="Node B", position=Point(200, 0), size=Dimensions(100, 50)),
                Connection(id="conn1", from_id="A", to_id="B", label="connects"),
            ],
        )

        d2 = generate_d2(diagram)

        assert "A: Node A" in d2
        assert "B: Node B" in d2
        assert "A -> B: connects" in d2

    def test_nested_containers(self):
        """Test nested container generation."""
        diagram = Diagram(
            id="test",
            elements=[
                Group(
                    id="system",
                    label="System",
                    children=["comp1", "comp2"],
                    position=Point(0, 0),
                    size=Dimensions(300, 200),
                ),
                Shape(
                    id="comp1",
                    label="Component 1",
                    position=Point(10, 10),
                    size=Dimensions(100, 50),
                ),
                Shape(
                    id="comp2",
                    label="Component 2",
                    position=Point(150, 10),
                    size=Dimensions(100, 50),
                ),
            ],
        )

        d2 = generate_d2(diagram)

        assert "system: System {" in d2
        assert "comp1: Component 1" in d2
        assert "comp2: Component 2" in d2
        assert "}" in d2

    def test_shapes(self):
        """Test different shape types."""
        diagram = Diagram(
            id="test",
            elements=[
                Shape(
                    id="db",
                    label="Database",
                    position=Point(0, 0),
                    size=Dimensions(100, 50),
                    semantic_type=SemanticType.DATABASE,
                ),
                Shape(
                    id="person",
                    label="User",
                    position=Point(200, 0),
                    size=Dimensions(100, 50),
                    semantic_type=SemanticType.PERSON,
                ),
            ],
        )

        d2 = generate_d2(diagram)

        assert "shape: cylinder" in d2
        assert "shape: person" in d2

    def test_styling(self):
        """Test style generation."""
        diagram = Diagram(
            id="test",
            elements=[
                Shape(
                    id="styled",
                    label="Styled",
                    position=Point(0, 0),
                    size=Dimensions(100, 50),
                    style=Style(fill_color="#ff0000", stroke_color="#00ff00"),
                ),
            ],
        )

        d2 = generate_d2(diagram)

        assert "style: {" in d2
        assert "fill: #ff0000" in d2
        assert "stroke: #00ff00" in d2

    def test_bidirectional_connection(self):
        """Test bidirectional arrows."""
        diagram = Diagram(
            id="test",
            elements=[
                Shape(id="A", label="A", position=Point(0, 0), size=Dimensions(50, 50)),
                Shape(id="B", label="B", position=Point(100, 0), size=Dimensions(50, 50)),
                Connection(
                    id="conn1",
                    from_id="A",
                    to_id="B",
                    connection_type="bidirectional",
                ),
            ],
        )

        d2 = generate_d2(diagram)

        assert "A <-> B" in d2

    def test_direction_config(self):
        """Test direction configuration."""
        diagram = Diagram(
            id="test",
            elements=[
                Shape(id="A", label="A", position=Point(0, 0), size=Dimensions(50, 50)),
            ],
        )

        config = D2Config(direction="down")
        d2 = generate_d2(diagram, config)

        assert "direction: down" in d2


class TestD2Integration:
    """Test integration scenarios."""

    def test_complex_hierarchy(self):
        """Test complex nested hierarchy."""
        diagram = Diagram(
            id="test",
            elements=[
                Group(
                    id="outer",
                    label="Outer System",
                    children=["inner", "comp"],
                    position=Point(0, 0),
                    size=Dimensions(400, 300),
                ),
                Group(
                    id="inner",
                    label="Inner System",
                    children=["deep"],
                    position=Point(10, 10),
                    size=Dimensions(180, 100),
                ),
                Shape(
                    id="deep",
                    label="Deep Component",
                    position=Point(20, 20),
                    size=Dimensions(80, 40),
                ),
                Shape(
                    id="comp",
                    label="Component",
                    position=Point(200, 20),
                    size=Dimensions(80, 40),
                ),
                Connection(id="conn", from_id="deep", to_id="comp"),
            ],
        )

        d2 = generate_d2(diagram)

        # Check nested structure
        assert "outer: Outer System {" in d2
        assert "inner: Inner System {" in d2
        # Connection should use full paths
        assert "->" in d2

    def test_end_to_end_excalidraw_to_d2(self, sample_excalidraw_data):
        """Test complete conversion from Excalidraw to D2."""
        from diacea.ir.parser import ExcalidrawParser

        parser = ExcalidrawParser()
        diagram = parser.parse(sample_excalidraw_data['elements'])

        d2 = generate_d2(diagram)

        # Should have valid D2 syntax
        assert "->" in d2 or ":" in d2
```

## Success Criteria

### Functional Requirements

- [ ] Generate valid D2 syntax
- [ ] Support nested containers
- [ ] Map semantic types to D2 shapes
- [ ] Support bidirectional connections
- [ ] Handle styling (fill, stroke, dash)
- [ ] Auto-detect layout direction
- [ ] Proper ID sanitization
- [ ] Label escaping

### Technical Requirements

- [ ] All tests pass (10+ test cases)
- [ ] Type hints throughout
- [ ] Follows generator pattern
- [ ] CLI integration working
- [ ] Documentation updated

### Quality Checks

- [ ] Generated D2 renders without errors
- [ ] Complex hierarchies work
- [ ] No path resolution issues
- [ ] Handles empty diagrams

## Migration Notes

No breaking changes - purely additive.

### CLI Usage

```bash
# Generate D2
diacea -i diagram.json -f d2 -o diagram.d2

# Specify direction
diacea -i diagram.json -f d2 --d2-direction down

# Sketch mode
diacea -i diagram.json -f d2 --d2-sketch

# Render with D2
diacea -i diagram.json -f d2 | d2 - diagram.svg
```

### Python API

```python
from diacea.ir.parser import ExcalidrawParser
from diacea.generators.d2 import generate_d2, D2Config

parser = ExcalidrawParser()
diagram = parser.parse(elements)

# Basic
d2_content = generate_d2(diagram)

# Custom config
config = D2Config(direction="right", sketch=True)
d2_content = generate_d2(diagram, config)
```

## Open Questions

1. **Icon Integration**: Should we provide default icon URLs for common semantic types?
   - Suggestion: Start without icons, add as optional feature

2. **Theme Support**: Should we support D2 theme selection?
   - Suggestion: Add as CLI flag later if requested

3. **Layout Preservation**: D2 supports position constraints - should we use them?
   - Suggestion: No, let D2 auto-layout for better results

## Estimated Effort

- Implementation: 1.5 weeks
- Testing: 0.5 weeks
- Documentation: 0.5 weeks
- **Total: 2.5 weeks**

## Dependencies

- Phase 1 (Rich IR) must be complete
- No new external dependencies (D2 CLI is for rendering, not required for generation)
