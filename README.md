# diacea

Universal diagram converter - the pandoc for diagrams

**diacea** converts between diagram formats through a format-agnostic intermediate representation. Any supported input converts to any supported output, in both directions between drawings and text: turn an Excalidraw sketch into Mermaid, a Mermaid flowchart into an editable Excalidraw scene, or GraphViz DOT into D2.

## Why diacea?

- **Drawing to text**: turn hand-drawn Excalidraw, TLDraw, and SVG diagrams into version-controllable Mermaid, PlantUML, C4, DOT, or D2
- **Text to drawing**: turn any text diagram into an editable Excalidraw scene, laid out for you
- **Text to text**: convert between Mermaid, PlantUML/C4, GraphViz DOT, and D2
- **Reads what it writes**: every text format diacea generates, it also parses, so conversions can be checked with `--verify`
- **Semantic inference you can correct**: element types (database, person, queue, ...) are guessed from shapes and labels, and overridden with a `<<type>>` in the label or `--hint`
- **Agent friendly**: `--json` envelopes, `inspect`/`formats` subcommands, and structured exit codes
- **Docs integrations**: `diacea sync` with pre-commit hooks and an MkDocs plugin keep generated diagrams current
- **Pure Python**: no renderer, browser, or JVM needed to convert

## Installation

```bash
pip install diacea

# For Obsidian Excalidraw notes with compressed-json Drawing blocks
pip install 'diacea[obsidian]'
```

## Quick Start

### CLI Usage

The input format is detected from the file's content (then its extension); the output format comes from `-f` or the extension of `-o`.

```bash
# Excalidraw sketch to Mermaid, printed to stdout
diacea sketch.excalidraw -f mermaid

# Output format inferred from the file name
diacea sketch.excalidraw -o architecture.d2

# Text to an editable drawing: open the result at excalidraw.com
diacea flow.mmd -o flow.excalidraw

# Text to text
diacea graph.dot -f d2
diacea architecture.puml -f mermaid --mermaid-type flowchart

# Preview any diagram as SVG without installing a renderer
diacea flow.mmd -o flow.svg

# C4-PlantUML from an Obsidian Excalidraw note
diacea notes/architecture.excalidraw.md -f c4 -o architecture.puml

# Confirm nothing was lost: parses the output back and compares
diacea sketch.excalidraw -o architecture.mmd --verify

# Pipe from stdin
cat diagram.json | diacea - -f mermaid

# Machine-readable output: JSON envelope with the converted text,
# detected formats, per-element semantic inference, and warnings
diacea sketch.excalidraw -f mermaid --json

# Build a workspace from existing diagram files
diacea-workspace create --name "My System" --from-diagrams a.json b.svg -o workspace.yml
```

`-i FILE` is accepted in place of the positional input.

### Checking and Correcting a Conversion

`diacea inspect` shows what was read from a file before you convert it: the detected format, every element, and the type guessed for it with a confidence.

```bash
diacea inspect sketch.excalidraw
```

A type with confidence below 0.90 is a guess from the label or shape. When a guess is wrong, state the type yourself in either of two ways:

- **In the diagram**: add a UML-style stereotype to the element's label, such as `Orders <<database>>` or `Ada <<person>>`. It works in every drawing tool and text format, and is removed from the label in the output
- **On the command line**: `--hint 'Orders=database'`, matching the element's label or id (repeatable)

`diacea formats` lists the valid type names. Anything the conversion could not carry over (a skipped directive, a connection the target format cannot express) is printed as a `Warning:` line, and `--verify` fails with the specifics if the output does not read back with the same nodes, groups, and connections. See [the troubleshooting guide](docs/docs/TROUBLESHOOTING.md) for common causes and fixes.

### Keeping Generated Diagrams in Sync

`diacea sync` regenerates text diagrams next to their sources, writing only when the output is stale:

```bash
# Write arch.mmd next to arch.excalidraw (default format: mermaid)
diacea sync docs/diagrams/arch.excalidraw

# Other formats and a dedicated output directory
diacea sync docs/diagrams/*.excalidraw -f d2 --output-dir docs/generated

# CI-friendly: report stale outputs and exit 1 without writing
diacea sync --check docs/diagrams/*.excalidraw
```

