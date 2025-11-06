# Ticket 002: C4-PlantUML Support

## Goal

Add C4-PlantUML format support, including System_Boundary, Container, Person, and ComponentDb elements. Port the golang C4 detection logic to Python.

## Current State

- Basic PlantUML generation exists (ticket 001)
- Golang code has C4-PlantUML generation logic
- Python code doesn't distinguish between element types for C4 model

## Requirements

1. Extend `diacea/plantuml.py` with C4-PlantUML support
2. Detect element types from Excalidraw:
   - **System Boundaries**: Large rectangles (width > 500 or height > 500) or text contains "cloud"/"eks"
   - **People**: Diamond shapes (`type == "diamond"`)
   - **Databases**: Ellipses (`type == "ellipse"`) or text contains "database"
   - **Containers**: Regular rectangles within system boundaries
3. Generate C4-PlantUML syntax:
   - `System_Boundary(Element_ID, "Label") { ... }`
   - `Person(Element_ID, "Label")`
   - `Container(Element_ID, "Label")`
   - `ComponentDb(Element_ID, "Label")`
   - `Rel(Element_ID1, Element_ID2, "Label")`
4. Include C4-PlantUML library: `!include https://raw.githubusercontent.com/plantuml-stdlib/C4-PlantUML/master/C4_Component.puml`
5. Handle nested system boundaries

## Implementation Steps

1. Add C4 detection functions:
   - `is_system_boundary(element: dict, all_elements: list) -> bool`
   - `is_person(element: dict) -> bool`
   - `is_database(element: dict) -> bool`
2. Modify PlantUML generation to use C4 syntax
3. Process system boundaries first (largest to smallest)
4. Nest containers within boundaries
5. Generate relationships with `Rel()` syntax
6. Add tests with complex diagram (use `_golang/excalidraw.pretty.json` as reference)

## Acceptance Criteria

- [ ] System boundaries are detected correctly
- [ ] People (diamonds) are converted to Person elements
- [ ] Databases (ellipses) are converted to ComponentDb
- [ ] Containers are nested within system boundaries
- [ ] Nested system boundaries are handled correctly
- [ ] Relationships use C4 `Rel()` syntax
- [ ] Output includes C4-PlantUML library include
- [ ] Demo: Convert complex Excalidraw diagram to C4-PlantUML and verify rendering

## Demo

```python
import json
from diacea.experiments import graph_based_approach
from diacea.plantuml import generate_c4_plantuml

# Load complex diagram
with open('_golang/excalidraw.pretty.json') as f:
    data = json.load(f)

relative = graph_based_approach(data['elements'])
c4_plantuml = generate_c4_plantuml(relative, data['elements'])

# Should produce C4-PlantUML with System_Boundary, Person, Container, etc.
```

## Notes

- Reference `_golang/pkg/converter/converter.go` lines 37-183 for detection logic
- System boundaries are sorted by size (largest first)
- Text detection for boundaries looks for text in top 25% of rectangle
- Arrow labels are detected from bound elements or nearby text (lines 194-269 in golang code)

