"""Convert diagrams to every output format, check each result, and build a visual review page.

Usage:

    uv run python scripts/render_fixtures.py --out review
    uv run python scripts/render_fixtures.py my_sketch.excalidraw --out review

For each input the script writes, under <out>/:

- renders/: every generated format, plus an image of it when the format's
  native tool is on PATH (mmdc, d2, dot, plantuml)
- index.html: one row per input showing diacea's own drawing of what it read
  next to each native render, so a wrong label, a missing arrow, or a box in
  the wrong group is visible at a glance
- summary.txt / summary.json: one line per input x format with three checks:
  convert (generation succeeded), render (the native tool accepted the
  output), and reread (parsing the output back gives the same nodes, groups,
  and connections)

Exits nonzero when any check fails. A missing native tool is a skip, not a
failure, and the reread check needs no tools at all.
"""

from __future__ import annotations

import argparse
import html
import json
import shutil
import subprocess  # noqa: S404
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from diacea.formats import (
    INPUT_FORMATS,
    OUTPUT_FORMATS,
    ConversionResult,
    input_format_for_path,
    parse_file,
    render_diagram,
    verify_conversion,
)

DEFAULT_FIXTURE_DIR = Path(__file__).resolve().parents[1] / 'tests' / 'data' / 'curated'

# Output format -> (native renderer binary, file suffix of the image it writes)
RENDERERS = {
    'c4': ('plantuml', '.png'),
    'd2': ('d2', '.svg'),
    'graphviz': ('dot', '.svg'),
    'mermaid': ('mmdc', '.png'),
    'plantuml': ('plantuml', '.png'),
}


@dataclass
class Cell:
    """One input x format outcome in the review matrix."""

    fixture: str
    format: str
    convert: str
    render: str
    reread: str
    output: str = ''
    image: str = ''
    note: str = ''


def _reread(result: ConversionResult) -> tuple[str, str]:
    problems = verify_conversion(result)
    if problems is None:
        return ('n/a', '')
    return ('fail', '; '.join(problems)) if problems else ('ok', '')


def _render_command(renderer: str, source: Path, image: Path) -> list[str]:
    match renderer:
        case 'mmdc':
            return ['mmdc', '-i', str(source), '-o', str(image), '--scale', '2']
        case 'plantuml':
            return ['plantuml', '-tpng', '-o', str(image.parent), str(source)]
        case 'dot':
            return ['dot', '-Tsvg', str(source), '-o', str(image)]
        case 'd2':
            return ['d2', str(source), str(image)]
    msg = f'Unsupported renderer: {renderer}'
    raise ValueError(msg)


