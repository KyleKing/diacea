# AI Agent Guide

This document provides AI assistants with an overview of the diacea codebase, its structure, and common development tasks.

## Project Overview

**diacea** is a universal diagram converter - the "pandoc for diagrams". It converts between visual diagram formats using a format-agnostic intermediate representation (IR).

**Supported Input Formats**: Excalidraw, Obsidian Excalidraw markdown, TLDraw (legacy and v2), SVG, Mermaid (flowchart, sequence, C4), PlantUML (including C4 and icon-library macros), GraphViz DOT, D2

**Supported Output Formats**: PlantUML, C4-PlantUML, Mermaid, GraphViz DOT, D2, Excalidraw, SVG

Every text format diacea writes it also reads, so any input converts to any output and a conversion can be verified by parsing its output back.

## Architecture

```
Input Formats            IR (Intermediate Repr)          Output Formats
-------------           ----------------------          --------------
Excalidraw    --+                                     +--> Mermaid
TLDraw        --+                                     +--> PlantUML
SVG           --+                                     +--> C4-PlantUML
Mermaid       --+--> Diagram -> Elements -> Semantic --+--> GraphViz DOT
PlantUML / C4 --+        (with semantic types)        +--> D2
GraphViz DOT  --+                                     +--> Excalidraw
D2            --+                                     +--> SVG
```

`diacea/formats.py` is the single registry of formats and the pipeline built on it (`parse_diagram` -> `render_diagram`, or `convert`). The CLI, `diacea sync`, workspace ingestion, and the MkDocs plugin all go through it; none of them names a parser or generator class.

## Codebase Structure

````
diacea/
├── diacea/
│   ├── __init__.py           # Package version
│   ├── cli.py                # Main CLI (convert, inspect, formats, sync); argument handling only
│   ├── formats.py            # Format registry + pipeline: detect, parse, hints, render, convert, verify
│   ├── layout.py             # Compound layered layout for diagrams without coordinates
│   ├── ingestion.py          # Parse diagram files into workspace elements
│   ├── markdown_fences.py    # Replace ```diacea fences with generated diagram blocks
│   ├── mkdocs_plugin.py      # MkDocs plugin wrapping markdown_fences (diacea[mkdocs] extra)
│   ├── workspace_cli.py      # Workspace management CLI
│   ├── workspace_format.py   # Workspace file format (YAML)
│   ├── ir/                   # Intermediate Representation
│   │   ├── __init__.py       # IR exports
│   │   ├── base.py           # Parser/Generator base classes
│   │   ├── elements.py       # Core IR elements (Shape, Connection, etc.)
│   │   ├── ids.py            # Readable ids for sources with tool-generated ones
│   │   ├── semantic.py       # Semantic type inference
│   │   └── workspace.py      # Workspace IR classes
│   ├── parsers/              # Input format parsers
│   │   ├── __init__.py
│   │   ├── d2.py             # D2 text parser
│   │   ├── excalidraw.py     # Excalidraw JSON parser
│   │   ├── graphviz.py       # GraphViz DOT parser
│   │   ├── mermaid.py        # Mermaid flowchart/sequence text parser
│   │   ├── obsidian.py       # Obsidian .excalidraw.md extraction
│   │   ├── plantuml.py       # PlantUML/C4-PlantUML text parser
│   │   ├── svg.py            # SVG parser
│   │   └── tldraw.py         # TLDraw JSON parser (v1 and v2)
│   └── generators/           # Output format generators
│       ├── __init__.py
│       ├── _text.py          # Shared helpers (ids, shape resolution, container endpoints)
│       ├── d2.py             # D2 diagrams
│       ├── excalidraw.py     # Editable Excalidraw scenes
│       ├── graphviz.py       # GraphViz DOT format
│       ├── mermaid.py        # Mermaid diagrams
│       ├── plantuml.py       # PlantUML and C4-PlantUML
│       └── svg.py            # SVG drawing of the IR (no external renderer)
├── tests/
│   ├── test_any_to_any.py        # Every fixture x every readable output reads back unchanged
│   ├── test_formats.py           # Registry, public API, hints, readable ids
│   ├── test_layout.py            # Synthesized layout: no overlaps, direction, routing
│   ├── test_ir_integration.py    # IR and generator tests
│   ├── test_tldraw_parser.py     # TLDraw parser tests
│   ├── test_svg_parser.py        # SVG parser tests
│   ├── test_workspace.py         # Workspace tests
│   └── data/                     # Test fixtures
│       ├── excalidraw.json
│       └── svg/
└── docs/
````

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

### Format registry and pipeline

**`diacea/formats.py`** is the public API and the only module that lists formats:

