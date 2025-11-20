# AI Agent Guide

This document provides AI assistants with an overview of the diacea codebase, its structure, key algorithms, and common development tasks.

## Project Overview

**diacea** is a Python library that converts Excalidraw JSON exports to PlantUML diagrams. The project is in early development, with core conversion algorithms implemented but PlantUML generation still in progress.

**Key Goal**: Create a Python-only implementation that converts visual Excalidraw diagrams to text-based PlantUML format, enabling version control and automated diagram generation.

## Codebase Structure

```
diacea/
├── diacea/                    # Main package
│   ├── __init__.py            # Package exports and version
│   ├── experiments.py         # Core conversion algorithms (476 lines)
│   └── _runtime_type_check_setup.py  # Beartype runtime type checking
├── tests/                     # Test suite
│   ├── test_experiment.py     # Tests for all 5 algorithms
│   ├── test_zz_diacea.py      # Integration tests
│   └── data/
│       └── excalidraw.json    # Test fixture
├── scripts/                   # Utility scripts
│   └── check_imports.py       # Import validation
├── docs/                      # Documentation
│   ├── docs/                  # MkDocs documentation
│   └── notes/                 # Development notes
└── tickets/                   # Incremental project tickets
```

## Key Algorithms

All algorithms are in `diacea/experiments.py` and convert absolute Excalidraw coordinates to relative relationships.

### 1. `convert_to_relative()` - Imperative Approach
- **Lines**: 50-98
- **Strategy**: Sequential processing with explicit loops
- **Use Case**: Simple, straightforward conversion

### 2. `rule_based_approach()` - Rule-Based
- **Lines**: 106-154
- **Strategy**: Apply conversion rules in order
- **Use Case**: When rules need to be easily modifiable

### 3. `csp_solver()` - Constraint Satisfaction Problem
- **Lines**: 162-240
- **Strategy**: Formulate as CSP with constraints
- **Dependencies**: `python-constraint2` package
- **Use Case**: Complex diagrams with ambiguous relationships
- **Note**: May not find solutions for all inputs

### 4. `quadtree_approach()` - Spatial Indexing
- **Lines**: 248-385
- **Strategy**: QuadTree for efficient spatial queries
- **Classes**: `Rectangle`, `QuadTree`
- **Use Case**: Large diagrams with many elements
- **Complexity**: O(n log n) average case

### 5. `graph_based_approach()` - Graph Representation
- **Lines**: 393-475
- **Strategy**: NetworkX directed graph
- **Dependencies**: `networkx` package
- **Use Case**: Complex relationships, graph analysis
- **Helper**: `generate_output()` converts graph to relative format

### Shared Utilities

- `is_rectangle_inside()`: Check if one rectangle contains another
- `_dist()`: Calculate distance from point to rectangle center
- `find_nearest_rectangle()`: Find rectangle closest to a point

## Data Flow

```
Excalidraw JSON
    ↓
Parse elements (rectangles, text, arrows)
    ↓
Convert absolute coordinates to relative relationships
    ↓
Output relative format (current)
    ↓
Generate PlantUML (planned)
```

## Input Format

Excalidraw JSON structure:
```python
{
  "type": "excalidraw/clipboard",
  "elements": [
    {
      "id": str,
      "type": "rectangle" | "text" | "arrow" | ...,
      "x": float,
      "y": float,
      "width": float,  # For rectangles
      "height": float,  # For rectangles
      "text": str,  # For text elements
      "points": [[float, float], ...],  # For arrows
      "boundElements": [...],
      "startBinding": {...},
      "endBinding": {...}
    }
  ]
}
```

## Output Format

Current relative format:
```python
[
  {
    "id": str,
    "type": "rectangle",
    "label": str,
    "parent": str  # Empty string if no parent
  },
  {
    "id": str,
    "type": "arrow",
    "label": str,
    "from": str,
    "to": str
  }
]
```

## Development Workflow

### Running Tests

```bash
./run test
# or
poetry run pytest
```

### Code Quality

```bash
./run lint.fix  # Auto-fix linting issues
./run main      # Run full check suite
```

### Adding New Algorithm

1. Add function to `diacea/experiments.py`
2. Follow existing pattern (shared utilities, output format)
3. Add test case to `tests/test_experiment.py`
4. Ensure test passes with existing test data

### Adding PlantUML Generation

1. Create new module `diacea/plantuml.py` (already implemented)
2. Implement function to convert relative format to PlantUML
3. Add tests with expected PlantUML output
4. Support both basic PlantUML and C4-PlantUML formats

## Common Tasks

### Task: Add Support for New Element Type

1. Identify element type in Excalidraw JSON
2. Add detection logic in algorithm functions
3. Determine how to represent in relative format
4. Update all 5 algorithms for consistency
5. Add test cases

### Task: Improve Arrow Detection

Current: Uses `find_nearest_rectangle()` for arrow endpoints
Improvement: Better handling of arrow bindings, midpoint detection for labels

### Task: Add Error Handling

1. Validate Excalidraw JSON structure
2. Check required fields for each element type
3. Validate coordinate ranges
4. Provide clear error messages
5. Handle edge cases gracefully

### Task: Enhance PlantUML Generation

The Python implementation in `diacea/plantuml.py` includes:
- C4-PlantUML format generation (implemented)
- System boundary detection (size > 500 or text contains "cloud"/"eks")
- Person detection (diamond shapes)
- Database detection (ellipses or text contains "database")
- Arrow label detection (bound elements or nearby text)
- Nested system boundary handling
- Basic PlantUML format generation

Future enhancements can improve detection logic or add new element types.

## Testing Strategy

All algorithms are tested against the same input (`tests/data/excalidraw.json`) to ensure consistent output. The test validates:
- Correct rectangle identification
- Correct parent-child relationships
- Correct arrow connections
- Correct label assignment

Expected output is hardcoded in `tests/test_experiment.py` for regression testing.

## Dependencies

- **networkx**: Graph-based algorithm
- **python-constraint2**: CSP solver algorithm
- **corallium**: Utility functions
- **calcipy**: Development tooling (dev dependency)

## Key Files to Modify

1. **`diacea/experiments.py`**: Core algorithms (476 lines)
2. **`tests/test_experiment.py`**: Algorithm tests
3. **`diacea/__init__.py`**: Package exports (currently minimal)

## Planned Additions

1. **`diacea/plantuml.py`**: PlantUML generation (new file)
2. **`diacea/cli.py`**: Command-line interface (new file)
3. **`diacea/converter.py`**: Unified converter class (new file)

## Notes for AI Assistants

- **Don't modify `experiments.py` algorithms** unless fixing bugs - they're working implementations
- **Test all algorithms** when making changes - use `test_experiment.py` as reference
- **Follow existing patterns** - the codebase has consistent style
- **Maintain backward compatibility** - existing relative format output should continue working
- **Use type hints** - the project uses strict type checking
- **Run linting** - use `./run lint.fix` before committing
- **PlantUML generation** is in `diacea/plantuml.py` with both basic and C4 formats

## Quick Reference

**Run tests**: `./run test`
**Fix linting**: `./run lint.fix`
**Full check**: `./run main`
**Install deps**: `poetry install --sync`

**Test data location**: `tests/data/excalidraw.json`
**Main algorithms**: `diacea/experiments.py`
**PlantUML generation**: `diacea/plantuml.py`
**CLI interface**: `diacea/cli.py`

