# diacea Ecosystem & Integration Strategy

This document explores how diacea fits into the broader diagramming ecosystem and potential integrations with related tools.

## Core Value Proposition

**diacea**: Universal diagram converter - the "pandoc for diagrams"

**Unique Position**:
- Format-agnostic conversion engine
- Rich semantic understanding
- Python-native (embeddable)
- Open source

## Ecosystem Integration Opportunities

### 1. C4 Model Tools

#### Structurizr (Integration Priority: HIGH)

**What it does**: Commercial tool for C4 architecture diagrams with workspace management

**Integration Strategy**:
```
Structurizr DSL → diacea → [Mermaid, GraphViz, D2, ...]
                ← diacea ← [Excalidraw, TLDraw, SVG]
```

**Use Cases**:
- Export Structurizr diagrams to formats for GitHub/GitLab
- Import visual diagrams into Structurizr workspace
- Generate presentation slides from Structurizr models

**Implementation**: Phase 7C (Structurizr Integration)

**Example Flow**:
```bash
# Export Structurizr to Mermaid for GitHub README
structurizr-cli export -workspace workspace.dsl -format json | \
  diacea import structurizr - | \
  diacea workspace generate - --format mermaid --view context

# Import Excalidraw sketches into Structurizr
diacea -i sketch.json -f structurizr --workspace-id ecommerce | \
  structurizr-cli import
```

#### IcePanel (Integration Priority: MEDIUM)

**What it does**: SaaS platform for collaborative C4 diagrams

**Integration Strategy**:
- IcePanel API → JSON → diacea → other formats
- diacea → IcePanel import API

**Use Cases**:
- Backup IcePanel diagrams to version control (as Mermaid/D2)
- Generate IcePanel diagrams from existing architecture docs

**Implementation**: API integration (Phase 8+)

#### C4-PlantUML (Current Integration: BASIC)

**Status**: diacea already generates C4-PlantUML
**Enhancement**: Import C4-PlantUML back to IR (reverse direction)

### 2. Documentation Platforms

#### Docusaurus / MkDocs / VitePress (Integration Priority: HIGH)

**What they do**: Static site generators for documentation

**Integration Strategy**: diacea as build-time diagram generator

**Implementation**:
```javascript
// docusaurus.config.js plugin
module.exports = {
  plugins: [
    ['docusaurus-plugin-diacea', {
      inputDir: 'diagrams/',
      outputFormat: 'mermaid',  // Native Docusaurus support
      workspaceMode: true
    }]
  ]
}
```

**Use Cases**:
- Convert architecture diagrams during documentation build
- Keep source diagrams in Excalidraw (visual), render as Mermaid (embeddable)
- Generate multiple diagram formats for different output targets

#### Notion / Confluence (Integration Priority: MEDIUM)

**What they do**: Collaborative documentation platforms

**Integration Strategy**:
- Export from Notion/Confluence → diacea → update diagrams → reimport
- Notion API integration for diagram blocks

**Challenges**: Limited import capabilities in these platforms

### 3. Architecture as Code Platforms

#### Diagrams (Python) (Integration Priority: HIGH)

**What it does**: Python library for cloud architecture diagrams

```python
from diagrams import Diagram
from diagrams.aws.compute import EC2
from diagrams.aws.database import RDS

with Diagram("Web Service"):
    web = EC2("web")
    db = RDS("userdb")
    web >> db
```

**Integration Strategy**:
```python
# diacea as output format for Diagrams
from diagrams import Diagram
from diacea.integrations.diagrams import DiaceaRenderer

with Diagram("Web Service", renderer=DiaceaRenderer(format="d2")):
    ...
```

**Bidirectional**:
- Diagrams Python → diacea IR → any format
- Visual tools → diacea IR → Diagrams Python code

#### Terraform Graph (Integration Priority: MEDIUM)

**What it does**: Generates dependency graphs from Terraform

**Integration Strategy**:
```bash
terraform graph | diacea import terraform-dot - | \
  diacea generate --format c4 --semantic-inference
```

**Use Cases**:
- Convert infrastructure-as-code to architecture diagrams
- Semantic inference: RDS resources → Database shapes
- Automatic documentation from infrastructure

#### Pulumi (Integration Priority: LOW)

**What it does**: Infrastructure as code in real programming languages

**Integration Strategy**: Similar to Terraform, but would need custom parser

### 4. Diagramming Tools

#### Draw.io / diagrams.net (Integration Priority: HIGH)

**What it does**: Popular open-source diagramming tool

**Integration Strategy**:
- Draw.io XML → diacea IR → other formats
- diacea → Draw.io XML (for editing)

**Implementation**: Phase 8 (Draw.io Parser)

**Use Cases**:
- Convert existing Draw.io diagrams to code-based formats
- Enable version control for Draw.io diagrams
- Collaborative editing in Draw.io, rendering in Mermaid/D2

#### Lucidchart (Integration Priority: MEDIUM)