- `INPUT_FORMATS` / `OUTPUT_FORMATS` - one `InputFormat` / `OutputFormat` entry per format (detection, file suffixes, parser or generator factory, CLI options)
- `detect_input_format(content, filename)` - content signature first, then file extension, then a last-resort D2 sniff
- `parse_diagram` / `parse_file` - detect, parse, then normalize: elements used as nodes become shapes, `<<type>>` stereotypes and `hints` are applied, and tool-generated ids are replaced with readable ones
- `render_diagram` - build the generator from keyword options and capture its warnings
- `convert` - parse and render in one call; returns a `ConversionResult`
- `verify_conversion` - parse the output back and report any node, group, or connection that differs

**`diacea/layout.py`** gives positions to diagrams that have none. Every text parser calls `layout_diagram`; the Excalidraw and SVG generators call `ensure_layout`.

### Parsers

All parsers implement the `Parser` base class with a `parse(data) -> Diagram` method.

- **`ExcalidrawParser`**: Parses Excalidraw JSON. Labels come from bound text, contained text, grouped text, or text beside an unlabeled shape; a shape with several texts takes the most prominent as its label and the rest as its description. Arrows follow bindings (including bindings to a shape's text) and carry their bound-text labels
- **`parsers/obsidian.py`**: Detects Obsidian `.excalidraw.md` notes and extracts the embedded Excalidraw JSON (compressed blocks need the `diacea[obsidian]` extra)
- **`TLDrawParser`**: Parses TLDraw JSON (legacy v1 and v2 `.tldr`), handles multi-page documents
- **`SVGParser`**: Parses SVG XML. A `<g>` holding one shape is a labelled node; a `<g>` holding several is a container whose enclosing rect is its border; `<defs>` are ignored
- **`MermaidParser`**: Parses flowchart/graph text (bracket shapes, edges, subgraphs, `style` directives), sequence diagrams (participants, actors, messages; control blocks and notes skipped with warnings), and C4 diagrams (delegated to the PlantUML macro parser); rejects other Mermaid diagram types
- **`PlantUMLParser`**: Parses deployment/component elements, relationships, the C4-PlantUML macro dialect, and `Name(alias, "Label")` macros from icon libraries
- **`GraphVizParser`**: Tokenizes and parses DOT: attribute lists and scoped defaults, edge chains and `{a b}` endpoint sets, `cluster` subgraphs as groups; HTML and record labels are flattened with a warning
- **`D2Parser`**: Parses shapes, nested containers, dotted paths, connections, and the `shape`/`label`/`style`/`direction` keywords; skips vars, classes, globs, and imports with a warning

Parsers expose a `warnings` list after `parse()` with any conversion losses detected (e.g. SVG curved outlines reduced to polygons); the CLI surfaces these. Text parsers set `diagram.metadata['direction']` and `['explicit_shapes']`, read back through `Diagram.direction` and `Diagram.has_explicit_shapes`.

### Generators

All generators implement the `Generator` base class with a `generate(diagram) -> str` method.

- **`PlantUMLGenerator`**: Basic PlantUML with components and relationships
- **`C4PlantUMLGenerator`**: C4-PlantUML macros, including `_Ext`, `Db`, and `Queue` variants, technology, and description
- **`MermaidGenerator`**: Mermaid flowcharts, C4, or sequence diagrams
- **`GraphVizGenerator`**: DOT format with clusters and configurable layout
- **`D2Generator`**: D2 diagrams with optional sketch mode
- **`ExcalidrawGenerator`**: Excalidraw scenes with bound labels and bound arrows; deterministic output
- **`SVGGenerator`**: Standalone SVG of the IR

Generators report losses with `warnings.warn`; `render_diagram` collects them. Shared decisions live in `generators/_text.py`: `visual_semantic` (a guessed type never overrides a shape the author chose in a text format), `Containers` (connections that start or end at a group), and `readable_id` (blank instead of a random id for unlabeled elements).

## CLI Usage

```bash
# Basic conversion; the output format comes from -f or the -o extension
diacea diagram.excalidraw -f mermaid
diacea diagram.excalidraw -o output.d2

# Text to an editable drawing, or to an SVG preview
diacea flow.mmd -o flow.excalidraw
diacea graph.dot -o graph.svg

# With format-specific options
diacea diagram.json -f graphviz --graphviz-direction TB

# Pipe from stdin
cat diagram.json | diacea - -f c4

# Correct a guessed type, and confirm nothing was lost
diacea diagram.excalidraw -f c4 --hint 'Orders=database' --verify
```

## CLI Usage for Agents

The conversion CLI is designed to be driven programmatically. Bare invocations (`diacea file -f mermaid`, or `-i file`) are equivalent to the `convert` subcommand.

### JSON envelope

`--json` on conversion emits a machine-readable envelope to stdout instead of the bare converted text:

```json
{
  "output": "flowchart LR\n    ...",
  "input_format": "excalidraw",
  "output_format": "mermaid",
  "diagram_type": "flowchart",
  "elements": [
    {
      "id": "web_server",
      "type": "shape",
      "label": "Web Server",
      "semantic_type": "service",
      "confidence": 0.8,
      "shape": "rectangle",
      "source_id": "vapRpvna4Qio1_zgMc5D3"
    }
  ],
  "warnings": []
}
```

`diagram_type` is the Mermaid type that auto-detection chose (`flowchart`, `c4`, or `sequence`); it is `null` for other output formats. `shape` is present on shapes only, and `source_id` only when the source's tool-generated id was replaced by a readable one. `warnings` lists every known loss, from parsing (SVG curved outlines reduced to polygons, TLDraw pages skipped, dropped arrows, hints that matched nothing) and from generation (dropped or re-pointed connections). In text mode the same warnings print to stderr as `Warning: ...` lines. With `--verify` the envelope also has `"verification": {"checked": true, "problems": []}`.

### Preview and discovery

```bash
# Parse without converting: detected format, element count, per-element
# semantic inference with confidence
diacea inspect diagram.json --json

# List input formats (with detection method and extensions), output formats
# (with options), and the semantic type names accepted by --hint
diacea formats --json

# Regenerate text outputs next to diagram sources; --check reports stale
# outputs with exit 1 instead of writing (used by the pre-commit hooks in
# .pre-commit-hooks.yaml)
diacea sync docs/diagrams/*.excalidraw -f mermaid
```

### Exit codes

- `0`: success
- `1`: error (file not found, unrecognized input format, parse/generation failure, or `--verify` found a difference)
- `2`: the file parsed but produced 0 elements (likely an unsupported schema)

With `--json`, errors are written to stderr as JSON: `{"error": "...", "exit_code": 1}`. `inspect` reports 0 elements as a warning with exit code 0 so agents can still read the report.

## Data Flow

```
Input file (any input format)
    ↓
formats.parse_diagram(): detect → Parser.parse() → Diagram IR
    ↓
Normalize: nodes from empty frames/linked text, <<type>> and --hint, readable ids
    ↓
formats.render_diagram(): Generator.generate() → output text + warnings
    ↓
formats.verify_conversion() (optional): parse the output back and compare
```

## Development Workflow

### Running Tests

```bash
./run main                              # lint, format, tests with coverage, docs
uv run pytest tests -k any_to_any       # every fixture x every readable output format
DIACEA_REGEN_GOLDENS=1 uv run pytest tests/test_curated_fixtures.py   # after an intended output change
DIACEA_RENDER=1 uv run pytest tests/test_curated_fixtures.py          # render with mmdc/d2/dot/plantuml if installed
uv run python scripts/render_fixtures.py --out review                 # HTML page for visual review
```

Review golden diffs before committing them: each changed line is a change in what users get.

### Adding a New Input Format

1. Create `diacea/parsers/newformat.py` with a class extending `Parser`; collect losses in `self.warnings`
1. For a text format, call `layout_diagram` and set `metadata['direction']` and `['explicit_shapes']`
1. Export it from `diacea/parsers/__init__.py`
1. Add one `InputFormat` entry to `INPUT_FORMATS` in `diacea/formats.py` (order decides which signature wins)
1. Create tests in `tests/test_newformat_parser.py` and add a fixture to `tests/test_any_to_any.py`

### Adding a New Output Format

1. Create `diacea/generators/newformat.py` with a class extending `Generator`; report losses with `warnings.warn`
1. Export it from `diacea/generators/__init__.py`
1. Add one `OutputFormat` entry to `OUTPUT_FORMATS` in `diacea/formats.py`, with its options and, if a parser reads it, `reads_back_as`
1. Add the suffix to `OUTPUT_FORMATS` in `tests/test_curated_fixtures.py` and regenerate goldens

The CLI flags, `diacea formats`, `diacea sync`, and extension inference all follow from the registry entry.

### Adding a New Semantic Type

1. Add to `SemanticType` enum in `diacea/ir/semantic.py`
1. Add keywords to `SEMANTIC_KEYWORDS` dict (matched against the head noun of the label's first line)
1. Add heuristics to `_infer_from_heuristics()` if needed
1. Update generators to handle new type

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
        diagram = Diagram(name='...')
        for elem in data['elements']:
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
        return '\n'.join(lines)
```

## Notes for AI Assistants

- **Follow existing patterns** - Parsers and generators have consistent structure
- **Go through the registry** - New call sites use `diacea.formats`, never a hard-coded parser or generator
- **Look at the output** - Convert real fixtures and read (or render) the result; `--verify` and `scripts/render_fixtures.py` catch what unit tests miss
- **Use type hints** - The project uses beartype for runtime checking
- **Test thoroughly** - Add tests for new functionality
- **Preserve semantics** - IR should capture semantic meaning, not just visual layout
- **Handle edge cases** - Empty diagrams, missing labels, unsupported elements
