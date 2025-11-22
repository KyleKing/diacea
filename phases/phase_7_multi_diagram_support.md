# Phase 7: Multi-Diagram & Workspace Support

## Problem Statement

### The C4 Model Challenge

C4 diagrams exist in a hierarchy with shared elements across levels:

```
Context (Level 1)          Container (Level 2)        Component (Level 3)
┌─────────────────┐       ┌──────────────────────┐   ┌─────────────────┐
│  [System A]     │  -->  │ System A {           │   │  API Service {  │
│                 │       │   [API Service]      │   │    [Handler]    │
│  [System B]     │       │   [Database]         │   │    [Router]     │
└─────────────────┘       │ }                    │   │  }              │
                          └──────────────────────┘   └─────────────────┘

Same element "System A" appears at different zoom levels with:
- Consistent ID/reference
- Consistent styling (colors, borders)
- Consistent labels/descriptions
- Drill-down relationships
```

**Current diacea limitation**: Converts ONE diagram at a time with no awareness of relationships to other diagrams.

### Similar Multi-Diagram Scenarios

| Use Case | Relationship Type | Examples |
|----------|------------------|----------|
| **C4 Model** | Hierarchical zoom | Context → Container → Component |
| **UML Suite** | Multiple views of same model | Class + Sequence + State diagrams |
| **Architecture Evolution** | Temporal | Before → During → After migration |
| **Microservices** | Nested detail | Landscape → Service internals → Data flows |
| **Network Architecture** | Different perspectives | Logical → Physical → Security zones |
| **Documentation** | Cross-references | Architecture → Deployment → Monitoring |

### Core Problem

1. **Element Reuse**: Same logical element appears in multiple diagrams
2. **Consistency**: Changes to element properties should propagate
3. **Navigation**: Users need drill-down/roll-up capabilities
4. **Styling**: Consistent colors/styles across related diagrams
5. **Validation**: Ensure references are valid across diagram set

## Proposed Solutions

### Option 1: Workspace Extension to diacea (Recommended)

Extend the Rich IR (Phase 1) with workspace concepts:

```python
# diacea/ir/workspace.py

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from .elements import Diagram, Element

@dataclass
class ElementDefinition:
    """Shared element definition that can be referenced across diagrams."""
    id: str
    label: str
    description: str = ""
    element_type: str = "component"  # system, container, component, etc.
    technology: str = ""
    style: Dict[str, any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, any] = field(default_factory=dict)


@dataclass
class DiagramView:
    """A view/diagram within a workspace, referencing shared elements."""
    id: str
    name: str
    diagram: Diagram
    view_type: str  # "context", "container", "component", "sequence", etc.
    zoom_level: int = 0  # C4: 1=Context, 2=Container, 3=Component, 4=Code
    parent_view: Optional[str] = None  # For drill-down relationships
    focused_element: Optional[str] = None  # Which element this zooms into
    element_refs: List[str] = field(default_factory=list)  # Elements used in this view


@dataclass
class Workspace:
    """Collection of related diagrams with shared element library."""
    id: str
    name: str
    description: str = ""

    # Shared element library - single source of truth
    elements: Dict[str, ElementDefinition] = field(default_factory=dict)

    # Multiple views/diagrams
    views: Dict[str, DiagramView] = field(default_factory=dict)

    # Metadata
    created: str = ""
    modified: str = ""
    author: str = ""
    version: str = "1.0.0"

    def get_element(self, element_id: str) -> Optional[ElementDefinition]:
        """Get element definition by ID."""
        return self.elements.get(element_id)

    def get_view(self, view_id: str) -> Optional[DiagramView]:
        """Get diagram view by ID."""
        return self.views.get(view_id)

    def get_related_views(self, view_id: str) -> List[DiagramView]:
        """Get views related to this one (parent, children, siblings)."""
        view = self.views.get(view_id)
        if not view:
            return []

        related = []

        # Parent view
        if view.parent_view:
            parent = self.views.get(view.parent_view)
            if parent:
                related.append(parent)

        # Child views
        for v in self.views.values():
            if v.parent_view == view_id:
                related.append(v)

        return related

    def validate_references(self) -> List[str]:
        """Validate that all element references in views exist in element library."""
        errors = []

        for view_id, view in self.views.items():
            for elem_ref in view.element_refs:
                if elem_ref not in self.elements:
                    errors.append(
                        f"View '{view_id}' references undefined element '{elem_ref}'"
                    )

        return errors

    def get_element_usage(self, element_id: str) -> List[str]:
        """Get list of views that use this element."""
        usage = []
        for view_id, view in self.views.items():
            if element_id in view.element_refs:
                usage.append(view_id)
        return usage


# Workspace format
@dataclass
class WorkspaceFormat:
    """Workspace file format specification."""

    # JSON structure
    # {
    #   "workspace": {
    #     "id": "ecommerce-platform",
    #     "name": "E-Commerce Platform",
    #     "elements": {
    #       "api-gateway": {
    #         "label": "API Gateway",
    #         "type": "container",
    #         "technology": "Node.js",
    #         "style": {"color": "#90EE90"}
    #       },
    #       ...
    #     },
    #     "views": {
    #       "context": {
    #         "name": "System Context",
    #         "type": "context",
    #         "level": 1,
    #         "file": "context.json",
    #         "elements": ["api-gateway", "user-service", ...]
    #       },
    #       "api-gateway-container": {
    #         "name": "API Gateway Containers",
    #         "type": "container",
    #         "level": 2,
    #         "parent": "context",
    #         "focus": "api-gateway",
    #         "file": "api-gateway.json",
    #         "elements": ["gateway-router", "auth-middleware", ...]
    #       }
    #     }
    #   }
    # }
    pass
```

