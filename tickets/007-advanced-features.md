# Ticket 007: Advanced Features

## Goal

Add support for additional Excalidraw elements and improve conversion quality. Handle complex diagrams with advanced features.

## Current State

- Basic rectangle, text, and arrow support
- C4-PlantUML generation works
- Some edge cases and advanced features not supported

## Requirements

1. **Additional Element Support**:
   - Ellipses (beyond database detection)
   - Diamonds (beyond person detection)
   - Other shapes if present in Excalidraw
2. **Improved Arrow Handling**:
   - Better arrow label detection
   - Handle arrows with multiple points (curved arrows)
   - Detect arrow direction and style
3. **Nested System Boundaries**:
   - Handle deeply nested boundaries
   - Preserve hierarchy correctly
   - Support multiple levels of nesting
4. **Text Handling**:
   - Multi-line text support
   - Text outside rectangles (notes)
   - Text formatting preservation
5. **Layout Improvements**:
   - Better element positioning hints
   - Preserve spatial relationships where possible
   - Improve PlantUML layout directives

## Implementation Steps

1. **Extend element detection**:
   - Add support for additional Excalidraw element types
   - Map to appropriate PlantUML elements
2. **Improve arrow processing**:
   - Better label detection algorithm
   - Handle multi-point arrows
   - Detect arrow styles (dashed, dotted, etc.)
3. **Enhance system boundary detection**:
   - Improve nested boundary detection
   - Handle overlapping boundaries
   - Better text detection for boundaries
4. **Add text features**:
   - Convert standalone text to PlantUML notes
   - Preserve multi-line text
   - Handle text formatting
5. **Layout enhancements**:
   - Add PlantUML layout hints
   - Improve relationship positioning
   - Add spacing directives
6. **Add tests** for new features
7. **Update documentation** with new capabilities

## Acceptance Criteria

- [ ] Ellipses are handled beyond database detection
- [ ] Diamonds are handled beyond person detection
- [ ] Arrow labels are detected more accurately
- [ ] Multi-point arrows are handled
- [ ] Deeply nested system boundaries work correctly
- [ ] Standalone text becomes PlantUML notes
- [ ] Multi-line text is preserved
- [ ] Demo: Complex diagram with all features converts correctly

## Demo

```python
from diacea import ExcalidrawConverter

# Complex diagram with:
# - Multiple nested system boundaries
# - Various element types (rectangles, ellipses, diamonds)
# - Multi-point curved arrows
# - Standalone text notes
# - Multi-line labels

converter = ExcalidrawConverter(algorithm='graph_based', format='c4')
result = converter.convert(complex_diagram['elements'])
plantuml = converter.to_plantuml()

# Should handle all features correctly:
# - All element types converted
# - Nested boundaries preserved
# - Arrow labels detected
# - Text notes included
# - Layout is reasonable
```

## Specific Improvements

### Arrow Label Detection
- Current: Basic binding and proximity detection
- Improvement: 
  - Better proximity algorithm
  - Consider arrow midpoint
  - Handle labels on curved arrows
  - Support labels at different positions

### System Boundary Text
- Current: Looks for text in top 25% of rectangle
- Improvement:
  - Better text positioning detection
  - Handle multiple text candidates
  - Support text outside but associated with boundary

### Element Type Detection
- Current: Basic type mapping
- Improvement:
  - Shape-based detection (size, aspect ratio)
  - Text content analysis
  - Context-aware detection
  - User hints/configuration

### Layout Preservation
- Current: PlantUML auto-layouts
- Improvement:
  - Add `left to right direction` hints
  - Use `skinparam` for spacing
  - Preserve relative positions where possible
  - Add layout constraints

## Notes

- This is an enhancement ticket - core functionality should work first
- Focus on quality improvements over new features
- Consider user feedback for prioritization
- Some features may require PlantUML extensions
- Test with real-world complex diagrams

## Future Enhancements (Beyond This Ticket)

- Image element support
- Group element support
- Frame element support
- Custom styling preservation
- Bidirectional conversion (PlantUML → Excalidraw)
- Additional output formats (Mermaid, Graphviz)

