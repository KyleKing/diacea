# AI Agent Guide

This document provides AI assistants with an overview of the diacea codebase, its structure, and common development tasks.

## Project Overview

**diacea** is a universal diagram converter - the "pandoc for diagrams". It converts between visual diagram formats using a format-agnostic intermediate representation (IR).

**Supported Input Formats**: Excalidraw, Obsidian Excalidraw markdown, TLDraw (legacy and v2), SVG, Mermaid flowcharts, PlantUML (including C4 macros)
**Supported Output Formats**: PlantUML, C4-PlantUML, Mermaid, GraphViz DOT, D2

## Architecture

```
Input Formats          IR (Intermediate Repr)         Output Formats
-------------         ----------------------         --------------
Excalidraw  --+                                    +-- PlantUML
TLDraw      --+--> Diagram -> Elements -> Semantic +--> C4-PlantUML
SVG         --+         (with semantic types)      +--> Mermaid
                                                   +--> GraphViz DOT
                                                   +-- D2
```

## Codebase Structure

```
diacea/
├── diacea/
│   ├── __init__.py           # Package version
│   ├── cli.py                # Main CLI (convert, inspect, formats)
│   ├── ingestion.py          # Parse diagram files into workspace elements
│   ├── workspace_cli.py      # Workspace management CLI
│   ├── workspace_format.py   # Workspace file format (YAML)
│   ├── ir/                   # Intermediate Representation
│   │   ├── __init__.py       # IR exports
│   │   ├── base.py           # Parser/Generator base classes
│   │   ├── elements.py       # Core IR elements (Shape, Connection, etc.)
│   │   ├── semantic.py       # Semantic type inference
│   │   └── workspace.py      # Workspace IR classes
│   ├── parsers/              # Input format parsers
│   │   ├── __init__.py
│   │   ├── excalidraw.py     # Excalidraw JSON parser
│   │   ├── mermaid.py        # Mermaid flowchart text parser
│   │   ├── obsidian.py       # Obsidian .excalidraw.md extraction
│   │   ├── plantuml.py       # PlantUML/C4-PlantUML text parser
│   │   ├── svg.py            # SVG parser
│   │   └── tldraw.py         # TLDraw JSON parser (v1 and v2)
│   └── generators/           # Output format generators
│       ├── __init__.py
│       ├── _text.py          # Shared text helpers (ID sanitization)
│       ├── d2.py             # D2 diagrams
│       ├── graphviz.py       # GraphViz DOT format
│       ├── mermaid.py        # Mermaid diagrams
│       └── plantuml.py       # PlantUML and C4-PlantUML
├── tests/
│   ├── test_ir_integration.py    # IR and generator tests
│   ├── test_tldraw_parser.py     # TLDraw parser tests
│   ├── test_svg_parser.py        # SVG parser tests
│   ├── test_workspace.py         # Workspace tests
│   └── data/                     # Test fixtures
│       ├── excalidraw.json
│       └── svg/
└── docs/
```

## Key Modules

### IR (Intermediate Representation)

**`diacea/ir/elements.py`** - Core data structures:
- `Point`, `Dimensions`, `Style` - Basic geometry and styling
- `Element` - Base class for all diagram elements
- `Shape` - Rectangle, ellipse, diamond, etc.
- `Connection` - Arrows and lines between shapes
- `Text` - Standalone text elements
- `Group` - Container for grouped elements
- `Diagram` - Top-level container

**`diacea/ir/semantic.py`** - Semantic type inference:
- `SemanticType` enum (Person, System, Container, Database, etc.)
- `infer_semantic_type()` - Hybrid inference using shape, size, and text hints

### Parsers

All parsers implement the `Parser` base class with a `parse(data) -> Diagram` method.

- **`ExcalidrawParser`**: Parses Excalidraw JSON, extracts shapes/arrows/text, infers semantics
- **`parsers/obsidian.py`**: Detects Obsidian `.excalidraw.md` notes and extracts the embedded Excalidraw JSON (compressed blocks need the `diacea[obsidian]` extra)
- **`TLDrawParser`**: Parses TLDraw JSON (legacy v1 and v2 `.tldr`), handles multi-page documents
- **`SVGParser`**: Parses SVG XML, extracts shapes from rect/circle/ellipse/polygon/path elements
- **`MermaidParser`**: Parses Mermaid flowchart/graph text (bracket shapes, edges, subgraphs); rejects other Mermaid diagram types; synthesizes a layered layout since text has no coordinates
- **`PlantUMLParser`**: Parses PlantUML deployment/component elements, relationships, and the C4-PlantUML macro dialect; synthesizes layout; round-trips diacea's own PlantUML/C4 output exactly

Parsers expose a `warnings` list after `parse()` with any conversion losses detected (e.g. SVG curved outlines reduced to polygons); the CLI surfaces these.

### Generators

All generators implement the `Generator` base class with a `generate(diagram) -> str` method.

