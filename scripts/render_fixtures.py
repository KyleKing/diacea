"""Convert curated fixtures to every output format and render each with its native tool.

Usage:

    uv run python scripts/render_fixtures.py --out /tmp/review
    uv run python scripts/render_fixtures.py tests/data/curated/styles.excalidraw --out /tmp/review

Writes rendered images under <out>/renders/ plus summary.txt and summary.json
under <out>/. Exits nonzero when any conversion or render fails; missing
renderer binaries downgrade the affected cells to skips.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess  # noqa: S404
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from diacea.generators import C4PlantUMLGenerator, D2Generator, GraphVizGenerator, MermaidGenerator, PlantUMLGenerator
from diacea.ir.elements import Diagram
from diacea.parsers import ExcalidrawParser, MermaidParser, PlantUMLParser, SVGParser, TLDrawParser

DEFAULT_FIXTURE_DIR = Path(__file__).resolve().parents[1] / 'tests' / 'data' / 'curated'

OUTPUT_FORMATS = {
    'c4': '.c4.puml',
    'd2': '.d2',
    'graphviz': '.dot',
    'mermaid': '.mmd',
    'plantuml': '.puml',
}

RENDERER_BINARIES = {
    'c4': 'plantuml',
    'd2': 'd2',
    'graphviz': 'dot',
    'mermaid': 'mmdc',
    'plantuml': 'plantuml',
}

SOURCE_RENDER_FORMATS = {
    '.dot': 'graphviz',
    '.mmd': 'mermaid',
    '.puml': 'plantuml',
}

SKIPPED_SOURCE_SUFFIXES = {'.excalidraw', '.tldr'}


@dataclass
class Cell:
    """One fixture x format outcome in the review matrix."""

    fixture: str
    format: str
    convert: str
    render: str
    output: str
    note: str = ''


def _parse_fixture(path: Path) -> Diagram:
    content = path.read_text(encoding='utf-8')
    match path.suffix:
        case '.excalidraw':
            return ExcalidrawParser().parse(json.loads(content))
        case '.tldr':
            return TLDrawParser().parse(json.loads(content))
        case '.mmd':
            return MermaidParser().parse(content)
        case '.puml':
            return PlantUMLParser().parse(content)
        case '.svg':
            return SVGParser().parse(content)
    msg = f'Unsupported fixture suffix: {path.suffix}'
    raise ValueError(msg)


def _generate(diagram: Diagram, output_format: str) -> str:
    match output_format:
        case 'c4':
            return C4PlantUMLGenerator().generate(diagram)
        case 'd2':
            return D2Generator().generate(diagram)
        case 'graphviz':
            return GraphVizGenerator().generate(diagram)
        case 'mermaid':
            return MermaidGenerator().generate(diagram)
        case 'plantuml':
            return PlantUMLGenerator().generate(diagram)
    msg = f'Unsupported output format: {output_format}'
    raise ValueError(msg)


def _render_command(renderer: str, source: Path, image: Path) -> list[str]:
    match renderer:
        case 'mmdc':
            return ['mmdc', '-i', str(source), '-o', str(image), '--scale', '2']
        case 'plantuml':
            return ['plantuml', '-tpng', '-o', str(image.parent), str(source)]
        case 'dot':
            return ['dot', '-Tpng', str(source), '-o', str(image)]
        case 'd2':
            return ['d2', str(source), str(image)]
    msg = f'Unsupported renderer: {renderer}'
    raise ValueError(msg)


def _image_path(renderer: str, source: Path) -> Path:
    if renderer == 'd2':
        return source.with_suffix(source.suffix + '.svg')
    if renderer == 'plantuml':
        return source.with_suffix('.png')
    return source.with_suffix(source.suffix + '.png')


def _render(renderer: str, source: Path) -> tuple[str, Path, str]:
    if shutil.which(renderer) is None:
        return ('skipped', source, f'{renderer} not installed')
    image = _image_path(renderer, source)
    command = _render_command(renderer, source, image)
    result = subprocess.run(command, capture_output=True, text=True, timeout=120, check=False)  # noqa: S603
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().splitlines()
        return ('fail', image, detail[0] if detail else f'exit {result.returncode}')
    return ('ok', image, '')


def _process_fixture(fixture: Path, renders_dir: Path) -> list[Cell]:
    cells = []
    try:
        diagram = _parse_fixture(fixture)
    except Exception as err:
        return [Cell(fixture.name, fmt, 'fail', 'skipped', '', f'parse error: {err}') for fmt in OUTPUT_FORMATS]

    for output_format, extension in OUTPUT_FORMATS.items():
        try:
            output = _generate(diagram, output_format)
        except Exception as err:
            cells.append(Cell(fixture.name, output_format, 'fail', 'skipped', '', str(err)))
            continue
        converted = renders_dir / f'{fixture.stem}{extension}'
        converted.write_text(output if output.endswith('\n') else output + '\n', encoding='utf-8')
        render_state, image, note = _render(RENDERER_BINARIES[output_format], converted)
        cells.append(Cell(fixture.name, output_format, 'ok', render_state, str(image), note))
    return cells


def _process_source(fixture: Path, renders_dir: Path) -> Cell:
    if fixture.suffix in SKIPPED_SOURCE_SUFFIXES:
        return Cell(fixture.name, 'source', 'n/a', 'skipped', '', f'no direct renderer for {fixture.suffix}')
    output_format = SOURCE_RENDER_FORMATS.get(fixture.suffix)
    if output_format is None:
        return Cell(fixture.name, 'source', 'n/a', 'skipped', '', f'unrecognized suffix {fixture.suffix}')
    staged = renders_dir / f'{fixture.stem}.source{fixture.suffix}'
    staged.write_text(fixture.read_text(encoding='utf-8'), encoding='utf-8')
    render_state, image, note = _render(RENDERER_BINARIES[output_format], staged)
    return Cell(fixture.name, 'source', 'n/a', render_state, str(image), note)


def _collect_fixtures(paths: list[Path]) -> list[Path]:
    fixtures = []
    for path in paths:
        if path.is_dir():
            fixtures.extend(
                child
                for child in sorted(path.iterdir())
                if child.is_file() and child.suffix in {'.excalidraw', '.mmd', '.puml', '.svg', '.tldr'}
            )
        else:
            fixtures.append(path)
    return fixtures


def _failed(cell: Cell) -> bool:
    return 'fail' in {cell.convert, cell.render}


def _format_summary(cells: list[Cell]) -> str:
    lines = [f'{"fixture":<36}{"format":<10}{"convert":<9}{"render":<9}note']
    lines.extend(f'{cell.fixture:<36}{cell.format:<10}{cell.convert:<9}{cell.render:<9}{cell.note}' for cell in cells)
    failures = sum(1 for cell in cells if _failed(cell))
    skips = sum(1 for cell in cells if cell.render == 'skipped')
    lines.extend(['', f'{len(cells)} cells: {failures} failed, {skips} skipped'])
    return '\n'.join(lines) + '\n'


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        'fixtures',
        nargs='*',
        type=Path,
        default=[DEFAULT_FIXTURE_DIR],
        help=f'Fixture files or directories (default: {DEFAULT_FIXTURE_DIR})',
    )
    parser.add_argument('--out', required=True, type=Path, help='Directory for renders and summaries')
    args = parser.parse_args(argv)

    renders_dir = args.out / 'renders'
    renders_dir.mkdir(parents=True, exist_ok=True)

    cells: list[Cell] = []
    for fixture in _collect_fixtures(args.fixtures):
        if not fixture.exists():
            cells.append(Cell(fixture.name, 'source', 'fail', 'skipped', '', 'fixture not found'))
            continue
        cells.append(_process_source(fixture, renders_dir))
        cells.extend(_process_fixture(fixture, renders_dir))

    summary_text = _format_summary(cells)
    (args.out / 'summary.txt').write_text(summary_text, encoding='utf-8')
    (args.out / 'summary.json').write_text(
        json.dumps([asdict(cell) for cell in cells], indent=2) + '\n', encoding='utf-8'
    )
    print(summary_text, end='')

    return 1 if any(_failed(cell) for cell in cells) else 0


if __name__ == '__main__':
    sys.exit(main())