#### pre-commit

The repo ships `diacea-sync` (rewrites stale outputs) and `diacea-check` (fails without writing) hooks:

```yaml
repos:
  - repo: https://github.com/kyleking/diacea
    rev: main  # prefer a release tag
    hooks:
      - id: diacea-sync
        args: [-f, mermaid]
```

#### MkDocs

Install `diacea[mkdocs]` and register the plugin:

```yaml
plugins:
  - diacea
```

Then reference diagram sources from markdown with a `diacea` fence, which is replaced at build time by a code block in the target language (so mkdocs-material's Mermaid support renders it):

````markdown
```diacea
source: diagrams/architecture.excalidraw
format: mermaid
```
````

`source` is resolved relative to the page, then the docs directory. `format` defaults to `mermaid`; `mermaid-type` optionally forces `flowchart`, `c4`, or `sequence`.

### Python API

```python
from diacea import convert

result = convert('flowchart LR\n    web[Web App] --> db[(Orders DB)]', to='d2')
print(result.output)
print(result.input_format, result.warnings)

# Correct a guessed type, pass generator options, or keep the parsed diagram
result = convert(open('sketch.excalidraw').read(), to='c4', hints={'Orders': 'database'})
result = convert(open('graph.dot').read(), to='mermaid', mermaid_type='flowchart')
for shape in result.diagram.get_shapes():
    print(shape.id, shape.label, shape.semantic_type)
```

`diacea.parse_file` / `diacea.parse_diagram` return the intermediate representation, and `diacea.render_diagram` generates from it; the parser and generator classes in `diacea.parsers` and `diacea.generators` are available for finer control.

## Supported Formats

Run `diacea formats` for the same lists with detection rules and options.

### Input Formats

| Format                                 | `--input-format` | Notes                                                                             |
| -------------------------------------- | ---------------- | --------------------------------------------------------------------------------- |
| Excalidraw JSON                        | `excalidraw`     | Scenes and clipboard exports; bound and loose labels, arrow labels, frames        |
| Obsidian Excalidraw (`.excalidraw.md`) | `obsidian`       | Compressed notes need the `[obsidian]` extra                                      |
| TLDraw JSON                            | `tldraw`         | Legacy v1 documents and v2 `.tldr` files                                          |
| SVG                                    | `svg`            | Shapes, text, and groups; curves sampled for accurate bounding boxes              |
| Mermaid                                | `mermaid`        | Flowchart/graph, sequence, and C4 diagrams                                        |
| PlantUML                               | `plantuml`       | Deployment/component elements, C4 macros, and icon-library macros (AWS, Azure, …) |
| GraphViz DOT                           | `graphviz`       | Clusters, attributes and defaults, edge chains and endpoint sets                  |
| D2                                     | `d2`             | Shapes, nested containers, connections, `shape` and `style` keywords              |

Text formats carry no coordinates, so a layered layout is synthesized for them (used by the Excalidraw and SVG outputs).

### Output Formats

| Format       | `-f`         | Extension     | Options                                    |
| ------------ | ------------ | ------------- | ------------------------------------------ |
| Mermaid      | `mermaid`    | `.mmd`        | `--mermaid-type` (flowchart, c4, sequence) |
| PlantUML     | `plantuml`   | `.puml`       | -                                          |
| C4-PlantUML  | `c4`         | `.puml`       | -                                          |
| GraphViz DOT | `graphviz`   | `.dot`        | `--graphviz-direction`, `--graphviz-type`  |
| D2           | `d2`         | `.d2`         | `--d2-direction`, `--d2-sketch`            |
| Excalidraw   | `excalidraw` | `.excalidraw` | `--excalidraw-roughness`                   |
| SVG          | `svg`        | `.svg`        | -                                          |

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

Every format is one entry in the registry in `diacea/formats.py`, which the CLI, the Python API, `diacea sync`, and the MkDocs plugin all share.

## Documentation

- **[Troubleshooting](docs/docs/TROUBLESHOOTING.md)** - Checking a conversion and fixing what it got wrong
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