#### Workspace CLI Usage

```bash
# Create workspace from multiple diagrams
diacea workspace create \
  --name "E-Commerce Platform" \
  --add context.json:context \
  --add containers.json:container \
  --add components.json:component \
  -o workspace.yml

# Validate workspace consistency
diacea workspace validate workspace.yml

# Generate all views in workspace
diacea workspace generate workspace.yml \
  --format mermaid \
  --output-dir ./output/

# Generate single view from workspace
diacea workspace view workspace.yml:context \
  --format graphviz \
  -o context.dot

# Update element styling across all views
diacea workspace style workspace.yml \
  --element api-gateway \
  --color blue \
  --update-all-views

# Show drill-down path
diacea workspace path workspace.yml \
  --from context \
  --to api-gateway-auth-component
```

### Option 2: Separate Tool - "diacea-studio"

Create a sibling tool focused on workspace management:

**diacea** (current tool):
- Single diagram conversion
- Input → IR → Output
- No multi-diagram awareness

**diacea-studio** (new tool):
- Workspace/model management
- Multi-diagram consistency
- Element library
- View generation
- Uses diacea as conversion engine

```bash
# diacea-studio commands
diacea-studio init "My Architecture"
diacea-studio element add api-gateway --type container --tech "Node.js"
diacea-studio element add database --type database --tech "PostgreSQL"

diacea-studio view create context --level 1
diacea-studio view create containers --level 2 --parent context

diacea-studio view add context api-gateway database
diacea-studio view generate context --format c4

# Export to various tools
diacea-studio export structurizr workspace.yml
diacea-studio export icepanel workspace.yml
diacea-studio export markdown workspace.yml

# Import from Structurizr DSL
diacea-studio import structurizr workspace.dsl
```

**Architecture**:
```
┌─────────────────┐
│ diacea-studio   │ - Workspace management
│                 │ - Element library
│                 │ - Multi-view generation
└────────┬────────┘
         │ uses
         ↓
┌─────────────────┐
│    diacea       │ - Single diagram conversion
│                 │ - Format parsers/generators
└─────────────────┘
```

### Option 3: Structurizr DSL Integration

Structurizr DSL already solves this problem! It's specifically designed for C4 with:
- Workspace concept
- Element definitions
- Multiple views
- Consistent styling
- Auto-layout

**Approach**: Make diacea a Structurizr DSL companion:

```bash
# Import Structurizr DSL to diacea IR
diacea import structurizr workspace.dsl -o workspace.yml

# Export diacea workspace to Structurizr DSL
diacea export structurizr workspace.yml -o workspace.dsl

# Use Structurizr as the "model", diacea for conversion
structurizr-cli export -workspace workspace.dsl -format json | \
  diacea convert -f mermaid
```

