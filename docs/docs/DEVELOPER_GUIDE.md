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
| `diacea/__init__.py`                  | 6          | 0       | 0        | 100.0%   |
| `diacea/_runtime_type_check_setup.py` | 13         | 0       | 37       | 100.0%   |
| `diacea/cli.py`                       | 279        | 18      | 0        | 92.5%    |
| `diacea/formats.py`                   | 238        | 15      | 0        | 92.0%    |
| `diacea/generators/__init__.py`       | 7          | 0       | 0        | 100.0%   |
| `diacea/generators/_text.py`          | 65         | 1       | 0        | 96.6%    |
| `diacea/generators/d2.py`             | 209        | 1       | 0        | 97.9%    |
| `diacea/generators/excalidraw.py`     | 121        | 5       | 0        | 93.5%    |
| `diacea/generators/graphviz.py`       | 160        | 4       | 0        | 96.1%    |
| `diacea/generators/mermaid.py`        | 247        | 11      | 0        | 93.3%    |
| `diacea/generators/plantuml.py`       | 143        | 1       | 0        | 97.8%    |
| `diacea/generators/svg.py`            | 90         | 6       | 0        | 92.3%    |
| `diacea/ingestion.py`                 | 91         | 4       | 0        | 92.9%    |
| `diacea/ir/__init__.py`               | 5          | 0       | 0        | 100.0%   |
| `diacea/ir/base.py`                   | 9          | 0       | 0        | 100.0%   |
| `diacea/ir/elements.py`               | 117        | 5       | 0        | 95.1%    |
| `diacea/ir/ids.py`                    | 58         | 2       | 0        | 96.3%    |
| `diacea/ir/semantic.py`               | 174        | 14      | 0        | 91.4%    |
| `diacea/ir/workspace.py`              | 98         | 3       | 0        | 93.8%    |
| `diacea/layout.py`                    | 302        | 5       | 0        | 97.7%    |
| `diacea/markdown_fences.py`           | 58         | 7       | 0        | 86.8%    |
| `diacea/mkdocs_plugin.py`             | 9          | 0       | 0        | 100.0%   |
| `diacea/parsers/__init__.py`          | 9          | 0       | 0        | 100.0%   |
| `diacea/parsers/d2.py`                | 328        | 17      | 0        | 93.2%    |
| `diacea/parsers/excalidraw.py`        | 379        | 25      | 0        | 91.8%    |
| `diacea/parsers/graphviz.py`          | 331        | 15      | 0        | 94.1%    |
| `diacea/parsers/mermaid.py`           | 432        | 16      | 0        | 95.2%    |
| `diacea/parsers/obsidian.py`          | 29         | 3       | 0        | 89.2%    |
| `diacea/parsers/plantuml.py`          | 346        | 12      | 0        | 95.6%    |
| `diacea/parsers/svg.py`               | 584        | 46      | 0        | 89.8%    |
| `diacea/parsers/tldraw.py`            | 353        | 48      | 0        | 83.0%    |
| `diacea/workspace_cli.py`             | 167        | 10      | 2        | 91.5%    |
| `diacea/workspace_format.py`          | 50         | 3       | 0        | 92.2%    |
| **Totals**                            | 5507       | 297     | 39       | 93.0%    |

Generated on: 2026-11-20
<!-- {cte} -->
