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
├── diacea/              # Main package
│   ├── __init__.py      # Package initialization
│   ├── experiments.py   # Conversion algorithms
│   └── _runtime_type_check_setup.py  # Type checking config
├── tests/               # Test suite
│   ├── test_experiment.py  # Algorithm tests
│   └── data/            # Test fixtures
│       └── excalidraw.json
├── scripts/             # Utility scripts
└── docs/                # Documentation
```

### Key Modules

- **`diacea.experiments`**: Contains all conversion algorithms:
  - `convert_to_relative()`: Imperative approach
  - `rule_based_approach()`: Rule-based conversion
  - `csp_solver()`: Constraint satisfaction problem solver
  - `quadtree_approach()`: QuadTree spatial indexing
  - `graph_based_approach()`: NetworkX graph-based conversion

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
  - `refactor(experiments): consolidate algorithm implementations`

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

Note: Coverage is currently limited as the main conversion logic in `experiments.py` is not yet fully covered.

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

