# Developer Notes

## Local Development

```sh
git clone https://github.com/kyleking/diacea.git
cd diacea
uv sync --all-extras

# See the available tasks
uv run calcipy
# Or use a local 'run' file (so that 'calcipy' can be extended)
./run

# Run the default task list (lint, auto-format, test coverage, etc.)
./run main

# Make code changes and run specific tasks as needed:
./run lint.fix test
```

### Maintenance

Dependency upgrades can be accomplished with:

```sh
uv lock --upgrade
uv sync --all-extras
```

## Publishing

Publishing is automated via GitHub Actions using PyPI Trusted Publishing. Tag creation triggers automated publishing.

```sh
./run release              # Bumps version, creates tag, pushes → triggers publish
./run release --suffix=rc  # For pre-releases
```

### Initial Setup

One-time setup to enable PyPI Trusted Publishing:

**Configure GitHub Environments**

Repository Settings → Environments:
- Create `testpypi` environment (no protection rules)
- Create `pypi` environment with "Required reviewers" enabled

**Register Trusted Publishers**

PyPI: https://pypi.org/manage/project/diacea/settings/publishing/
- Owner: `kyleking`
- Repository: `diacea`
- Workflow: `publish.yml`
- Environment: `pypi`
    - Or environment `testpypi` (for [TestPyPI](https://test.pypi.org/manage/account/publishing))

### Manual Publishing

For emergency manual publish:

```sh
export UV_PUBLISH_TOKEN=pypi-...
uv build
uv publish
```

## Current Status

<!-- {cts} COVERAGE -->
| File                                  | Statements | Missing | Excluded | Coverage |
|---------------------------------------|-----------:|--------:|---------:|---------:|
| `diacea/__init__.py`                  | 4          | 0       | 0        | 100.0%   |
| `diacea/_runtime_type_check_setup.py` | 13         | 0       | 37       | 100.0%   |
| `diacea/cli.py`                       | 290        | 16      | 0        | 94.4%    |
| `diacea/generators/__init__.py`       | 5          | 0       | 0        | 100.0%   |
| `diacea/generators/_text.py`          | 7          | 0       | 0        | 100.0%   |
| `diacea/generators/d2.py`             | 192        | 2       | 0        | 97.0%    |
| `diacea/generators/graphviz.py`       | 134        | 5       | 0        | 94.1%    |
| `diacea/generators/mermaid.py`        | 238        | 11      | 0        | 92.7%    |
| `diacea/generators/plantuml.py`       | 187        | 6       | 0        | 94.5%    |
| `diacea/ingestion.py`                 | 119        | 12      | 0        | 87.7%    |
| `diacea/ir/__init__.py`               | 5          | 0       | 0        | 100.0%   |
| `diacea/ir/base.py`                   | 9          | 0       | 0        | 100.0%   |
| `diacea/ir/elements.py`               | 107        | 5       | 0        | 94.6%    |
| `diacea/ir/semantic.py`               | 154        | 21      | 0        | 86.2%    |
| `diacea/ir/workspace.py`              | 98         | 3       | 0        | 93.8%    |
| `diacea/markdown_fences.py`           | 73         | 12      | 0        | 80.2%    |
| `diacea/mkdocs_plugin.py`             | 9          | 0       | 0        | 100.0%   |
| `diacea/parsers/__init__.py`          | 7          | 0       | 0        | 100.0%   |
| `diacea/parsers/excalidraw.py`        | 268        | 24      | 0        | 89.1%    |
| `diacea/parsers/mermaid.py`           | 416        | 18      | 0        | 94.2%    |
| `diacea/parsers/obsidian.py`          | 29         | 3       | 0        | 89.2%    |
| `diacea/parsers/plantuml.py`          | 379        | 20      | 0        | 93.5%    |
| `diacea/parsers/svg.py`               | 525        | 47      | 0        | 88.4%    |
| `diacea/parsers/tldraw.py`            | 353        | 48      | 0        | 83.0%    |
| `diacea/workspace_cli.py`             | 167        | 10      | 2        | 91.5%    |
| `diacea/workspace_format.py`          | 50         | 3       | 0        | 92.2%    |
| **Totals**                            | 3838       | 266     | 39       | 91.1%    |

Generated on: 2026-09-02
<!-- {cte} -->
