# Specification

This document describes what diacea does, its use cases, input/output formats, algorithms, and limitations.

## Purpose

diacea converts Excalidraw JSON exports to PlantUML diagrams, enabling:
- Version control of diagrams as text files
- Automated diagram generation
- Integration with documentation pipelines
- Conversion between visual and text-based diagram formats

## High-Level Use Cases

### Use Case 1: Convert Simple Excalidraw Diagram to PlantUML

**Input**: Excalidraw JSON with rectangles, text labels, and arrows

**Process**: 
1. Parse Excalidraw JSON structure
2. Convert absolute coordinates to relative relationships
3. Generate PlantUML syntax

**Output**: PlantUML `.puml` file

**Example**:
- Input: Excalidraw diagram with nested rectangles and connecting arrows
- Output: PlantUML diagram with container relationships and connections

### Use Case 2: Generate C4 Architecture Diagrams

**Input**: Excalidraw diagram with system boundaries, containers, and people

**Process**:
1. Detect system boundaries (large rectangles or specific text patterns)
2. Identify containers within boundaries
3. Map people (diamond shapes) to Person elements
4. Generate C4-PlantUML format

**Output**: C4-PlantUML diagram

**Example**:
- Input: Excalidraw diagram showing AWS Cloud, EKS cluster, and services
- Output: C4 Component diagram with System_Boundary, Container, and Person elements

### Use Case 3: Batch Conversion

**Input**: Multiple Excalidraw JSON files

**Process**: Process each file through the conversion pipeline

**Output**: Multiple PlantUML files

## Input Format

### Excalidraw JSON Structure

```json
{
  "type": "excalidraw/clipboard",
  "elements": [
    {
      "id": "unique-id",
      "type": "rectangle" | "text" | "arrow" | "ellipse" | "diamond",
      "x": 0.0,
      "y": 0.0,
      "width": 100.0,
      "height": 100.0,
      "text": "Label text",
      "points": [[x1, y1], [x2, y2]],  // For arrows
      "boundElements": [...],
      "startBinding": {...},
      "endBinding": {...},
      ...
    }
  ],
  "files": {}
}
```

### Key Element Types

- **rectangle**: Boxes, containers, system boundaries
- **text**: Labels, standalone text elements
- **arrow**: Connections between elements
- **ellipse**: Often used for databases
- **diamond**: Often used for people/users

## Output Format

### Relative Format (Current)

The Python algorithms currently output a relative format:

```python
[
  {
    "id": "rect-id",
    "type": "rectangle",
    "label": "Container Name",
    "parent": "parent-rect-id"  # Empty string if no parent
  },
  {
    "id": "arrow-id",
    "type": "arrow",
    "label": "",
    "from": "source-id",
    "to": "target-id"
  }
]
```

### PlantUML Format (Planned)

```plantuml
@startuml
!include https://raw.githubusercontent.com/plantuml-stdlib/C4-PlantUML/master/C4_Component.puml

LAYOUT_WITH_LEGEND()

System_Boundary(Element_abc123, "System Name") {
    Container(Element_def456, "Container Name")
}

Rel(Element_def456, Element_ghi789, "Label")

@enduml
```

## Algorithms

### 1. Imperative Approach (`convert_to_relative`)

**Strategy**: Sequential processing with explicit loops

**Steps**:
1. Sort rectangles by area (largest first)
2. For each rectangle:
   - Find contained text for label
   - Find smallest containing rectangle for parent
3. For each arrow:
   - Find nearest rectangles to start/end points
   - Create relationship

**Complexity**: O(n²) for rectangle containment checks

**Best For**: Simple diagrams, easy to understand

### 2. Rule-Based Approach (`rule_based_approach`)

**Strategy**: Apply rules in order

**Similar to**: Imperative but with clearer rule separation

**Best For**: When rules need to be easily modifiable

### 3. CSP Solver (`csp_solver`)

**Strategy**: Constraint Satisfaction Problem formulation

**Constraints**:
- Each text label can only be used once
- Parent must be a containing rectangle
- All rectangles must have valid parents

**Best For**: Complex diagrams with ambiguous relationships

