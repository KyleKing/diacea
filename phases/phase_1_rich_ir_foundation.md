# Phase 1: Rich IR Foundation & Refactoring

## Goals

Create a comprehensive Intermediate Representation (IR) that can represent any diagram format, and refactor existing code to use it.

## Strategic Decisions

### 1. Semantic Inference Approach: **Hybrid (Rules + Hints)**

**Rationale:**
- **ML**: Too heavy for v1, requires training data, model maintenance
- **Pure Rules**: Brittle, hard to maintain, many edge cases
- **Hybrid (CHOSEN)**:
  - Start with rule-based heuristics (80% of cases)
  - Support user hints/annotations (10% of cases)
  - Leave door open for ML enhancement (future 10%)

**Implementation:**
```python
# Priority order:
1. Explicit user hints (metadata/annotations)
2. Strong heuristics (size thresholds, shape types)
3. Text-based hints ("database", "system", etc.)
4. Fallback to generic types
```

### 2. Scope: **Diagram DSLs First, Limited SVG**

**In Scope:**
- PlantUML (basic + C4) ✅
- Mermaid (flowchart, sequence, C4)
- GraphViz/DOT
- D2
- Structurizr DSL
- Simple SVG (basic shapes only, no complex paths)

**Out of Scope (for now):**
- Complex SVG (paths, masks, filters)
- PDF/EPS
- Proprietary formats (Visio, etc.)
- Image formats (PNG, JPEG)

## Technical Implementation

### IR Module Structure

```
diacea/ir/
├── __init__.py           # Public IR API
├── core.py               # Core IR classes
├── semantic.py           # Semantic type definitions
├── geometry.py           # Geometric utilities
├── validation.py         # IR validation
└── builder.py            # IR builder pattern
```

### Core IR Classes

```python
# diacea/ir/core.py

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

@dataclass
class Point:
    """2D point."""
    x: float
    y: float

@dataclass
class Dimensions:
    """2D dimensions."""
    width: float
    height: float

@dataclass
class Style:
    """Visual styling."""
    stroke_color: Optional[str] = None
    stroke_width: Optional[float] = None
    fill_color: Optional[str] = None
    opacity: Optional[float] = None
    font_size: Optional[float] = None
    font_family: Optional[str] = None

class ElementType(Enum):
    """Base element types."""
    SHAPE = "shape"
    CONNECTION = "connection"
    TEXT = "text"
    GROUP = "group"

class ShapeType(Enum):
    """Shape geometries."""
    RECTANGLE = "rectangle"
    CIRCLE = "circle"
    ELLIPSE = "ellipse"
    DIAMOND = "diamond"
    POLYGON = "polygon"
    PATH = "path"  # For complex SVG paths

class ConnectionType(Enum):
    """Connection types."""
    ARROW = "arrow"
    LINE = "line"
    BIDIRECTIONAL = "bidirectional"
    CURVE = "curve"

@dataclass
class Element:
    """Base IR element."""
    id: str
    element_type: ElementType
    position: Point
    size: Dimensions
    style: Style = field(default_factory=Style)
    metadata: dict = field(default_factory=dict)

    # Semantic hints (user-provided or inferred)
    semantic_type: Optional[str] = None  # e.g., "system", "person", "database"
    semantic_confidence: float = 0.0  # 0.0-1.0 confidence in semantic type

@dataclass
class Shape(Element):
    """Shape element."""
    shape_type: ShapeType
    vertices: Optional[list[Point]] = None  # For polygons

    def __post_init__(self):
        self.element_type = ElementType.SHAPE

@dataclass
class Connection(Element):
    """Connection between elements."""
    from_id: str
    to_id: str
    connection_type: ConnectionType
    points: list[Point] = field(default_factory=list)  # Waypoints
    label: Optional[str] = None

    def __post_init__(self):
        self.element_type = ElementType.CONNECTION

@dataclass
class Text(Element):
    """Text element."""
    content: str
    bound_to: Optional[str] = None  # ID of element this text is bound to

    def __post_init__(self):
        self.element_type = ElementType.TEXT

@dataclass
class Group(Element):
    """Group of elements (container, boundary, layer)."""
    children: list[str] = field(default_factory=list)  # Child element IDs
    group_type: Optional[str] = None  # "boundary", "container", "layer"

    def __post_init__(self):
        self.element_type = ElementType.GROUP

@dataclass
class Diagram:
    """Complete diagram IR."""
    elements: list[Element] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    # Computed indices for fast lookup
    _element_index: dict[str, Element] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self):
        self._rebuild_index()

    def _rebuild_index(self):
        """Build element lookup index."""
        self._element_index = {elem.id: elem for elem in self.elements}

    def get_element(self, id: str) -> Optional[Element]:
        """Get element by ID."""
        return self._element_index.get(id)

    def add_element(self, element: Element):
        """Add element to diagram."""
        self.elements.append(element)
        self._element_index[element.id] = element

    def get_shapes(self) -> list[Shape]:
        """Get all shape elements."""
        return [e for e in self.elements if isinstance(e, Shape)]

    def get_connections(self) -> list[Connection]:
        """Get all connection elements."""
        return [e for e in self.elements if isinstance(e, Connection)]

    def get_texts(self) -> list[Text]:
        """Get all text elements."""
        return [e for e in self.elements if isinstance(e, Text)]

    def get_groups(self) -> list[Group]:
        """Get all group elements."""
        return [e for e in self.elements if isinstance(e, Group)]
```

