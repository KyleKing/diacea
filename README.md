# diacea

Convert between Excalidraw and PlantUML

**diacea** is a Python library that converts Excalidraw JSON exports to PlantUML diagrams. Think of it as "pandoc for diagrams" - bridging the gap between Excalidraw's visual diagramming and PlantUML's text-based diagramming.

## Why diacea?

- **Visual to Text**: Convert your hand-drawn Excalidraw diagrams into version-controllable PlantUML text
- **Multiple Algorithms**: Choose from various conversion approaches (imperative, rule-based, CSP solver, quadtree, graph-based)
- **C4 Model Support**: Generate C4-PlantUML diagrams for architecture documentation
- **Python Native**: Pure Python implementation, no external dependencies on other languages

## Installation

```bash
poetry add diacea
```

Or with pip:

```bash
pip install diacea
```

## Quick Start

```python
import json
from diacea.experiments import graph_based_approach
from diacea import generate_plantuml

# Load Excalidraw JSON
with open('diagram.json') as f:
    excalidraw_data = json.load(f)

# Convert to relative format
relative_data = graph_based_approach(excalidraw_data['elements'])

# Convert to PlantUML
plantuml = generate_plantuml(relative_data)

# Save to file
with open('output.puml', 'w') as f:
    f.write(plantuml)
```

## Project Status

This project is in early development. Current capabilities:

- ✅ Convert Excalidraw absolute coordinates to relative relationships
- ✅ Multiple algorithm implementations for spatial analysis
- ✅ Test coverage for core conversion logic
- ✅ Basic PlantUML generation
- 🚧 CLI interface (planned)
- 🚧 C4-PlantUML support (planned)

See [SPEC.md](SPEC.md) for detailed use cases and limitations.

## Documentation

- **[DEVELOPER.md](DEVELOPER.md)** - How to develop, test, and contribute
- **[SPEC.md](SPEC.md)** - What the project does, use cases, and specifications
- **[AGENTS.md](AGENTS.md)** - AI assistant guide to the codebase

## Related Projects

- [procXD](https://github.com/BardOfCodes/procXD) - Process diagram converter
- [Excalidraw_Interface](https://github.com/RobertJN64/Excalidraw_Interface) - Excalidraw integration tools

## Contributing

We welcome pull requests! For your pull request to be accepted smoothly, we suggest that you first open a GitHub issue to discuss your idea. For resources on getting started with the code base, see [DEVELOPER.md](DEVELOPER.md).

## Code of Conduct

We follow the [Contributor Covenant Code of Conduct](https://www.contributor-covenant.org).

## Responsible Disclosure

If you have any security issue to report, please contact the project maintainers privately. You can reach us at [dev.act.kyle@gmail.com](mailto:dev.act.kyle@gmail.com).

## License

[MIT License](LICENSE)

## Links

- **Documentation**: [https://diacea.kyleking.me](https://diacea.kyleking.me)
- **PyPI**: [https://pypi.org/project/diacea](https://pypi.org/project/diacea)
- **Repository**: [https://github.com/kyleking/diacea](https://github.com/kyleking/diacea)
- **Changelog**: [docs/docs/CHANGELOG.md](docs/docs/CHANGELOG.md)
