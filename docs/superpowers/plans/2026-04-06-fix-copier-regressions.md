# Fix Copier-Restore Regressions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore six content regressions introduced by `copier-auto-update` that reset project-specific content back to template defaults.

**Architecture:** All changes are config/documentation edits — no logic, no new tests. Each task is a focused file edit followed by a commit. Tasks are independent and can be done in any order, but Task 1 is the most critical (missing deps will break installs).

**Tech Stack:** `pyproject.toml` (PEP 517/uv), Markdown

---

## Files Modified

- Modify: `pyproject.toml` — restore description, dependencies, dev deps, add `[project.scripts]`
- Modify: `README.md` — restore full project description (overwritten by template stub)
- Modify: `docs/README.md` — fix `poetry add` install instruction → `pip install`

---

### Task 1: Restore pyproject.toml project description

**Files:**

- Modify: `pyproject.toml:26`

The copier restore reset `description` to `"TBD"`. The intended value (from `pyproject.toml.rej`) is `"Convert between Excalidraw and PlantUML"`.

- [ ] **Step 1: Edit the description field**

In `pyproject.toml`, change line 26:

```toml
description = "TBD"
```

to:

```toml
description = "Convert between Excalidraw and PlantUML"
```

- [ ] **Step 2: Verify the change**

Run:

```bash
grep 'description' pyproject.toml
```

Expected output:

```
description = "Convert between Excalidraw and PlantUML"
```

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "fix: restore project description after copier update"
```

---

### Task 2: Restore pyproject.toml project dependencies

**Files:**

- Modify: `pyproject.toml:23-25`

The copier restore stripped three runtime dependencies. The committed `HEAD` version had:

```
dependencies = ['corallium>=2.2.0', 'networkx>=3.4.2,<4', 'python-constraint2>=2.0.0b8,<3', 'pyyaml>=6.0,<7']
```

The staged version has only `"corallium>=2.2.0"`.

- [ ] **Step 1: Replace the dependencies block**

In `pyproject.toml`, find:

```toml
dependencies = [
  "corallium>=2.2.0",
]
```

Replace with:

```toml
dependencies = [
  "corallium>=2.2.0",
  "networkx>=3.4.2,<4",
  "python-constraint2>=2.0.0b8,<3",
  "pyyaml>=6.0,<7",
]
```

- [ ] **Step 2: Verify**

Run:

```bash
grep -A6 '^dependencies' pyproject.toml
```

Expected:

```toml
dependencies = [
  "corallium>=2.2.0",
  "networkx>=3.4.2,<4",
  "python-constraint2>=2.0.0b8,<3",
  "pyyaml>=6.0,<7",
]
```

- [ ] **Step 3: Sync the lock file**

Run:

```bash
uv sync
```

Expected: resolves without error and updates `uv.lock`.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "fix: restore stripped project dependencies after copier update"
```

---

### Task 3: Restore dev dependency group

**Files:**

- Modify: `pyproject.toml:6-8`

The copier restore removed `calcipy[dev]>=5.0.0` from `[dependency-groups].dev`. Only `calcipy[recommended]>=6.0.0b3` was kept.

- [ ] **Step 1: Add the missing dev dependency**

In `pyproject.toml`, find:

```toml
[dependency-groups]
dev = [
  "calcipy[recommended]>=6.0.0b3",
]
```

Replace with:

```toml
[dependency-groups]
dev = [
  "calcipy[dev]>=5.0.0",
  "calcipy[recommended]>=6.0.0b3",
]
```

- [ ] **Step 2: Verify**

Run:

```bash
grep -A5 '^\[dependency-groups\]' pyproject.toml
```

Expected:

```toml
[dependency-groups]
dev = [
  "calcipy[dev]>=5.0.0",
  "calcipy[recommended]>=6.0.0b3",
]
```

- [ ] **Step 3: Sync the lock file**

Run:

```bash
uv sync
```