### Semantic Type Definitions

```python
# diacea/ir/semantic.py

from enum import Enum

class SemanticType(Enum):
    """Common semantic types across diagram formats."""

    # C4 Model
    SYSTEM = "system"
    SYSTEM_BOUNDARY = "system_boundary"
    CONTAINER = "container"
    COMPONENT = "component"
    PERSON = "person"
    DATABASE = "database"

    # Flowchart
    PROCESS = "process"
    DECISION = "decision"
    START_END = "start_end"
    DATA = "data"

    # Sequence Diagram
    ACTOR = "actor"
    LIFELINE = "lifeline"
    ACTIVATION = "activation"

    # Generic
    BOX = "box"
    NOTE = "note"
    LABEL = "label"

    # Unknown
    UNKNOWN = "unknown"

class SemanticInference:
    """Semantic type inference using heuristics."""

    @staticmethod
    def infer_from_shape(
        shape_type: ShapeType,
        size: Dimensions,
        text: str = "",
        metadata: dict = None
    ) -> tuple[SemanticType, float]:
        """
        Infer semantic type from shape characteristics.

        Returns:
            (semantic_type, confidence) where confidence is 0.0-1.0
        """
        metadata = metadata or {}
        text_lower = text.lower()

        # Explicit hints (highest confidence)
        if hint := metadata.get('semantic_type'):
            return SemanticType(hint), 1.0

        # Strong heuristics (high confidence)
        if shape_type == ShapeType.DIAMOND:
            if 'decision' in text_lower or 'if' in text_lower:
                return SemanticType.DECISION, 0.9
            return SemanticType.PERSON, 0.8

        if shape_type == ShapeType.ELLIPSE:
            if 'database' in text_lower or 'db' in text_lower:
                return SemanticType.DATABASE, 0.9
            return SemanticType.DATABASE, 0.6

        if shape_type == ShapeType.RECTANGLE:
            # Large rectangles are likely boundaries
            if size.width > 500 or size.height > 500:
                if 'system' in text_lower or 'cloud' in text_lower or 'eks' in text_lower:
                    return SemanticType.SYSTEM_BOUNDARY, 0.9
                return SemanticType.SYSTEM_BOUNDARY, 0.7

            # Text-based hints
            if 'database' in text_lower:
                return SemanticType.DATABASE, 0.8
            if 'person' in text_lower or 'user' in text_lower:
                return SemanticType.PERSON, 0.7
            if 'system' in text_lower:
                return SemanticType.SYSTEM, 0.7

            # Default rectangle
            return SemanticType.CONTAINER, 0.5

        # Fallback
        return SemanticType.UNKNOWN, 0.0
```

### Parser Interface

