## Unreleased

### Feat

- diacea sync, pre-commit hooks, and MkDocs plugin
- parse Mermaid sequence diagrams
- sample SVG path curves for accurate bounding boxes
- Mermaid and PlantUML text parsers for text-to-text conversion
- agent-friendly CLI (--json, inspect, formats) and docs refresh
- workspace diagram ingestion and generator consolidation
- tldraw v2 parsing, Obsidian .excalidraw.md input, D2/PlantUML output fixes
- **docs**: support Zensical migration via calcipy_template
- **phase-7**: add workspace CLI commands
- **phase-7**: add workspace file format support
- **phase-7**: add workspace IR classes
- **phase-6**: implement SVG parser with CLI integration
- implement Phase 5 - TLDraw Input Parser
- implement Phase 4 - D2 Output Support
- add CLI for universal diagram conversion
- implement Phase 3 - GraphViz/DOT Output Support
- implement Phase 2 - Mermaid Output Support
- implement Phase 1 - Rich IR Foundation
- add golang implementation
- add experiments
- initialize the project

### Fix

- **mermaid**: type C4 Rel endpoint as optional so the unresolved guard stays live
- **excalidraw**: prefer native containerId binding for labels
- **mermaid**: record source diagram type and emit valid dashed edges
- **c4**: remap Rel endpoints from suppressed container shapes to boundary aliases
- **d2**: drop container-to-descendant connections dagre cannot lay out
- **excalidraw**: use center-point containment and skip soft-deleted elements
- **generators**: render nested groups recursively in all five outputs
- **excalidraw**: detect groups native-first with direct children only
- **svg**: parse untrusted SVG with defusedxml
- **workspace**: keep the Windows drive letter out of the diagram spec split
- **deps**: bump urllib3 to 2.7.0
- **deps**: bump soupsieve to 2.9.1
- **deps**: bump pytest to 9.1.1
- **deps**: bump pymdown-extensions to 11.0.1
- **deps**: bump pygments to 2.20.0
- **deps**: bump idna to 3.18
- **deps**: bump gitpython to 3.1.57
- clear the mypy and pyright typecheck backlog
- Mermaid C4 declarations, label quoting, and text-format ingestion
- parser defects found by real-world fixture evaluation
- restore README content overwritten by copier-auto-update
- restore pyproject.toml content stripped by copier-auto-update
- address label escaping

### Refactor

- cleanup original experimentation
- cleanup
- remove golang
- try automating fixes

### Perf

- **excalidraw**: index shapes in a bucket grid instead of scanning every pair
