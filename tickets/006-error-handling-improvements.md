# Ticket 006: Error Handling Improvements

## Goal

Add comprehensive error handling throughout the codebase. Validate inputs, handle edge cases gracefully, and provide clear error messages.

## Current State

- No input validation - assumes valid Excalidraw JSON
- No error messages - fails with Python exceptions
- Edge cases may cause crashes
- No validation of element structure

## Requirements

1. **Input Validation**:
   - Validate Excalidraw JSON structure
   - Check required fields for each element type
   - Validate coordinate ranges
   - Check for missing or null values
2. **Error Classes**:
   - Create custom exception classes in `diacea/exceptions.py`
   - `InvalidExcalidrawError`: Invalid JSON structure
   - `MissingElementError`: Required element missing
   - `InvalidCoordinateError`: Invalid coordinates
   - `ConversionError`: Conversion failures
3. **Graceful Degradation**:
   - Continue processing when possible
   - Report issues without crashing
   - Option to fail fast or continue with warnings
4. **Clear Error Messages**:
   - User-friendly messages with context
   - Suggest fixes when possible
   - Include element IDs and types in errors
5. **Edge Case Handling**:
   - Empty diagrams
   - Missing elements
   - Invalid coordinates
   - Circular references
   - Orphaned elements

## Implementation Steps

1. **Create `diacea/exceptions.py`**:
   ```python
   class DiaceaError(Exception):
       """Base exception for diacea"""
   
   class InvalidExcalidrawError(DiaceaError):
       """Invalid Excalidraw JSON structure"""
   
   class MissingElementError(DiaceaError):
       """Required element missing"""
   
   # ... etc
   ```
2. **Add validation functions**:
   - `validate_excalidraw_json(data: dict) -> None`
   - `validate_element(element: dict, element_type: str) -> None`
   - `validate_coordinates(x: float, y: float, width: float, height: float) -> None`
3. **Update converter functions** to use validation
4. **Add error handling** in CLI
5. **Add tests** for error cases
6. **Update documentation** with error handling info

## Acceptance Criteria

- [ ] Custom exception classes exist
- [ ] Input validation catches invalid JSON
- [ ] Element validation catches missing fields
- [ ] Coordinate validation catches invalid values
- [ ] Error messages are clear and helpful
- [ ] Edge cases are handled gracefully
- [ ] Demo: Invalid inputs produce helpful error messages

## Demo

```python
from diacea import ExcalidrawConverter
from diacea.exceptions import InvalidExcalidrawError

# Invalid JSON structure
try:
    converter = ExcalidrawConverter()
    converter.convert({"invalid": "structure"})
except InvalidExcalidrawError as e:
    print(f"Error: {e}")
    # Should show: "Invalid Excalidraw JSON: missing 'elements' field"

# Missing required fields
try:
    converter.convert({"elements": [{"id": "123"}]})  # Missing 'type'
except MissingElementError as e:
    print(f"Error: {e}")
    # Should show: "Element '123' missing required field 'type'"

# Invalid coordinates
try:
    converter.convert({
        "elements": [{
            "id": "123",
            "type": "rectangle",
            "x": -1e10,  # Invalid
            "y": 0,
            "width": 100,
            "height": 100
        }]
    })
except InvalidCoordinateError as e:
    print(f"Error: {e}")
    # Should show helpful message about coordinate range
```

## Error Cases to Handle

1. **Invalid JSON**: Not valid JSON, wrong structure
2. **Missing Elements**: Required fields missing
3. **Invalid Types**: Element type not recognized
4. **Invalid Coordinates**: Out of range, NaN, infinity
5. **Missing Bindings**: Arrow without start/end binding
6. **Circular References**: Elements referencing each other
7. **Orphaned Elements**: Elements not connected to diagram
8. **Empty Diagram**: No elements in diagram

## Notes

- Consider adding `--strict` flag to CLI for fail-fast mode
- Default to graceful degradation (warn but continue)
- Log warnings for recoverable issues
- Provide `--verbose` flag for detailed error information
- Consider using `warnings` module for non-fatal issues