```python
# diacea/parsers/base.py

from abc import ABC, abstractmethod
from pathlib import Path
from diacea.ir import Diagram

class BaseParser(ABC):
    """Base parser interface."""

    @abstractmethod
    def parse(self, source: Path | str | dict) -> Diagram:
        """
        Parse source into IR.

        Args:
            source: File path, JSON string, or dict

        Returns:
            Diagram IR
        """
        pass

    @abstractmethod
    def can_parse(self, source: Path | str) -> bool:
        """Check if this parser can handle the source."""
        pass

    @property
    @abstractmethod
    def format_name(self) -> str:
        """Name of the format this parser handles."""
        pass
```

### Generator Interface

```python
# diacea/generators/base.py

from abc import ABC, abstractmethod
from pathlib import Path
from diacea.ir import Diagram

class BaseGenerator(ABC):
    """Base generator interface."""

    @abstractmethod
    def generate(self, diagram: Diagram) -> str:
        """
        Generate output from IR.

        Args:
            diagram: Diagram IR

        Returns:
            Generated output as string
        """
        pass

    @abstractmethod
    def write(self, diagram: Diagram, output: Path):
        """Write generated output to file."""
        content = self.generate(diagram)
        output.write_text(content)

    @property
    @abstractmethod
    def format_name(self) -> str:
        """Name of the format this generator produces."""
        pass
```

### Refactor Existing Code

**1. Create ExcalidrawParser:**
```python
# diacea/parsers/excalidraw.py

from diacea.parsers.base import BaseParser
from diacea.ir import Diagram, Shape, Connection, Text, ShapeType, ConnectionType
from diacea.ir.semantic import SemanticInference
# ... implementation
```

**2. Create PlantUMLGenerator:**
```python
# diacea/generators/plantuml.py

from diacea.generators.base import BaseGenerator
from diacea.ir import Diagram
# ... move current plantuml.py logic here
```

**3. Update Converter:**
```python
# diacea/converter.py

class DiagramConverter:
    """Unified converter with fluent API."""

    def __init__(self):
        self._parsers = {}
        self._generators = {}
        self._diagram: Optional[Diagram] = None

    def register_parser(self, parser: BaseParser):
        """Register input parser."""
        self._parsers[parser.format_name] = parser

    def register_generator(self, generator: BaseGenerator):
        """Register output generator."""
        self._generators[generator.format_name] = generator

    def from_file(self, path: Path, format: str = None) -> 'DiagramConverter':
        """Load from file."""
        if format:
            parser = self._parsers[format]
        else:
            parser = self._auto_detect_parser(path)

        self._diagram = parser.parse(path)
        return self

    def to_file(self, path: Path, format: str) -> 'DiagramConverter':
        """Write to file."""
        generator = self._generators[format]
        generator.write(self._diagram, path)
        return self

    def to_string(self, format: str) -> str:
        """Generate to string."""
        generator = self._generators[format]
        return generator.generate(self._diagram)

    @property
    def ir(self) -> Diagram:
        """Access IR directly."""
        return self._diagram
```

## New Tests

### 1. IR Core Tests
```python
# tests/test_ir_core.py

def test_point_creation()
def test_dimensions_creation()
def test_style_defaults()
def test_shape_creation()
def test_connection_creation()
def test_text_creation()
def test_group_creation()
def test_diagram_add_element()
def test_diagram_get_element()
def test_diagram_filtering()
```

### 2. Semantic Inference Tests
```python
# tests/test_semantic_inference.py

def test_explicit_hint_highest_priority()
def test_diamond_inferred_as_person()
def test_ellipse_inferred_as_database()
def test_large_rectangle_as_boundary()
def test_text_hints_database()
def test_text_hints_system()
def test_confidence_scores()
def test_unknown_fallback()
```

### 3. Parser Tests
```python
# tests/parsers/test_excalidraw_parser.py

def test_parse_rectangles_to_shapes()
def test_parse_arrows_to_connections()
def test_parse_text_elements()
def test_semantic_inference_integration()
def test_parse_bound_elements()
def test_parse_groups()
```

### 4. Generator Tests
```python
# tests/generators/test_plantuml_generator.py

def test_generate_from_ir()
def test_c4_format_generation()
def test_basic_format_generation()
def test_semantic_types_to_c4()
```

### 5. Integration Tests
```python
# tests/test_integration.py

def test_excalidraw_to_plantuml_via_ir()
def test_ir_roundtrip_excalidraw()
def test_converter_fluent_api()
```

