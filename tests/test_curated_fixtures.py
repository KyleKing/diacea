"""Conversion, render, and golden checks over the curated fixtures in tests/data/curated.

Each fixture pins one behavior (see tests/data/curated/README.md). Render checks
shell out to mmdc/plantuml/dot/d2 and only run when DIACEA_RENDER=1. Goldens
live in tests/data/curated/goldens and regenerate with DIACEA_REGEN_GOLDENS=1.
"""

import json
import os
import shutil
import subprocess

import pytest

from diacea.generators import C4PlantUMLGenerator, D2Generator, GraphVizGenerator, MermaidGenerator, PlantUMLGenerator
from diacea.parsers import ExcalidrawParser, MermaidParser, PlantUMLParser, TLDrawParser

from .configuration import TEST_DATA_DIR

CURATED_DIR = TEST_DATA_DIR / 'curated'
GOLDENS_DIR = CURATED_DIR / 'goldens'

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

_KNOWN_RENDER_FAILURES: dict[tuple[str, str], str] = {}


def _fixtures():
    return sorted(path for path in CURATED_DIR.iterdir() if path.is_file() and path.name != 'README.md')


def _convert(fixture_path, output_format):
    content = fixture_path.read_text(encoding='utf-8')
    match fixture_path.suffix:
        case '.excalidraw':
            diagram = ExcalidrawParser().parse(json.loads(content))
        case '.tldr':
            diagram = TLDrawParser().parse(json.loads(content))
        case '.mmd':
            diagram = MermaidParser().parse(content)
        case '.puml':
            diagram = PlantUMLParser().parse(content)
        case _:
            msg = f'Unhandled fixture suffix: {fixture_path.suffix}'
            raise ValueError(msg)
    generators = {
        'c4': C4PlantUMLGenerator,
        'd2': D2Generator,
        'graphviz': GraphVizGenerator,
        'mermaid': MermaidGenerator,
        'plantuml': PlantUMLGenerator,
    }
    return generators[output_format]().generate(diagram)


def _matrix_params(*, with_render_marks: bool = False):
    params = []
    for fixture_path in _fixtures():
        for output_format in OUTPUT_FORMATS:
            marks = []
            if with_render_marks and (reason := _KNOWN_RENDER_FAILURES.get((fixture_path.name, output_format))):
                marks = [pytest.mark.xfail(reason=reason, strict=False)]
            params.append(
                pytest.param(fixture_path, output_format, id=f'{fixture_path.name}-{output_format}', marks=marks)
            )
    return params


@pytest.mark.parametrize(('fixture_path', 'output_format'), _matrix_params())
def test_curated_conversion(fixture_path, output_format):
    output = _convert(fixture_path, output_format)

    assert output.strip()


def _render_command(renderer, source, out_dir):
    match renderer:
        case 'mmdc':
            return ['mmdc', '-i', str(source), '-o', str(out_dir / 'out.png'), '--scale', '2']
        case 'plantuml':
            return ['plantuml', '-tpng', '-o', str(out_dir), str(source)]
        case 'dot':
            return ['dot', '-Tpng', str(source), '-o', str(out_dir / 'out.png')]
        case 'd2':
            return ['d2', str(source), str(out_dir / 'out.svg')]
    msg = f'Unhandled renderer: {renderer}'
    raise ValueError(msg)


@pytest.mark.skipif(os.environ.get('DIACEA_RENDER') != '1', reason='set DIACEA_RENDER=1 to run render checks')
@pytest.mark.parametrize(('fixture_path', 'output_format'), _matrix_params(with_render_marks=True))
def test_curated_render(fixture_path, output_format, tmp_path):
    renderer = RENDERER_BINARIES[output_format]
    if shutil.which(renderer) is None:
        pytest.skip(f'{renderer} not installed')

    source = tmp_path / f'diagram{OUTPUT_FORMATS[output_format]}'
    source.write_text(_convert(fixture_path, output_format), encoding='utf-8')
    result = subprocess.run(
        _render_command(renderer, source, tmp_path), capture_output=True, text=True, timeout=120, check=False
    )

    assert result.returncode == 0, (result.stderr or result.stdout).strip()


@pytest.mark.parametrize(('fixture_path', 'output_format'), _matrix_params())
def test_curated_golden(fixture_path, output_format):
    golden_path = GOLDENS_DIR / f'{fixture_path.stem}{OUTPUT_FORMATS[output_format]}'
    output = _convert(fixture_path, output_format)
    if not output.endswith('\n'):
        output += '\n'

    if os.environ.get('DIACEA_REGEN_GOLDENS') == '1':
        golden_path.parent.mkdir(parents=True, exist_ok=True)
        golden_path.write_text(output, encoding='utf-8')
        return
    if not golden_path.exists():
        pytest.skip('golden not generated yet')

    assert output == golden_path.read_text(encoding='utf-8')
