# Test Diagrams Collection

This directory contains example diagrams in various formats for testing the diacea parsers and generators.

## Purpose

These diagrams serve as:
1. **Test data** for parser implementations
2. **Reference examples** for generator output
3. **Complexity benchmarks** (simple → complex)
4. **Format comparison** across different diagramming languages

## Diagram Files

### Mermaid Format (.mmd)

| File | Type | Complexity | Description |
|------|------|------------|-------------|
| `simple_architecture.mmd` | Flowchart | Simple | Basic microservices with databases and queue |
| `c4_architecture.mmd` | C4 Context | Medium | System context with external systems |
| `c4_container.mmd` | C4 Container | Medium | Container-level view of e-commerce system |

**Render with:**
- Online: https://mermaid.live/
- CLI: `mmdc -i file.mmd -o output.svg`

### D2 Format (.d2)

| File | Type | Complexity | Description |
|------|------|------------|-------------|
| `simple_architecture.d2` | Architecture | Medium | Microservices with nested containers and connections |

**Render with:**
- Online: https://play.d2lang.com/
- CLI: `d2 file.d2 output.svg`

### GraphViz DOT Format (.dot)

| File | Type | Complexity | Description |
|------|------|------------|-------------|
| `architecture_system.dot` | Directed Graph | Medium | Microservices with clusters for services and databases |

**Render with:**
- Online: https://graphvizonline.net/
- CLI: `dot -Tsvg file.dot -o output.svg`

### SVG Format (.svg)

| File | Type | Complexity | Description |
|------|------|------------|-------------|
| `simple_architecture.svg` | Vector Diagram | Simple | Basic microservices with semantic hints (data-semantic) |
| `complex_architecture.svg` | Vector Diagram | Complex | Multi-cloud platform with AWS, GCP, external services |

**View:**
- Any web browser
- Inkscape, Adobe Illustrator, etc.

## Semantic Types Used

All diagrams demonstrate various semantic types that should be inferred or parsed:

- **Person**: End users, administrators (ellipse/circle shapes)
- **System**: Major system boundaries (large rectangles with dashed borders)
- **Container**: Application containers, services (rectangles)
- **Component**: Specific components within containers (smaller rectangles)
- **Database**: Data stores (cylinders/ellipses with "DB" labels)
- **Queue**: Message queues (folders/special shapes with "Queue" labels)
- **External**: Third-party services (octagons/special shapes)
- **Cloud**: Cloud provider boundaries (large rounded rectangles)
- **Storage**: Object storage, cache (rectangles with storage-related labels)

## Test Scenarios

### Simple → Complex Progression

1. **Simple** (`simple_architecture.*`):
   - 3-5 services
   - Single database per service
   - Linear connections
   - Good for basic parser testing

2. **Medium** (`c4_*.mmd`, `simple_architecture.d2`, `architecture_system.dot`):
   - 5-10 components
   - Nested containers/clusters
   - Multiple connection types
   - Good for semantic inference testing

3. **Complex** (`complex_architecture.svg`):
   - 20+ components
   - Multiple system boundaries
   - Cross-cloud connections
   - Bidirectional and async connections
   - Good for stress testing and real-world scenarios

## Format-Specific Features

### Mermaid
- Supports C4 diagrams natively
- Subgraphs for grouping
- Style classes for visual customization
- Limited shape variety

### D2
- Excellent nested container support
- Clean, minimal syntax
- Shape variety (person, cylinder, queue, etc.)
- Direction control

### GraphViz DOT
- Powerful layout algorithms (dot, neato, fdp, etc.)
- Clusters with `subgraph cluster_*`
- Extensive shape library
- Fine-grained style control

### SVG
- Most flexible format
- Can embed semantic hints via `data-semantic` attributes
- Groups via `<g>` elements
- Direct browser rendering

## Using with diacea

### Parsing Examples

```bash
# Parse Excalidraw (existing)
diacea -i diagram.json -f c4

# Parse TLDraw (Phase 5)
diacea -i diagram.tldr --input-format tldraw -f mermaid

# Parse SVG (Phase 6)
diacea -i simple_architecture.svg --input-format svg -f d2
```

### Generating Examples

```bash
# Generate Mermaid (Phase 2)
diacea -i input.json -f mermaid

# Generate GraphViz (Phase 3)
diacea -i input.json -f graphviz --graphviz-direction LR

# Generate D2 (Phase 4)
diacea -i input.json -f d2 --d2-sketch
```

## Expected Conversion Results

When converting between formats, expect:

1. **Shape Mapping**:
   - Rectangles → boxes/containers
   - Circles/Ellipses → persons/databases (context-dependent)
   - Diamonds → decision nodes
   - Custom shapes → closest equivalent

2. **Hierarchy Preservation**:
   - Groups/clusters maintain nesting
   - Parent-child relationships preserved
   - System boundaries maintained

3. **Connection Types**:
   - Solid lines → directed connections
   - Dashed lines → async/optional connections
   - Labels preserved
   - Direction maintained

4. **Semantic Inference**:
   - "Database", "DB" → DATABASE type
   - "User", "Person" → PERSON type
   - Large containers → SYSTEM type
   - "Queue", "SQS" → QUEUE type
   - "Cloud", "EKS" → CLOUD type

## Contributing

When adding new test diagrams:

1. Create diagrams that demonstrate specific features
2. Include both simple and complex versions
3. Add semantic hints where applicable (especially in SVG)
4. Document expected conversion behavior
5. Update this README with new files

## Validation

To validate diagram correctness:

```bash
# Mermaid
mmdc -i file.mmd -o /dev/null

# D2
d2 file.d2 /dev/null

# GraphViz
dot -Tsvg file.dot > /dev/null

# SVG
xmllint --noout file.svg
```

## References

- [Mermaid Documentation](https://mermaid.js.org/)
- [D2 Language](https://d2lang.com/)
- [GraphViz Documentation](https://graphviz.org/documentation/)
- [SVG Specification](https://www.w3.org/TR/SVG2/)
- [C4 Model](https://c4model.com/)
