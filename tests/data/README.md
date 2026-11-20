# Test Data

Static files used for package tests.

- `curated/`: small hand-authored sources that each pin one behavior, with expected output for every format in `curated/goldens/` (see `curated/README.md`)
- `real/`: diagrams collected from public projects (see `real/README.md`)
- `mermaid/`, `plantuml/`, `svg/`, and the files at this level: parser fixtures

Every text and drawing fixture here also runs through `tests/test_any_to_any.py`, which converts it to each output format and checks that the result reads back with the same nodes, groups, and connections. To look at the conversions instead of asserting on them, run `uv run python scripts/render_fixtures.py --out review` and open `review/index.html`.