def _render(output_format: str, source: Path) -> tuple[str, Path | None, str]:
    if output_format == 'svg':
        return ('ok', source, '')
    if output_format not in RENDERERS:
        return ('n/a', None, '')
    renderer, image_suffix = RENDERERS[output_format]
    if shutil.which(renderer) is None:
        return ('skipped', None, f'{renderer} not installed')
    image = source.with_suffix(image_suffix) if renderer == 'plantuml' else Path(f'{source}{image_suffix}')
    result = subprocess.run(  # noqa: S603
        _render_command(renderer, source, image), capture_output=True, text=True, timeout=180, check=False
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().splitlines()
        return ('fail', None, detail[-1] if detail else f'exit {result.returncode}')
    return ('ok', image, '')


def _process_fixture(fixture: Path, renders_dir: Path) -> list[Cell]:
    try:
        parsed = parse_file(fixture)
    except ValueError as err:
        return [Cell(fixture.name, 'parse', 'fail', 'n/a', 'n/a', note=str(err))]

    cells = []
    for output_format, fmt in OUTPUT_FORMATS.items():
        suffix = '.c4.puml' if output_format == 'c4' else fmt.suffix
        try:
            result = render_diagram(parsed.diagram, output_format)
        except Exception as err:
            cells.append(Cell(fixture.name, output_format, 'fail', 'n/a', 'n/a', note=str(err)))
            continue
        converted = renders_dir / f'{fixture.name}{suffix}'
        converted.write_text(result.output if result.output.endswith('\n') else result.output + '\n', encoding='utf-8')
        render_state, image, render_note = _render(output_format, converted)
        reread_state, reread_note = _reread(result)
        cells.append(
            Cell(
                fixture.name,
                output_format,
                'ok',
                render_state,
                reread_state,
                output=str(converted),
                image=str(image) if image else '',
                note='; '.join(note for note in (render_note, reread_note) if note),
            )
        )
    return cells


def _collect_fixtures(paths: list[Path]) -> list[Path]:
    fixtures = []
    for path in paths:
        if path.is_dir():
            fixtures.extend(
                child
                for child in sorted(path.iterdir())
                if child.is_file() and input_format_for_path(child) is not None
            )
        else:
            fixtures.append(path)
    return fixtures


def _failed(cell: Cell) -> bool:
    return 'fail' in {cell.convert, cell.render, cell.reread}


def _format_summary(cells: list[Cell]) -> str:
    lines = [f'{"input":<40}{"format":<12}{"convert":<9}{"render":<9}{"reread":<8}note']
    lines.extend(
        f'{cell.fixture:<40}{cell.format:<12}{cell.convert:<9}{cell.render:<9}{cell.reread:<8}{cell.note}'
        for cell in cells
    )
    failures = sum(1 for cell in cells if _failed(cell))
    skips = sum(1 for cell in cells if cell.render == 'skipped')
    lines.extend(['', f'{len(cells)} cells: {failures} failed, {skips} renders skipped (tool not installed)'])
    return '\n'.join(lines) + '\n'


def _review_page(cells: list[Cell], out_dir: Path) -> str:
    """One row per input: diacea's own drawing first, then each native render."""
    rows = []
    by_fixture: dict[str, list[Cell]] = {}
    for cell in cells:
        by_fixture.setdefault(cell.fixture, []).append(cell)
    for fixture, fixture_cells in by_fixture.items():
        figures = []
        for cell in sorted(fixture_cells, key=lambda cell: cell.format != 'svg'):
            status = 'fail' if _failed(cell) else 'ok'
            caption = f'{cell.format} - {status}' + (f' ({html.escape(cell.note)})' if cell.note else '')
            if cell.image:
                relative = Path(cell.image).relative_to(out_dir)
                body = f'<a href="{relative}"><img src="{relative}" alt="{cell.format}"></a>'
            elif cell.output:
                body = f'<a href="{Path(cell.output).relative_to(out_dir)}">open {cell.format} text</a>'
            else:
                body = ''
            figures.append(f'<figure class="{status}"><figcaption>{caption}</figcaption>{body}</figure>')
        rows.append(f'<section><h2>{html.escape(fixture)}</h2><div class="row">{"".join(figures)}</div></section>')
    style = (
        'body{font-family:sans-serif;margin:1.5rem}h2{font-size:1rem;margin:1.5rem 0 .5rem}'
        '.row{display:flex;gap:1rem;overflow-x:auto;align-items:flex-start}'
        'figure{margin:0;border:1px solid #ccc;padding:.5rem;min-width:260px;max-width:420px}'
        'figure.fail{border-color:#c92a2a}figcaption{font-size:.8rem;margin-bottom:.4rem}'
        'img{max-width:400px;max-height:420px}'
    )
    intro = (
        '<h1>diacea conversion review</h1><p>First image in each row is diacea&rsquo;s own drawing of what it '
        'read from the input; the rest are the generated formats rendered by their native tools. '
        'Compare each row against the source diagram.</p>'
    )
    head = f'<!doctype html><meta charset="utf-8"><title>diacea review</title><style>{style}</style>'
    return f'{head}{intro}{"".join(rows)}\n'


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        'fixtures',
        nargs='*',
        type=Path,
        default=[DEFAULT_FIXTURE_DIR],
        help=f'Diagram files or directories in any of: {", ".join(sorted(INPUT_FORMATS))} (default: curated fixtures)',
    )
    parser.add_argument('--out', required=True, type=Path, help='Directory for renders, summaries, and index.html')
    args = parser.parse_args(argv)

    out_dir = args.out.resolve()
    renders_dir = out_dir / 'renders'
    renders_dir.mkdir(parents=True, exist_ok=True)

    cells: list[Cell] = []
    for fixture in _collect_fixtures(args.fixtures):
        cells.extend(_process_fixture(fixture, renders_dir))

    summary_text = _format_summary(cells)
    (out_dir / 'summary.txt').write_text(summary_text, encoding='utf-8')
    (out_dir / 'summary.json').write_text(
        json.dumps([asdict(cell) for cell in cells], indent=2) + '\n', encoding='utf-8'
    )
    (out_dir / 'index.html').write_text(_review_page(cells, out_dir), encoding='utf-8')
    print(summary_text, end='')
    print(f'Review page: {out_dir / "index.html"}')

    return 1 if any(_failed(cell) for cell in cells) else 0


if __name__ == '__main__':
    sys.exit(main())