## Success Criteria

### Functional

1. **IR Completeness**
   - ✅ Can represent all Excalidraw elements
   - ✅ Can represent semantic types (C4, flowchart)
   - ✅ Preserves geometric and style information
   - ✅ Supports text binding and grouping

2. **Semantic Inference**
   - ✅ 90%+ accuracy on common patterns
   - ✅ Confidence scores working correctly
   - ✅ Explicit hints override heuristics

3. **Refactoring**
   - ✅ All existing tests pass
   - ✅ No regression in PlantUML output quality
   - ✅ Code organized in new structure

4. **API Usability**
   - ✅ Fluent API works as designed
   - ✅ Parser/Generator interfaces clean
   - ✅ Easy to add new formats

### Technical

1. **Performance**
   - IR creation: <100ms for 100 elements
   - Semantic inference: <1ms per element
   - No memory leaks

2. **Code Quality**
   - Type hints 100%
   - Docstrings for all public APIs
   - Linting passes
   - Test coverage >80%

3. **Backward Compatibility**
   - Old API still works (deprecated warnings)
   - CLI unchanged from user perspective
   - Existing test data works

## Open Questions

### 1. IR Versioning Strategy?

**Options:**
- A) Include version field in Diagram metadata
- B) Semantic versioning for IR module
- C) No versioning (breaking changes in major versions)

**Recommendation:** B - Semantic versioning for IR module

### 2. How to Handle Unknown Shapes?

**Options:**
- A) Fail hard (raise exception)
- B) Convert to generic "box" with low confidence
- C) Store raw geometry, pass through

**Recommendation:** B for semantic, C for geometry preservation

### 3. IR Serialization Format?

**Options:**
- A) JSON (human-readable, web-friendly)
- B) MessagePack (compact, fast)
- C) Both (JSON for debug, MessagePack for production)

**Recommendation:** A (JSON) - focus on clarity over performance

### 4. Style Normalization?

**Options:**
- A) Normalize all colors to hex
- B) Keep original format
- C) Convert to semantic names where possible

**Recommendation:** A - normalize to hex for consistency

### 5. Coordinate System?

**Options:**
- A) Keep original (varies by format)
- B) Normalize to top-left origin
- C) Normalize to center origin

**Recommendation:** B - top-left origin (standard for most formats)

## Migration Strategy

### Phase 1a: Create IR (Week 1)
- Implement IR classes
- Write IR tests
- No integration yet

### Phase 1b: Refactor Excalidraw Parser (Week 1-2)
- Create ExcalidrawParser
- Migrate existing logic
- Maintain old API as facade

### Phase 1c: Refactor PlantUML Generator (Week 2)
- Create PlantUMLGenerator
- Migrate existing logic
- Add C4 semantic mapping

### Phase 1d: Create Converter (Week 2)
- Implement DiagramConverter
- Wire up parser and generator
- Update CLI to use converter

### Phase 1e: Testing & Documentation (Week 2-3)
- Comprehensive test suite
- Update DEVELOPER.md
- Add IR specification document

## Files to Create

```
diacea/ir/__init__.py
diacea/ir/core.py
diacea/ir/semantic.py
diacea/ir/geometry.py
diacea/ir/validation.py
diacea/ir/builder.py

diacea/parsers/__init__.py
diacea/parsers/base.py
diacea/parsers/excalidraw.py

diacea/generators/__init__.py
diacea/generators/base.py
diacea/generators/plantuml.py

diacea/converter.py

tests/test_ir_core.py
tests/test_semantic_inference.py
tests/parsers/test_excalidraw_parser.py
tests/generators/test_plantuml_generator.py
tests/test_converter.py
tests/test_integration.py

docs/IR_SPECIFICATION.md
```

## Estimated Effort

- **Development**: 2-3 weeks
- **Testing**: 1 week
- **Documentation**: 0.5 week
- **Total**: 3.5-4.5 weeks

## Risk Assessment

**Low Risk:**
- IR design (well-defined problem)
- Refactoring (existing tests validate)

**Medium Risk:**
- Semantic inference accuracy
- Performance with large diagrams

**Mitigation:**
- Start with simple heuristics, iterate
- Profile early, optimize as needed
- Keep old code path during transition