Expected: resolves without error.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "fix: restore calcipy[dev] dev dependency after copier update"
```

---

### Task 4: Add missing [project.scripts] entry points

**Files:**

- Modify: `pyproject.toml` — add new `[project.scripts]` section

Both `diacea/cli.py` and `diacea/workspace_cli.py` exist but are not registered as console scripts. The `pyproject.toml.rej` shows these were `[tool.poetry.scripts]` entries that were never migrated to `[project.scripts]`.

- [ ] **Step 1: Confirm entry point functions exist**

Run:

```bash
grep -n '^def main' diacea/cli.py diacea/workspace_cli.py
```

Expected:

```
diacea/cli.py:NN:def main(...)
diacea/workspace_cli.py:NN:def main_workspace(...)
```

If the function names differ from `main` / `main_workspace`, adjust the entry points in the next step accordingly.

- [ ] **Step 2: Add [project.scripts] section**

In `pyproject.toml`, insert a new section immediately after `[project.urls]` (currently ending around line 39). Add:

```toml
[project.scripts]
diacea = "diacea.cli:main"
diacea-workspace = "diacea.workspace_cli:main_workspace"
```

- [ ] **Step 3: Verify the section is present**

Run:

```bash
grep -A3 '^\[project.scripts\]' pyproject.toml
```

Expected:

```toml
[project.scripts]
diacea = "diacea.cli:main"
diacea-workspace = "diacea.workspace_cli:main_workspace"
```

- [ ] **Step 4: Reinstall and smoke-test the CLI**

Run:

```bash
uv sync
uv run diacea --help
```

Expected: diacea help text appears without `ModuleNotFoundError`.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml
git commit -m "fix: add missing [project.scripts] CLI entry points"
```

---

### Task 5: Restore README.md project content

**Files:**

- Modify: `README.md`

The copier restore replaced the full project README with a 3-line template stub (`# diacea\n\nTBD\n...`). The full content from `HEAD` must be restored exactly.

- [ ] **Step 1: Replace README.md with the committed content**

Overwrite `README.md` with the following content (verbatim from `git show HEAD:README.md`):

````markdown
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
````

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

| Format          | Parser             | Auto-detect |
| --------------- | ------------------ | ----------- |
| Excalidraw JSON | `ExcalidrawParser` | Yes         |
| TLDraw JSON     | `TLDrawParser`     | Yes         |
| SVG             | `SVGParser`        | Yes         |

### Output Formats

| Format       | Generator             | Options                                    |
| ------------ | --------------------- | ------------------------------------------ |
| PlantUML     | `PlantUMLGenerator`   | -                                          |
| C4-PlantUML  | `C4PlantUMLGenerator` | -                                          |
| Mermaid      | `MermaidGenerator`    | `--mermaid-type` (flowchart, c4, sequence) |
| GraphViz DOT | `GraphVizGenerator`   | `--graphviz-direction`, `--graphviz-type`  |
| D2           | `D2Generator`         | `--d2-direction`, `--d2-sketch`            |

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

````

- [ ] **Step 2: Verify first and last lines**

Run:
```bash
head -5 README.md && echo "---" && tail -3 README.md
````

Expected:

```
# diacea

Universal diagram converter - the pandoc for diagrams
---
- **Changelog**: [docs/docs/CHANGELOG.md](docs/docs/CHANGELOG.md)
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "fix: restore README content overwritten by copier template reset"
```

---

### Task 6: Fix docs/README.md install instruction

**Files:**

- Modify: `docs/README.md:7`

The newly added template file has `poetry add diacea` on line 7. The project uses uv and the install instruction in `README.md` uses `pip install diacea`.

- [ ] **Step 1: Fix the install instruction**

In `docs/README.md`, find:

```markdown
1. `poetry add diacea`
```

Replace with:

```markdown
1. `pip install diacea`
```

- [ ] **Step 2: Verify**

Run:

```bash
grep 'install\|add' docs/README.md
```

Expected: no `poetry` references remain.

- [ ] **Step 3: Commit**

```bash
git add docs/README.md
git commit -m "fix: update docs/README install instruction from poetry to pip"
```

---

## Self-Review

**Spec coverage:**

- Issue 1 (description) → Task 1
- Issue 2 (dependencies stripped) → Task 2
- Issue 3 (dev dep dropped) → Task 3
- Issue 4 (missing scripts) → Task 4
- Issue 5 (README.md reset) → Task 5
- Issue 6 (poetry add in docs/README.md) → Task 6

All six issues covered.

**Placeholder scan:** No TBD/TODO/placeholder steps. All code blocks contain exact content.

**Type consistency:** No types — pure config/doc edits.

**Order note:** Task 2 and Task 3 both modify `pyproject.toml` and call `uv sync`. If run by the same agent in sequence, combine the `uv sync` + commit steps to avoid redundant lock file churn. If run in parallel by separate agents, each agent handles its own `uv sync`.
