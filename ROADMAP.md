# diacea Project Roadmap

**Vision**: Transform diacea into the "pandoc for diagrams" - a universal diagram converter supporting multiple input and output formats.

## Status

### Shipped

Detailed phase plans are in the `phases/` directory. All seven phases are implemented and tested.

| Phase | Deliverable | Reality notes |
|-------|-------------|---------------|
| 1 | Rich IR foundation (`diacea/ir/`) | `Diagram`/`Element` dataclasses with semantic inference and confidence scores; format metadata preserved for one-way conversion, not round-trips |
| 2 | Mermaid output | Flowchart, C4, and sequence with auto-detection (`--mermaid-type` to force); subgraphs capped at 3 levels |
| 3 | GraphViz DOT output | Clusters, direction auto-detection, `digraph`/`graph`; layout is delegated to the engine (positions dropped) |
| 4 | D2 output | Nested containers, sketch mode, direction auto-detection |
| 5 | TLDraw input | Legacy v1 documents and v2 `.tldr` files; single page by default (multi-page emits a conversion warning) |
| 6 | SVG input | rect/circle/ellipse/polygon/path/line/text/groups with `data-semantic` hints; curve commands (C/S/Q/T/A) are flattened to bounding boxes with a runtime warning |
| 7 | Multi-diagram workspaces | `diacea-workspace` CLI: create (including `--from-diagrams` ingestion with element deduplication), validate, info, add-element, add-view |

Also shipped beyond the original phase plans:

- Obsidian Excalidraw markdown input (`.excalidraw.md`), with `compressed-json` support via the `diacea[obsidian]` extra
- Agent-friendly CLI: `--json` envelopes, `diacea inspect`, `diacea formats`, structured exit codes, and conversion-loss warnings

### Next

- Mermaid and PlantUML text parsers, enabling text-to-text conversion (e.g. Mermaid to D2)
- SVG curve fidelity: approximate C/S/Q/T/A commands instead of flattening to bounding boxes
- MkDocs and pre-commit integrations for keeping generated diagrams in sync

### Ideas (unscheduled)

- Draw.io (mxGraph XML) parser
- Structurizr DSL generator
- Web interface with live preview

## Success Metrics

- **Correctness**: Semantic inference >80% accurate on the test suite; structure (nodes, connections, groups) preserved in every conversion
- **Performance**: Parse/generate <1s for diagrams with <100 elements
- **CLI usability**: Single command for any conversion, machine-readable output, actionable errors

## Known Limitations

Conversions are one-way (visual to text). Documented losses, tracked in `tests/test_roundtrip_limitations.py`:

- Exact positions are dropped; text formats delegate layout to their renderers
- SVG curves become bounding boxes
- Hand-drawn styling (Excalidraw roughness, seeds) is not preserved

## Test Data

Example diagrams live in `test_diagrams/` (Mermaid, D2, GraphViz, SVG at simple/medium/complex sizes) and parser fixtures in `tests/data/`. See [test_diagrams/README.md](test_diagrams/README.md).

## Contributing

- **Phase history**: See `phases/phase_N_*.md` for the original specifications
- **Development setup**: See [DEVELOPER.md](DEVELOPER.md)
- **Questions**: Open a GitHub issue

---

**Last Updated**: 2026-07-05
