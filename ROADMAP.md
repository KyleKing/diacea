# diacea Project Roadmap

**Vision**: Transform diacea into the "pandoc for diagrams" - a universal diagram converter supporting multiple input and output formats.

## Current Status (✅ Completed)

- ✅ Core conversion algorithms (5 approaches)
- ✅ Basic PlantUML generation
- ✅ C4-PlantUML support
- ✅ CLI interface
- ✅ Python-only implementation (Golang removed)
- ✅ Comprehensive test suite

## Upcoming Phases

Detailed phase plans are in the `phases/` directory. Each phase is estimated at 2-2.5 weeks.

### Phase 1: Rich IR Foundation (Week 1-2.5)

**Status**: 📋 Planned
**Document**: [phases/phase_1_rich_ir_foundation.md](phases/phase_1_rich_ir_foundation.md)

**Goals**:
- Create comprehensive Intermediate Representation (IR)
- Implement hybrid semantic inference (rules + hints)
- Refactor existing code to use IR
- Establish parser/generator pattern

**Key Deliverables**:
- `diacea/ir/` module with complete IR classes
- `SemanticType` enum and inference logic
- Base `Parser` and `Generator` interfaces
- Refactored `ExcalidrawParser`
- Migration of existing PlantUML generators

**Open Questions** (5):
1. Confidence threshold for semantic inference
2. Handling ambiguous diagrams
3. Versioning strategy for IR
4. Performance optimization approach
5. User override mechanism

### Phase 2: Mermaid Output Support (Week 3-5.5)

**Status**: 📋 Planned
**Document**: [phases/phase_2_mermaid_support.md](phases/phase_2_mermaid_support.md)

**Goals**:
- Add Mermaid as first new output format
- Support flowchart, C4, and sequence diagrams
- Implement auto-detection of diagram type
- CLI integration

**Key Deliverables**:
- `diacea/generators/mermaid.py`
- `MermaidGenerator` class
- Auto-detection logic
- 10+ test cases
- CLI flag: `--format mermaid`

**Open Questions** (3):
1. Default diagram type selection
2. Style preservation approach
3. Subgraph depth limits

### Phase 3: GraphViz/DOT Output Support (Week 6-8.5)

**Status**: 📋 Planned
**Document**: [phases/phase_3_graphviz_support.md](phases/phase_3_graphviz_support.md)

**Goals**:
- Add GraphViz DOT format generation
- Support directed/undirected graphs
- Implement cluster/subgraph handling
- Auto-detect optimal layout direction

**Key Deliverables**:
- `diacea/generators/graphviz.py`
- `GraphVizGenerator` class
- Layout optimization logic
- CLI flag: `--format graphviz --graphviz-direction [LR|TB|RL|BT]`

**Open Questions** (3):
1. Color mapping strategy (hex vs named)
2. Nested cluster depth
3. Position preservation vs auto-layout

### Phase 4: D2 Output Support (Week 9-11.5)

**Status**: 📋 Planned
**Document**: [phases/phase_4_d2_support.md](phases/phase_4_d2_support.md)

**Goals**:
- Add D2 modern diagram format
- Support nested containers
- Implement sketch mode option
- Handle complex hierarchies

**Key Deliverables**:
- `diacea/generators/d2.py`
- `D2Generator` class
- Direction auto-detection
- CLI flags: `--format d2 --d2-sketch --d2-direction [up|down|left|right]`

**Open Questions** (3):
1. Icon integration approach
2. Theme support priority
3. Layout preservation strategy

### Phase 5: TLDraw Input Parser (Week 12-14)

**Status**: 📋 Planned
**Document**: [phases/phase_5_tldraw_parser.md](phases/phase_5_tldraw_parser.md)

**Goals**:
- Add TLDraw as second input format
- Parse TLDraw JSON to IR
- Handle bindings and connections
- Support auto-format detection

**Key Deliverables**:
- `diacea/parsers/tldraw.py`
- `TLDrawParser` class
- Multi-page support
- CLI flag: `--input-format [auto|excalidraw|tldraw]`

**Open Questions** (4):
1. Multi-page handling strategy
2. Custom shape mapping
3. Version compatibility range
4. Freehand element handling

### Phase 6: Basic SVG Input Parser (Week 15-17.5)

**Status**: 📋 Planned
**Document**: [phases/phase_6_svg_parser.md](phases/phase_6_svg_parser.md)

**Goals**:
- Add SVG parsing for basic shapes
- Support semantic hints via `data-semantic`
- Parse groups and text labels
- Enable import from vector tools

**Key Deliverables**:
- `diacea/parsers/svg.py`
- `SVGParser` class
- Semantic hint parsing
- Text association logic
- CLI flag: `--input-format svg`

**Scope Limits**:
- ✅ Basic shapes (rect, circle, ellipse, polygon)
- ✅ Text elements
- ✅ Simple groups
- ✅ Lines (limited)
- ❌ Complex paths
- ❌ Gradients, filters, masks

**Open Questions** (3):
1. Path support scope
2. Transform matrix handling
3. Connection detection approach

## Future Phases (Beyond Week 17.5)

### Phase 7: Draw.io Parser
- Parse Draw.io XML format
- Support mxGraph structure
- Handle Draw.io-specific elements