- **`PlantUMLGenerator`**: Basic PlantUML with components and relationships
- **`C4PlantUMLGenerator`**: C4-PlantUML with Person, System, Container elements
- **`MermaidGenerator`**: Mermaid flowcharts, C4, or sequence diagrams
- **`GraphVizGenerator`**: DOT format with clusters and configurable layout
- **`D2Generator`**: D2 diagrams with optional sketch mode

## CLI Usage

```bash
# Basic conversion
diacea -i diagram.json -f mermaid -o output.mmd

# With format-specific options
diacea -i diagram.json -f graphviz --graphviz-direction TB

# Auto-detect input format
diacea -i diagram.svg -f d2 --d2-sketch

# Pipe from stdin
cat diagram.json | diacea -i - -f c4
```

## CLI Usage for Agents

The conversion CLI is designed to be driven programmatically. Bare invocations (`diacea -i file -f mermaid`) are equivalent to the `convert` subcommand.

### JSON envelope

`--json` on conversion emits a machine-readable envelope to stdout instead of the bare converted text:

```json
{
  "output": "flowchart LR\n    ...",
  "input_format": "excalidraw",
  "output_format": "mermaid",
  "diagram_type": "flowchart",
  "elements": [
    {"id": "web", "label": "Web Server", "semantic_type": "service", "confidence": 0.8}
  ],
  "warnings": []
}
```

`diagram_type` is the Mermaid type that auto-detection chose (`flowchart`, `c4`, or `sequence`); it is `null` for other output formats. `warnings` lists known conversion losses detected at parse time (SVG curved outlines reduced to polygons, TLDraw pages skipped, dropped arrows). In text mode the same warnings print to stderr as `Warning: ...` lines.

### Preview and discovery

```bash
# Parse without converting: detected format, element count, per-element
# semantic inference with confidence
diacea inspect diagram.json --json

# List input formats (with detection method) and output formats (with options)
diacea formats --json
```

### Exit codes

- `0`: success
- `1`: error (file not found, unrecognized input format, parse/generation failure)
- `2`: the file parsed but produced 0 elements (likely an unsupported schema)

With `--json`, errors are written to stderr as JSON: `{"error": "...", "exit_code": 1}`. `inspect` reports 0 elements as a warning with exit code 0 so agents can still read the report.

## Data Flow

```
Input File (Excalidraw/TLDraw/SVG)
    ↓
Parser.parse() → Diagram IR
    ↓
Semantic inference (shape + text → semantic type)
    ↓
Generator.generate() → Output string
    ↓
Output File (PlantUML/Mermaid/GraphViz/D2)
```

## Development Workflow

### Running Tests

```bash
pytest                    # Run all tests
pytest tests/test_ir_integration.py  # Run specific test file
pytest -v                 # Verbose output
```

### Adding a New Input Format

1. Create `diacea/parsers/newformat.py`
2. Implement class extending `Parser` base class
3. Add to `diacea/parsers/__init__.py`
4. Add detection logic to `diacea/cli.py:detect_input_format()`
5. Add parser instantiation to `diacea/cli.py:main()`
6. Create tests in `tests/test_newformat_parser.py`

### Adding a New Output Format

1. Create `diacea/generators/newformat.py`
2. Implement class extending `Generator` base class
3. Add to `diacea/generators/__init__.py`
4. Add CLI arguments to `diacea/cli.py:create_parser()`
5. Add generator instantiation to `diacea/cli.py:main()`
6. Add tests to `tests/test_ir_integration.py`

### Adding a New Semantic Type

1. Add to `SemanticType` enum in `diacea/ir/semantic.py`
2. Add keywords to `SEMANTIC_KEYWORDS` dict
3. Add heuristics to `_infer_from_heuristics()` if needed
4. Update generators to handle new type

## Dependencies

**Runtime**:
- `networkx` - Graph operations
- `python-constraint2` - Constraint solving (for complex layouts)
- `corallium` - Utility functions
- `pyyaml` - Workspace file format

**Development**:
- `calcipy` - Development tooling (lint, test, docs)
- `pytest` - Testing framework

## Key Patterns

### Parser Pattern
```python
class MyParser(Parser):
    def parse(self, data: dict) -> Diagram:
        diagram = Diagram(name="...")
        for elem in data["elements"]:
            shape = self._parse_shape(elem)
            diagram.add_element(shape)
        return diagram
```

### Generator Pattern
```python
class MyGenerator(Generator):
    def generate(self, diagram: Diagram) -> str:
        lines = []
        for elem in diagram.elements:
            if isinstance(elem, Shape):
                lines.append(self._generate_shape(elem))
        return "\n".join(lines)
```

## Notes for AI Assistants

- **Follow existing patterns** - Parsers and generators have consistent structure
- **Use type hints** - The project uses beartype for runtime checking
- **Test thoroughly** - Add tests for new functionality
- **Preserve semantics** - IR should capture semantic meaning, not just visual layout
- **Handle edge cases** - Empty diagrams, missing labels, unsupported elements
