# Ticket 001: Basic PlantUML Generation

## Goal

Port PlantUML generation from golang to Python. Convert the relative format output from existing algorithms to basic PlantUML syntax.

## Current State

- Python algorithms convert Excalidraw to relative format (rectangles, arrows, relationships)
- Golang code (`_golang/pkg/converter/converter.go`) generates PlantUML but is not integrated
- No Python code generates PlantUML output

## Requirements

1. Create new module `diacea/plantuml.py`
2. Implement function to convert relative format to basic PlantUML
3. Support basic elements:
   - Rectangles as `component` or `rectangle`
   - Arrows as `-->` relationships
   - Labels on relationships
4. Generate valid PlantUML syntax with `@startuml` and `@enduml` tags

## Implementation Steps

1. Create `diacea/plantuml.py` module
2. Implement `generate_plantuml(relative_data: list[dict]) -> str` function
3. Map relative format to PlantUML:
   - Rectangle with label → `component "Label" as Element_ID`
   - Arrow from→to → `Element_from --> Element_to : label`
   - Handle parent relationships (nested components)
4. Add basic tests in `tests/test_plantuml.py`
5. Test with existing `tests/data/excalidraw.json` data

## Acceptance Criteria

- [ ] Function converts relative format to valid PlantUML syntax
- [ ] All rectangles are converted to PlantUML components
- [ ] All arrows are converted to PlantUML relationships
- [ ] Labels are preserved on components and relationships
- [ ] Output can be rendered by PlantUML tools
- [ ] Tests pass with existing test data
- [ ] Demo: Convert `tests/data/excalidraw.json` to PlantUML and verify it renders

## Demo

```python
import json
from diacea.experiments import graph_based_approach
from diacea.plantuml import generate_plantuml

# Load and convert
with open('tests/data/excalidraw.json') as f:
    data = json.load(f)

relative = graph_based_approach(data['elements'])
plantuml = generate_plantuml(relative)

# Save and verify
with open('output.puml', 'w') as f:
    f.write(plantuml)

# Should produce valid PlantUML that can be rendered
```

## Notes

- Start with basic PlantUML syntax, not C4-PlantUML (that's ticket 002)
- Focus on correctness over features
- Reference golang implementation for logic but adapt to Python style
- Keep output simple and readable

