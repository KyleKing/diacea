# Ticket 005: API Refactoring

## Goal

Create a unified API/class structure for diacea. Consolidate experiment algorithms into converter classes with a clean, consistent interface.

## Current State

- Multiple standalone functions in `diacea/experiments.py`
- No unified API - users must import individual functions
- No configuration options
- Algorithms are separate functions, not organized into classes

## Requirements

1. Create `diacea/converter.py` with converter classes
2. Design unified API:
   ```python
   from diacea import ExcalidrawConverter
   
   converter = ExcalidrawConverter(algorithm='graph_based')
   result = converter.convert(excalidraw_data)
   plantuml = converter.to_plantuml(format='c4')
   ```
3. Support algorithm selection via constructor
4. Support output format selection (relative, basic PlantUML, C4-PlantUML)
5. Maintain backward compatibility with existing function API
6. Add configuration options:
   - Algorithm selection
   - Output format
   - C4 detection thresholds
   - Error handling mode

## Implementation Steps

1. **Create `Converter` base class**:
   ```python
   class ExcalidrawConverter:
       def __init__(self, algorithm='graph_based', format='c4'):
           ...
       def convert(self, excalidraw_data):
           ...
       def to_relative(self):
           ...
       def to_plantuml(self, format=None):
           ...
   ```
2. **Refactor algorithms** (optional - can wrap existing functions):
   - Keep existing functions for backward compatibility
   - Wrap in converter class methods
   - Or refactor into class methods
3. **Add configuration**:
   - Algorithm selection
   - Format selection
   - C4 detection parameters
4. **Update CLI** to use new API
5. **Add tests** for new API
6. **Update documentation** with API examples

## Acceptance Criteria

- [ ] Unified `ExcalidrawConverter` class exists
- [ ] All algorithms accessible via converter
- [ ] Can output relative format, basic PlantUML, or C4-PlantUML
- [ ] Backward compatibility maintained (existing functions still work)
- [ ] Configuration options work
- [ ] CLI uses new API
- [ ] Demo: Clean API usage examples work

## Demo

```python
from diacea import ExcalidrawConverter
import json

# Load data
with open('diagram.json') as f:
    data = json.load(f)

# Create converter
converter = ExcalidrawConverter(
    algorithm='graph_based',
    format='c4'
)

# Convert
result = converter.convert(data['elements'])

# Get different outputs
relative = converter.to_relative()
plantuml = converter.to_plantuml(format='c4')
basic = converter.to_plantuml(format='basic')

# All should work seamlessly
```

## API Design Options

### Option 1: Wrapper Class (Recommended)
- Keep existing functions
- Wrap in converter class
- Minimal changes, maintains compatibility

### Option 2: Full Refactor
- Move algorithms into class methods
- More organized but breaking changes
- Better for long-term maintenance

### Option 3: Hybrid
- Core algorithms stay as functions
- Converter class provides unified interface
- Best of both worlds

## Notes

- Prefer Option 1 or 3 for backward compatibility
- Consider adding `from_excalidraw_file()` and `to_plantuml_file()` convenience methods
- Add type hints throughout
- Consider using dataclasses for configuration