**Limitations**: May not find solutions for all inputs

### 4. QuadTree Approach (`quadtree_approach`)

**Strategy**: Spatial indexing with QuadTree

**Steps**:
1. Build QuadTree from all elements
2. Query QuadTree for spatial relationships
3. Process rectangles and arrows using spatial queries

**Complexity**: O(n log n) average case

**Best For**: Large diagrams with many elements

### 5. Graph-Based Approach (`graph_based_approach`)

**Strategy**: NetworkX directed graph representation

**Steps**:
1. Create graph with all elements as nodes
2. Add edges for containment relationships
3. Add edges for text containment
4. Add edges for arrows
5. Generate output from graph structure

**Best For**: Complex relationships, graph analysis

**Advantages**: Can leverage graph algorithms for analysis

## Error Handling

### Current Limitations

1. **No Input Validation**: Assumes valid Excalidraw JSON structure
2. **No Error Messages**: Fails silently or with Python exceptions
3. **Missing Elements**: May fail if required fields are missing
4. **Invalid Coordinates**: No bounds checking

### Planned Error Handling

- **JSON Validation**: Verify Excalidraw JSON structure
- **Element Validation**: Check required fields for each element type
- **Coordinate Validation**: Ensure coordinates are within reasonable bounds
- **Clear Error Messages**: User-friendly error messages with context
- **Graceful Degradation**: Continue processing when possible, report issues

## Known Limitations

### Spatial Detection

1. **Overlapping Rectangles**: May incorrectly identify parent-child relationships
2. **Arrow Endpoints**: May not correctly identify target if arrow doesn't bind to element
3. **Text Positioning**: Text must be clearly within rectangle bounds
4. **Nested Boundaries**: Deep nesting may not be detected correctly

### Element Support

1. **Limited Shapes**: Currently focuses on rectangles, arrows, and text
2. **No Images**: Image elements are not supported
3. **No Groups**: Grouped elements are not handled specially
4. **No Frames**: Frame elements are ignored

### Output Format

1. **No PlantUML Generation**: Currently only outputs relative format
2. **No C4 Support**: C4-PlantUML format not yet implemented in Python
3. **No Styling**: Visual styling from Excalidraw is lost
4. **No Layout**: PlantUML layout is auto-generated, not preserved from Excalidraw

## Edge Cases

### Case 1: Empty Diagram

**Input**: Excalidraw JSON with no elements

**Expected**: Empty relative format array `[]`

**Status**: Should be handled gracefully

### Case 2: Orphaned Text

**Input**: Text element not contained in any rectangle

**Expected**: Text is ignored or becomes a note

**Status**: Currently ignored in relative format

### Case 3: Arrow Without Binding

**Input**: Arrow with no startBinding or endBinding

**Expected**: Use point coordinates to find nearest elements

**Status**: Handled by `find_nearest_rectangle()` function

### Case 4: Multiple Text Elements in Rectangle

**Input**: Rectangle containing multiple text elements

**Expected**: Use first text found or largest text

**Status**: Currently uses first text found

### Case 5: Circular Containment

**Input**: Rectangles that contain each other (shouldn't happen but possible)

**Expected**: Detect and report error, or use size to determine hierarchy

**Status**: Not currently detected

### Case 6: Arrow to Text Element

**Input**: Arrow pointing to a text element instead of rectangle

**Expected**: Find rectangle containing the text, or skip the relationship

**Status**: Currently may create invalid relationships

## Performance Considerations

- **Small Diagrams** (< 50 elements): All algorithms perform well
- **Medium Diagrams** (50-200 elements): Graph-based and QuadTree approaches preferred
- **Large Diagrams** (> 200 elements): QuadTree or optimized graph approach recommended

## Future Enhancements

1. **Bidirectional Conversion**: PlantUML to Excalidraw
2. **Additional Formats**: Mermaid, Graphviz, etc.
3. **Layout Preservation**: Maintain visual layout in text format
4. **Styling Support**: Preserve colors, line styles, etc.
5. **Interactive Mode**: Preview conversion before saving
6. **Batch Processing**: Convert multiple files at once
7. **Validation Mode**: Check diagram validity without conversion