### Phase 8: Structurizr DSL Generator
- Generate Structurizr DSL
- C4 model native support
- Workspace generation

### Phase 9: PlantUML Parser
- Parse PlantUML to IR (reverse direction)
- Enable round-trip conversion
- Preserve formatting hints

### Phase 10: Web Interface
- Browser-based converter
- Real-time preview
- Drag-and-drop support

## Success Metrics

### Technical Metrics

- **Format Coverage**:
  - Inputs: Excalidraw, TLDraw, SVG (Phases 1-6)
  - Outputs: PlantUML, C4, Mermaid, GraphViz, D2 (Phases 1-6)

- **Test Coverage**: >85% code coverage

- **Performance**:
  - Parse/generate <1s for diagrams with <100 elements
  - Parse/generate <5s for diagrams with <500 elements

- **Accuracy**:
  - Semantic inference >80% accurate on test suite
  - No data loss in conversions (structure preserved)

### User Experience Metrics

- **CLI Usability**: Single command for any conversion
- **Documentation**: Complete examples for each format
- **Error Messages**: Clear, actionable error messages

## Architecture Evolution

### Current (Phase 0)
```
Excalidraw JSON → Multiple Algorithms → Relative Format → PlantUML/C4
```

### After Phase 1
```
Excalidraw JSON → Parser → Rich IR → Generator → PlantUML/C4
```

### After Phase 6
```
┌─────────────────┐
│  Input Formats  │
├─────────────────┤
│  Excalidraw     │
│  TLDraw         │──┐
│  SVG (basic)    │  │
└─────────────────┘  │
                     ↓
              ┌──────────────┐
              │   Rich IR    │
              │  (Semantic)  │
              └──────────────┘
                     ↓
┌─────────────────┐  │
│ Output Formats  │  │
├─────────────────┤  │
│  PlantUML       │←─┘
│  C4-PlantUML    │
│  Mermaid        │
│  GraphViz DOT   │
│  D2             │
└─────────────────┘
```

## Test Data

Comprehensive test diagrams available in `test_diagrams/`:

### Mermaid Examples
- `simple_architecture.mmd` - Basic flowchart
- `c4_architecture.mmd` - C4 system context
- `c4_container.mmd` - C4 container diagram

### D2 Examples
- `simple_architecture.d2` - Nested containers

### GraphViz Examples
- `architecture_system.dot` - Clusters and subgraphs

### SVG Examples
- `simple_architecture.svg` - Basic shapes with semantic hints
- `complex_architecture.svg` - Multi-cloud architecture (20+ components)

**Complexity Levels**:
- Simple: 3-5 components
- Medium: 5-10 components
- Complex: 20+ components

See [test_diagrams/README.md](test_diagrams/README.md) for details.

## Implementation Guidelines

### For Each Phase:

1. **Planning** (included in phase documents):
   - Technical specification
   - Test specification
   - Success criteria
   - Open questions

2. **Implementation**:
   - Follow existing patterns
   - Type hints throughout
   - Docstrings for all public APIs
   - Error handling and validation

3. **Testing**:
   - Unit tests for all functions
   - Integration tests with test diagrams
   - Edge case coverage
   - Performance benchmarks

4. **Documentation**:
   - Update README.md
   - CLI help text
   - Code examples
   - Migration notes

5. **Review**:
   - Code review
   - Test coverage check
   - Performance validation
   - User acceptance

## Dependencies

### Current
- networkx (graph-based algorithm)
- python-constraint2 (CSP solver)
- Standard library (json, dataclasses, etc.)

### Planned
- None! All format generation uses only Python standard library
- External tools (mermaid-cli, d2, dot) only for rendering, not generation

## Contributing

See phase documents for specific implementation details and open questions.

### Priority Order
1. Phase 1 (IR) - Foundation for everything else
2. Phase 2 (Mermaid) - Popular format, good ROI
3. Phase 3 (GraphViz) - Industry standard
4. Phase 4 (D2) - Modern format
5. Phase 5 (TLDraw) - Second input format
6. Phase 6 (SVG) - Universal input format

### Parallel Development
Some phases can be developed in parallel after Phase 1:
- Phases 2-4 (generators) can run in parallel
- Phases 5-6 (parsers) can run in parallel

## Questions?

- **Phase-specific questions**: See `phases/phase_N_*.md`
- **General questions**: Open a GitHub issue
- **Implementation details**: See DEVELOPER.md

## Timeline Summary

| Phase | Weeks | Deliverable | Status |
|-------|-------|-------------|--------|
| 0 (Current) | - | Python-only implementation | ✅ Complete |
| 1 | 1-2.5 | Rich IR Foundation | 📋 Planned |
| 2 | 3-5.5 | Mermaid Output | 📋 Planned |
| 3 | 6-8.5 | GraphViz Output | 📋 Planned |
| 4 | 9-11.5 | D2 Output | 📋 Planned |
| 5 | 12-14 | TLDraw Parser | 📋 Planned |
| 6 | 15-17.5 | SVG Parser | 📋 Planned |
| **Total** | **~17.5 weeks** | **6 major formats** | - |

---

**Last Updated**: 2025-11-22
**Next Review**: After Phase 1 completion