**What it does**: Commercial diagramming tool

**Integration Strategy**: Via Lucidchart API or export formats
**Challenges**: Proprietary format, limited API access

#### Miro / FigJam (Integration Priority: LOW)

**What they do**: Collaborative whiteboards with diagramming

**Integration Strategy**: API-based, extract diagram elements
**Challenges**: Freeform nature, hard to extract structured diagrams

#### Excalidraw (Current Integration: GOOD)

**Status**: Primary input format ✅
**Enhancement**: Excalidraw library metadata for semantic hints

#### TLDraw (Integration Priority: HIGH)

**Status**: Planned for Phase 5
**Integration**: Full import support

### 5. CI/CD & Development Tools

#### GitHub Actions / GitLab CI (Integration Priority: HIGH)

**What they do**: Automated workflows

**Integration Strategy**:
```yaml
# .github/workflows/diagrams.yml
name: Generate Diagrams
on: [push]
jobs:
  diagrams:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Generate diagrams
        run: |
          pip install diacea
          diacea workspace generate workspace.yml \
            --format mermaid \
            --output-dir docs/diagrams/
      - name: Commit updated diagrams
        run: |
          git add docs/diagrams/
          git commit -m "Update generated diagrams"
          git push
```

**Use Cases**:
- Automatic diagram generation on commit
- Validate workspace consistency in PR checks
- Generate multiple format variants for different platforms

#### Pre-commit Hooks (Integration Priority: HIGH)

**Integration Strategy**:
```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: diacea-workspace-validate
        name: Validate diagram workspace
        entry: diacea workspace validate
        language: python
        files: workspace\.yml$

      - id: diacea-generate
        name: Generate diagrams
        entry: diacea workspace generate workspace.yml --format mermaid
        language: python
        files: workspace\.yml|diagrams/.*\.json$
        pass_filenames: false
```

**Use Cases**:
- Validate workspace before commit
- Auto-generate output diagrams
- Ensure consistency

### 6. Visualization & Rendering

#### Graphviz (Integration Priority: HIGH)

**Status**: Planned for Phase 3 (output generation)
**Enhancement**: Import Graphviz DOT files (reverse direction)

#### Mermaid (Integration Priority: HIGH)

**Status**: Planned for Phase 2 (output generation)
**Enhancement**: Parse Mermaid back to IR (round-trip)

#### D2 (Integration Priority: HIGH)

**Status**: Planned for Phase 4 (output generation)
**Enhancement**: Parse D2 back to IR (round-trip)

#### PlantUML (Current Integration: GOOD)

**Status**: Output generation ✅
**Enhancement**: PlantUML parser (Phase 9)

### 7. AI & Machine Learning Tools

#### GPT-4 / Claude / LLMs (Integration Priority: MEDIUM)

**What they do**: Generate diagrams from natural language

**Integration Strategy**:
```python
# Example: LLM generates Mermaid, diacea converts to workspace
llm_output = claude.generate("Create a microservices architecture for e-commerce")
# LLM returns Mermaid diagram

# Parse to workspace for consistency
diacea.parse_mermaid(llm_output) | \
  diacea.workspace.add_view("llm-generated") | \
  diacea.workspace.validate()
```

**Use Cases**:
- LLM generates initial diagram
- diacea normalizes to workspace format
- Human refines in preferred tool
- diacea maintains consistency

#### Diagram Recognition / OCR (Integration Priority: LOW)

**What it does**: Extract diagrams from images/PDFs

**Integration Strategy**:
- Image → ML model → structural JSON → diacea IR
- Whiteboard photo → architecture diagram

**Challenges**: Complex ML problem, low accuracy

### 8. Database & Schema Tools

#### SchemaSpy / dbdocs (Integration Priority: MEDIUM)

**What they do**: Generate database documentation from schema

**Integration Strategy**:
```bash
# Database schema → diacea → architecture diagrams
schemaspy -o schema.json | \
  diacea import database-schema - | \
  diacea generate --format c4 --view data-model
```

**Use Cases**:
- Database ERD in multiple formats
- Include database schema in C4 container diagrams

#### SQL Alchemy / Django ORM (Integration Priority: LOW)

**What they do**: Python ORM frameworks

**Integration Strategy**: Extract model relationships → diacea IR → diagrams

## Workspace Management: Sibling Tool Strategy

### Option A: diacea-studio (Standalone Tool)

**Purpose**: Visual workspace editor and management

**Features**:
- Web-based UI for workspace editing
- Element library management
- Live preview of all views
- Collaborative editing
- Import from multiple sources

**Technology Stack**:
- Frontend: React + TypeScript
- Backend: FastAPI (Python)
- Storage: Git-backed (YAML files)
- Rendering: diacea as engine

**Usage Pattern**:
```bash
# Start local server
diacea-studio serve --workspace workspace.yml --port 3000

# Export to diacea format
diacea-studio export workspace --format diacea-workspace -o workspace.yml

# Import from various sources
diacea-studio import structurizr workspace.dsl
diacea-studio import icepanel --api-key $KEY
```

