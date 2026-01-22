# Developer Guide

This guide covers how to set up, develop, test, and contribute to diacea.

## Local Development Setup

### Prerequisites

- Python 3.10 or higher
- [Poetry](https://python-poetry.org/) for dependency management

### Installation

```bash
git clone https://github.com/kyleking/diacea.git
cd diacea
poetry install --sync
poetry run calcipy-pack pack.install-extras
```

### Available Tasks

The project uses `calcipy` for task management. See available tasks:

```bash
poetry run calcipy
# Or use the local 'run' file
./run
```

Run the default task list (lint, auto-format, test coverage, etc.):

```bash
./run main
```

Make code changes and run specific tasks as needed:

```bash
./run lint.fix test
```

## Code Structure

```
diacea/
├── diacea/
│   ├── __init__.py           # Package version
│   ├── cli.py                # Main CLI entry point
│   ├── workspace_cli.py      # Workspace management CLI
│   ├── workspace_format.py   # Workspace file format (YAML)
│   ├── ir/                   # Intermediate Representation
│   │   ├── elements.py       # Core IR elements (Shape, Connection, etc.)
│   │   ├── semantic.py       # Semantic type inference
│   │   └── workspace.py      # Workspace IR classes
│   ├── parsers/              # Input format parsers
│   │   ├── excalidraw.py     # Excalidraw JSON parser
│   │   ├── tldraw.py         # TLDraw JSON parser
│   │   └── svg.py            # SVG parser
│   └── generators/           # Output format generators
│       ├── plantuml.py       # PlantUML and C4-PlantUML
│       ├── mermaid.py        # Mermaid diagrams
│       ├── graphviz.py       # GraphViz DOT format
│       └── d2.py             # D2 diagrams
├── tests/
│   ├── test_ir_integration.py    # IR and generator tests
│   ├── test_tldraw_parser.py     # TLDraw parser tests
│   ├── test_svg_parser.py        # SVG parser tests
│   └── test_workspace.py         # Workspace tests
├── scripts/             # Utility scripts
└── docs/                # Documentation
```

### Key Modules

- **`diacea.ir`**: Intermediate Representation for format-agnostic diagram conversion
- **`diacea.parsers`**: Input format parsers (Excalidraw, TLDraw, SVG)
- **`diacea.generators`**: Output format generators (PlantUML, C4, Mermaid, GraphViz, D2)
- **`diacea.cli`**: Command-line interface

## Testing

Run tests:

```bash
./run test
```

Or with pytest directly:

```bash
poetry run pytest
```

### Test Data

Test fixtures are located in `tests/data/`:
- `excalidraw.json`: Sample Excalidraw export for testing

All algorithms are tested against the same input to ensure consistent output format.

## Code Style

### Git Commit Messages

We use [Commitizen](https://github.com/commitizen-tools/commitizen) to manage auto-generated changelogs and version increments following [semver](https://semver.org/). Please follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) style.

#### Commit Format

```
type(scope): description
```

**Types:**
- `fix`: A bug fix (PATCH version)
- `feat`: A new feature (MINOR version)
- `docs`: Documentation-only changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `perf`: Performance improvements
- `test`: Adding or updating tests
- `build`: Build system or dependency changes
- `ci`: CI configuration changes
- Add `!` for breaking changes (MAJOR version)

**Scopes:**
- Class name, file name, issue number, or other appropriate noun
- Examples: `build(poetry): bump requests to v3`, `style(#32): add missing type annotations`

**Description Guidelines:**
- Use lowercase and present tense
- Be concise but descriptive
- Examples:
  - `fix(converter): bug in parent rectangle detection`
  - `feat(cli): add command-line interface`
  - `refactor(parsers): consolidate input format detection`

### Python Style

The project uses:
- **Ruff** for linting and formatting
- **mypy** for type checking
- **Google-style** docstrings

Key style rules:
- Line length: 120 characters
- Use single quotes for strings
- Type hints required for all functions
- Follow PEP 8 with project-specific overrides

Run linting:

```bash
./run lint.fix
```

## Publishing

### Test Publishing

For testing, create an account on [TestPyPi](https://test.pypi.org/legacy/). Replace `...` with your API token:

```bash
poetry config repositories.testpypi https://test.pypi.org/legacy/
poetry config pypi-token.testpypi ...

./run main pack.publish --to-test-pypi
```

### Production Publishing

To publish to PyPI:

```bash
poetry config pypi-token.pypi ...

./run release
```

For pre-releases:

```bash
./run release --suffix=rc
```

## Scripts

The `scripts/` directory contains utility scripts for development:

- `check_imports.py`: Validates that all package imports work correctly

Use these scripts for prototyping or creating reference examples.

## Current Status

### Test Coverage

<!-- {cts} COVERAGE -->
| File                                  | Statements | Missing | Excluded | Coverage |
|---------------------------------------|-----------:|--------:|---------:|---------:|
| `diacea/__init__.py`                  | 4          | 0       | 0        | 100.0%   |
| `diacea/_runtime_type_check_setup.py` | 13         | 0       | 37       | 100.0%   |
| **Totals**                            | 17         | 0       | 37       | 100.0%   |

Generated on: 2024-12-12
<!-- {cte} -->

Note: Coverage table may be outdated. Run `./run test` for current coverage.

## Development Workflow

1. **Create a branch** for your feature or fix
2. **Write tests** first (TDD approach recommended)
3. **Implement** the feature
4. **Run tests and linting**: `./run main`
5. **Commit** using conventional commit format
6. **Push** and create a pull request

## Issue Labels and Milestones

- **Current Tasks**: Main milestone for active work
- **Next Tasks**: Planned but not yet started
- **Blue Sky**: Future ideas and enhancements

## Resources

- [Python Style Guides](https://docs.python-guide.org/writing/style/)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [Semantic Versioning](https://semver.org/)
- [Git Best Practices](https://chris.beams.io/posts/git-commit/)

