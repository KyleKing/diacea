# Scripts

- `render_fixtures.py`: convert diagrams to every output format, check each result, and build an HTML page for visual review. Defaults to the curated fixtures; pass any files or directories. See the module docstring for the checks and outputs
- `benchmark.py`: time parsing and generation on synthetic diagrams
- `check_imports.py`: verify the package imports cleanly

```bash
uv run python scripts/render_fixtures.py --out review
uv run python scripts/render_fixtures.py my_sketch.excalidraw docs/diagrams --out review
```
