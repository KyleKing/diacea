# diacea

Universal diagram converter - the pandoc for diagrams

**diacea** converts between visual diagram formats using a format-agnostic intermediate representation. Convert Excalidraw, TLDraw, or SVG diagrams to PlantUML, C4-PlantUML, Mermaid, GraphViz DOT, or D2.

## Why diacea?

- **Visual to Text**: Convert hand-drawn diagrams into version-controllable text formats
- **Multiple Input Formats**: Excalidraw, TLDraw, SVG
- **Multiple Output Formats**: PlantUML, C4-PlantUML, Mermaid, GraphViz DOT, D2
- **Semantic Inference**: Automatically detects diagram element types (databases, people, systems)
- **Python Native**: Pure Python implementation

## Installation

```bash
pip install diacea
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

# Convert SVG to D2 with sketch mode
diacea -i diagram.svg -f d2 --d2-sketch -o output.d2

# Pipe from stdin
cat diagram.json | diacea -i - -f mermaid
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
| Format | Parser | Auto-detect |
|--------|--------|-------------|
| Excalidraw JSON | `ExcalidrawParser` | Yes |
| TLDraw JSON | `TLDrawParser` | Yes |
| SVG | `SVGParser` | Yes |

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
TLDraw      --+--> Diagram -> Elements -> Semantic +--> C4-PlantUML
SVG         --+         (with semantic types)      +--> Mermaid
                                                   +--> GraphViz DOT
                                                   +-- D2
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