### Option B: diacea workspace (Integrated Subcommand)

**Purpose**: Workspace management within diacea CLI

**Advantages**:
- Single tool
- Simpler installation
- Consistent UX

**Disadvantages**:
- No visual interface
- Text-based editing only

**Recommendation**: Start with Option B (Phase 7), build Option A later if demand exists

## Integration Architecture Patterns

### Pattern 1: diacea as Converter Hub

```
         ┌──────────────┐
         │   diacea     │
         │   (Core IR)  │
         └──────┬───────┘
                │
    ┌───────────┼───────────┐
    ↓           ↓           ↓
┌────────┐  ┌────────┐  ┌────────┐
│ Input  │  │ Workspace│ │ Output │
│Parsers │  │ Manager  │ │Generators│
└────────┘  └────────┘  └────────┘
    ↑           ↑           ↓
    │           │           │
Excalidraw  Structurizr  Mermaid
TLDraw      C4 Model     GraphViz
SVG         Multi-view   D2
Draw.io                  PlantUML
```

### Pattern 2: diacea as Library

```python
# Embedded in other tools
from diacea import parse_excalidraw, generate_mermaid

# In a Docusaurus plugin
def process_diagram(source_file):
    diagram = parse_excalidraw(source_file)
    return generate_mermaid(diagram)

# In a CI/CD pipeline
from diacea.workspace import Workspace

ws = Workspace.load("architecture.yml")
ws.validate()
for view_id in ws.views:
    output = ws.generate_view(view_id, format="mermaid")
    save(f"docs/{view_id}.mmd", output)
```

### Pattern 3: diacea as Service

```yaml
# Docker Compose
services:
  diacea-api:
    image: diacea/api:latest
    ports:
      - "8000:8000"
    volumes:
      - ./workspaces:/workspaces

  docs:
    image: docusaurus
    depends_on:
      - diacea-api
    environment:
      DIAGRAM_CONVERTER_URL: http://diacea-api:8000
```

**API Endpoints**:
```
POST /convert
  Body: { "input": "...", "from": "excalidraw", "to": "mermaid" }

POST /workspace/validate
  Body: { workspace YAML }

GET /workspace/{id}/view/{view_id}?format=mermaid
```

## Competitive Analysis & Positioning

### Direct Competitors

| Tool | Strengths | Weaknesses | How diacea competes |
|------|-----------|------------|---------------------|
| **Structurizr** | C4 native, workspace model | Java, proprietary, limited formats | Partner (import/export), broader format support |
| **Mermaid Live** | Simple, GitHub integration | Single format | Multi-format hub, workspace management |
| **diagrams.net** | Feature-rich, popular | Desktop-focused, no workspace | Code-first alternative, version control |
| **Lucidchart** | Professional, collaborative | Commercial, proprietary | Open source, local-first, CI/CD friendly |

### Unique Value Propositions

1. **Format Agnostic**: Only tool supporting 10+ diagram formats
2. **Workspace-Aware**: Multi-diagram consistency (via Phase 7)
3. **Semantic Understanding**: Infers diagram types and element roles
4. **Python Native**: Embeddable in Python workflows
5. **Open Source**: Community-driven, transparent
6. **CLI-First**: Automation-friendly, CI/CD ready

## Monetization & Sustainability (If Applicable)

### Open Core Model

**Free (diacea)**:
- All conversion features
- Single diagram processing
- Basic workspace support
- CLI tool

**Commercial (diacea-studio Pro)**:
- Web-based workspace editor
- Real-time collaboration
- Enterprise SSO
- Hosted rendering service
- Priority support

### Service Model

**Free**:
- Self-hosted conversion

**Paid**:
- SaaS diagram conversion API
- Managed workspace hosting
- Integration marketplace

## Roadmap: Ecosystem Integration

### Near-term (2025)
- ✅ Phase 1-6: Core formats
- ⏳ Phase 7: Workspace support
- ⏳ Structurizr DSL integration
- ⏳ GitHub Actions integration
- ⏳ Docusaurus plugin

### Mid-term (2026)
- Draw.io parser
- PlantUML parser (reverse)
- Mermaid parser (reverse)
- diacea Python API documentation
- Terraform graph integration

### Long-term (2027+)
- diacea-studio (web interface)
- Notion/Confluence plugins
- Database schema integration
- AI-assisted diagram generation
- Collaborative workspace hosting

## Call to Action

The ecosystem is rich with opportunities for integration. Priority should be:

1. **Structurizr** - Solve the C4 multi-diagram problem definitively
2. **GitHub/GitLab** - Enable docs-as-code workflows
3. **Docusaurus/MkDocs** - Integrate into documentation sites
4. **diagrams.net** - Bridge visual and code-based diagramming

This positions diacea as the universal conversion layer for the entire diagramming ecosystem.