**Example Structurizr DSL**:
```
workspace "E-Commerce Platform" {
    model {
        user = person "Customer"

        system = softwareSystem "E-Commerce System" {
            webapp = container "Web Application" {
                technology "React"
            }
            api = container "API" {
                technology "Node.js"

                router = component "Router"
                auth = component "Auth Handler"
            }
            database = container "Database" {
                technology "PostgreSQL"
            }
        }

        user -> webapp "Uses"
        webapp -> api "Calls"
        api -> database "Reads/Writes"
    }

    views {
        systemContext system "Context" {
            include *
        }

        container system "Containers" {
            include *
        }

        component api "API_Components" {
            include *
        }
    }
}
```

## Recommended Approach

**Phase 7A: Workspace Support in diacea** (3 weeks)
- Add `Workspace` class to IR
- Implement workspace file format (YAML/JSON)
- CLI commands: `workspace create`, `validate`, `generate`
- Single tool, extended functionality

**Phase 7B: Optional - diacea-studio** (6-8 weeks)
- Visual workspace editor (web-based)
- Interactive element library
- Live preview
- Structurizr DSL import/export

**Phase 7C: Structurizr Integration** (2 weeks)
- Parser: Structurizr DSL → diacea Workspace
- Generator: diacea Workspace → Structurizr DSL
- Enables round-trip conversion

## Related Diagram Types Needing Multi-Diagram Support

### 1. C4 Model (PRIMARY)
- **Levels**: Context → Container → Component → Code
- **Shared elements**: Systems, containers, components
- **Styling**: Consistent colors/borders across levels
- **Navigation**: Drill-down from context to code

### 2. UML Multi-View
- **Views**: Class, Sequence, State, Activity, Deployment
- **Shared elements**: Classes, interfaces, objects
- **Consistency**: Same class appears in multiple diagrams
- **Example**: E-commerce system with class diagram + checkout sequence diagram

### 3. Microservices Architecture
- **Levels**: Landscape → Service internals → Data flows
- **Shared elements**: Services, databases, queues
- **Multiple perspectives**: Logical, deployment, security

### 4. Network Architecture
- **Views**: Logical topology, Physical topology, Security zones, Data flows
- **Shared elements**: Devices, connections, zones
- **Consistency**: Same router in logical and physical views

### 5. Architecture Decision Records (ADRs)
- **Temporal**: Before → Current → Proposed
- **Shared elements**: Systems evolving over time
- **Change tracking**: What changed between versions

### 6. Event Storming / Domain-Driven Design
- **Views**: Big picture, Process modeling, Software design
- **Shared elements**: Aggregates, events, commands
- **Consistency**: Events referenced across views

### 7. Data Flow Diagrams (DFD)
- **Levels**: Context (Level 0) → Level 1 → Level 2
- **Shared elements**: Processes, data stores, external entities
- **Decomposition**: Process explosion to show internals

## Implementation Specification

### Workspace File Format

```yaml
# workspace.yml
workspace:
  id: ecommerce-platform
  name: E-Commerce Platform
  version: 1.0.0
  author: Architecture Team

  # Shared element library
  elements:
    api-gateway:
      label: API Gateway
      type: container
      technology: Node.js + Express
      description: Routes requests to appropriate services
      style:
        color: "#90EE90"
        shape: hexagon
      tags:
        - web-tier
        - critical

    user-service:
      label: User Service
      type: container
      technology: Python + FastAPI
      style:
        color: "#87CEEB"

    user-db:
      label: User Database
      type: database
      technology: PostgreSQL
      style:
        color: "#FFE4B5"
        shape: cylinder

  # Views/Diagrams
  views:
    context:
      name: System Context
      type: c4-context
      level: 1
      description: High-level view of the e-commerce platform
      elements:
        - api-gateway
        - user-service
        - user-db
      file: diagrams/context.json

    api-gateway-detail:
      name: API Gateway Internals
      type: c4-container
      level: 2
      parent: context
      focus: api-gateway
      description: Detailed view inside API Gateway
      elements:
        - gateway-router
        - auth-middleware
        - rate-limiter
      file: diagrams/api-gateway.json

    user-flow:
      name: User Registration Flow
      type: sequence
      description: Sequence diagram for user registration
      elements:
        - user
        - api-gateway
        - user-service
        - user-db
      file: diagrams/user-registration-sequence.json
```

### Workspace Generators

