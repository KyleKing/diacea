# diacea

Universal diagram converter - the pandoc for diagrams

**diacea** converts between diagram formats using a format-agnostic intermediate representation. Convert Excalidraw (including Obsidian `.excalidraw.md`), TLDraw, SVG, Mermaid, or PlantUML diagrams to PlantUML, C4-PlantUML, Mermaid, GraphViz DOT, or D2.

## Why diacea?

- **Visual to Text**: Convert hand-drawn diagrams into version-controllable text formats
- **Text to Text**: Convert between Mermaid, PlantUML/C4, GraphViz DOT, and D2
- **Multiple Input Formats**: Excalidraw, Obsidian Excalidraw markdown, TLDraw (legacy and v2 `.tldr`), SVG, Mermaid flowcharts and sequence diagrams, PlantUML (including C4 macros)
- **Multiple Output Formats**: PlantUML, C4-PlantUML, Mermaid, GraphViz DOT, D2
- **Semantic Inference**: Automatically detects diagram element types (databases, people, systems)
- **Agent Friendly**: `--json` envelopes, `inspect`/`formats` subcommands, and structured exit codes
- **Python Native**: Pure Python implementation

## Installation

```bash
pip install diacea

# For Obsidian Excalidraw notes with compressed-json Drawing blocks
pip install 'diacea[obsidian]'
```

## Quick Start

### CLI Usage

```bash
# Convert Excalidraw to Mermaid
diacea -i diagram.json -f mermaid -o output.mmd

# Convert to C4-PlantUML
diacea -i diagram.json -f c4 -o architecture.puml

# Convert TLDraw to GraphViz with custom direction
diacea -i tldraw.json -f graphviz --graphviz-direction TB -o output.dot

# Convert an Obsidian Excalidraw note
diacea -i notes/architecture.excalidraw.md -f mermaid

# Convert SVG to D2 with sketch mode
diacea -i diagram.svg -f d2 --d2-sketch -o output.d2

# Text-to-text: Mermaid flowchart to D2, PlantUML to Mermaid
diacea -i flow.mmd -f d2
diacea -i architecture.puml -f mermaid --mermaid-type flowchart

# Pipe from stdin
cat diagram.json | diacea -i - -f mermaid

# Machine-readable output: JSON envelope with the converted text,
# detected formats, per-element semantic inference, and warnings
diacea -i diagram.json -f mermaid --json

# Preview a file before converting (detected format, elements, confidences)
diacea inspect diagram.json --json

# List supported formats and their options
diacea formats --json

# Build a workspace from existing diagram files
diacea-workspace create --name "My System" --from-diagrams a.json b.svg -o workspace.yml
```

### Python API

```python
from diacea.parsers import ExcalidrawParser
from diacea.generators import MermaidGenerator, C4PlantUMLGenerator

# Parse input
parser = ExcalidrawParser()
with open('diagram.json') as f:
    import json
    diagram = parser.parse(json.load(f))

# Generate output
mermaid_gen = MermaidGenerator()
print(mermaid_gen.generate(diagram))

c4_gen = C4PlantUMLGenerator()
print(c4_gen.generate(diagram))
```

## Supported Formats

### Input Formats
| Format | Parser | Auto-detect | Notes |
|--------|--------|-------------|-------|
| Excalidraw JSON | `ExcalidrawParser` | Yes | Scenes and clipboard exports |
| Obsidian Excalidraw (`.excalidraw.md`) | `ExcalidrawParser` | Yes | Compressed notes need the `[obsidian]` extra |
| TLDraw JSON | `TLDrawParser` | Yes | Legacy v1 documents and v2 `.tldr` files |
| SVG | `SVGParser` | Yes | Basic shapes; curves sampled for accurate bounding boxes |
| Mermaid | `MermaidParser` | Yes | Flowchart/graph and sequence diagrams; layout synthesized |
| PlantUML | `PlantUMLParser` | Yes | Deployment/component elements and C4 macros; layout synthesized |

### Output Formats
| Format | Generator | Options |
|--------|-----------|---------|
| PlantUML | `PlantUMLGenerator` | - |
| C4-PlantUML | `C4PlantUMLGenerator` | - |
| Mermaid | `MermaidGenerator` | `--mermaid-type` (flowchart, c4, sequence) |
| GraphViz DOT | `GraphVizGenerator` | `--graphviz-direction`, `--graphviz-type` |
| D2 | `D2Generator` | `--d2-direction`, `--d2-sketch` |

## Architecture

```
Input Formats          IR (Intermediate Repr)         Output Formats
-------------         ----------------------         --------------
Excalidraw  --+                                    +-- PlantUML
TLDraw      --+                                    +--> C4-PlantUML
SVG         --+--> Diagram -> Elements -> Semantic +--> Mermaid
Mermaid     --+         (with semantic types)      +--> GraphViz DOT
PlantUML/C4 --+                                    +-- D2
```

## Documentation

- **[DEVELOPER.md](DEVELOPER.md)** - Development setup and contributing
- **[SPEC.md](SPEC.md)** - Detailed specifications and use cases
- **[AGENTS.md](AGENTS.md)** - AI assistant guide to the codebase

## Related Projects

- [procXD](https://github.com/BardOfCodes/procXD) - Process diagram converter
- [Excalidraw_Interface](https://github.com/RobertJN64/Excalidraw_Interface) - Excalidraw integration tools

## Contributing

We welcome pull requests! For your pull request to be accepted smoothly, we suggest that you first open a GitHub issue to discuss your idea. For resources on getting started with the code base, see [DEVELOPER.md](DEVELOPER.md).

## Code of Conduct

We follow the [Contributor Covenant Code of Conduct](https://www.contributor-covenant.org).

## License

[MIT License](LICENSE)

## Links

- **Documentation**: [https://diacea.kyleking.me](https://diacea.kyleking.me)
- **PyPI**: [https://pypi.org/project/diacea](https://pypi.org/project/diacea)
- **Repository**: [https://github.com/kyleking/diacea](https://github.com/kyleking/diacea)
- **Changelog**: [docs/docs/CHANGELOG.md](docs/docs/CHANGELOG.md)