```python
# diacea/generators/workspace_plantuml.py

def generate_workspace_plantuml(workspace: Workspace, view_id: str) -> str:
    """Generate PlantUML with consistent styling from workspace."""
    view = workspace.get_view(view_id)
    if not view:
        raise ValueError(f"View {view_id} not found")

    lines = ["@startuml"]

    # Add element definitions with consistent styling
    for elem_id in view.element_refs:
        elem_def = workspace.get_element(elem_id)
        if elem_def:
            # Apply workspace-level styling
            color = elem_def.style.get("color", "white")
            lines.append(f"rectangle \"{elem_def.label}\" as {elem_id} #{color}")

    # Add relationships from diagram
    # ... (use view.diagram for structure)

    lines.append("@enduml")
    return "\n".join(lines)
```

## Success Criteria

### Functional
- [ ] Create workspace from multiple diagrams
- [ ] Validate element references across views
- [ ] Generate consistent styling across all views
- [ ] Navigate drill-down relationships (parent/child views)
- [ ] Update element definition propagates to all views
- [ ] Export to Structurizr DSL
- [ ] Import from Structurizr DSL

### Technical
- [ ] Workspace YAML/JSON schema defined
- [ ] Validation catches missing references
- [ ] Performance: <1s to generate all views for 10 diagrams
- [ ] Type hints throughout
- [ ] 15+ test cases

### User Experience
- [ ] Clear error messages for reference issues
- [ ] CLI commands feel natural
- [ ] Documentation with real-world examples
- [ ] Migration path from single diagrams to workspace

## Open Questions

1. **Workspace Format**: YAML vs JSON vs custom DSL?
   - Suggestion: YAML for human readability, JSON for machine processing

2. **Element Library Scope**: How to handle element variations across views?
   - Example: "System A" is a box in context, a boundary in container view
   - Suggestion: Element definition is abstract, view controls rendering

3. **Structurizr Compatibility**: Full compatibility or subset?
   - Suggestion: Support import/export of common features, not all Structurizr features

4. **Version Control**: How to handle workspace evolution?
   - Suggestion: Workspace version field, migration scripts

5. **Collaborative Editing**: Should workspace support merge/conflict resolution?
   - Suggestion: Out of scope for v1, design file format to be git-friendly

6. **Cross-Workspace References**: Can one workspace reference another?
   - Example: Microservice workspace referencing platform workspace
   - Suggestion: Not in v1, add later if needed

## Related Tools & Prior Art

### Structurizr
- **Strengths**: Purpose-built for C4, excellent workspace model
- **Weaknesses**: Proprietary, Java-based, limited format support
- **How diacea complements**: Structurizr as source → diacea converts to other formats

### IcePanel
- **Strengths**: Visual C4 editor, real-time collaboration
- **Weaknesses**: SaaS only, no local tooling
- **How diacea complements**: Export from IcePanel → diacea converts

### Archi (ArchiMate)
- **Strengths**: Enterprise architecture, viewpoint management
- **Weaknesses**: Complex, steep learning curve
- **How diacea complements**: Different domain (EA vs software architecture)

### PlantUML !include
- **Strengths**: Can reference other files
- **Weaknesses**: No shared element library, manual consistency
- **How diacea complements**: Workspace generates consistent PlantUML files

### Mermaid (no workspace support)
- **Limitation**: No built-in workspace concept
- **How diacea helps**: Generate multiple consistent Mermaid files from workspace

## Implementation Timeline

### Phase 7A: Basic Workspace (3 weeks)
- Week 1: Workspace IR classes, file format spec
- Week 2: CLI commands (create, validate, generate)
- Week 3: Generators with workspace awareness, tests

### Phase 7B: Advanced Features (2 weeks)
- Week 4: Drill-down navigation, element usage tracking
- Week 5: Workspace refactoring tools, migration helpers

### Phase 7C: Structurizr Integration (2 weeks)
- Week 6: Structurizr DSL parser
- Week 7: Structurizr DSL generator, round-trip tests

**Total: 7 weeks**

## Recommendation Summary

1. **Extend diacea with workspace support** (Option 1) for Phase 7
   - Natural evolution of the IR model
   - Leverages existing infrastructure
   - Keeps everything in one tool

2. **Integrate with Structurizr DSL** (Option 3)
   - Don't reinvent the workspace wheel
   - Structurizr DSL is industry standard for C4
   - diacea becomes the universal converter

3. **Consider diacea-studio later** (Option 2) if there's demand
   - Visual workspace editor
   - Web-based interface
   - Uses diacea as engine

This gives users flexibility:
- Simple use case: Single diagram conversion (current diacea)
- C4 architecture: Structurizr DSL → diacea conversion
- Complex multi-view: diacea workspace management
