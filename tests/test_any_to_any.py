"""Every format diacea writes, it reads back with the same structure, and every output is pinned.

For each fixture and each output format that is also an input format, the
generated text is re-parsed and compared with the original IR: same node
labels, same group labels, and same connections between the same labels.
The only tolerated differences are ones the generator reported as a
warning: a connection dropped because a container linked to its own content
has no equivalent in most text formats, or a Mermaid C4 relation re-pointed
from a boundary to an element inside it.

Each text and SVG output is also compared byte for byte with a golden in
tests/data/goldens (Excalidraw output is pinned for the curated fixtures only) (the curated fixtures keep theirs in
tests/data/curated/goldens, checked by test_curated_fixtures.py). Goldens
regenerate with DIACEA_REGEN_GOLDENS=1; review the diff before keeping it.
"""

import os

import pytest

from diacea.formats import OUTPUT_FORMATS, parse_diagram, parse_file, render_diagram, verify_conversion

from .configuration import TEST_DATA_DIR

REPO_ROOT = TEST_DATA_DIR.parents[1]
GOLDENS_DIR = TEST_DATA_DIR / 'goldens'
SUFFIXES = {
    'c4': '.c4.puml',
    'd2': '.d2',
    'graphviz': '.dot',
    'mermaid': '.mmd',
    'plantuml': '.puml',
    'svg': '.svg',
}

CURATED = sorted(
    [
        *(TEST_DATA_DIR / 'curated').glob('*.excalidraw'),
        *(TEST_DATA_DIR / 'curated').glob('*.mmd'),
        *(TEST_DATA_DIR / 'curated').glob('*.puml'),
    ]
)
FIXTURES = sorted(
    [
        *(TEST_DATA_DIR / 'mermaid').glob('*.mmd'),
        *(TEST_DATA_DIR / 'plantuml').glob('*.puml'),
        *(TEST_DATA_DIR / 'real').glob('*.mmd'),
        *(TEST_DATA_DIR / 'real').glob('*.excalidraw'),
        *(TEST_DATA_DIR / 'real').glob('*.puml'),
        *(TEST_DATA_DIR / 'real').glob('*.svg'),
        *(TEST_DATA_DIR / 'real').glob('*.tldr'),
        *(TEST_DATA_DIR / 'svg').glob('*.svg'),
        TEST_DATA_DIR / 'excalidraw.json',
        TEST_DATA_DIR / 'tldraw_v2.tldr',
        TEST_DATA_DIR / 'obsidian_plain.excalidraw.md',
        *(REPO_ROOT / 'test_diagrams').glob('*.dot'),
        *(REPO_ROOT / 'test_diagrams').glob('*.d2'),
        *(REPO_ROOT / 'test_diagrams').glob('*.mmd'),
        *(REPO_ROOT / 'test_diagrams').glob('*.svg'),
    ]
)
# fineract_release_process.puml is an activity diagram, which the parser rejects
UNSUPPORTED = {'fineract_release_process.puml'}
# Unlabeled SVG shapes and groups do not survive Mermaid and Excalidraw output
NOT_READ_BACK = {'llm_proxy_component.svg'}

READ_BACK = {name for name, fmt in OUTPUT_FORMATS.items() if fmt.reads_back_as}


def _params():
    params = [
        pytest.param(fixture, output_format, True, id=f'{fixture.name}-{output_format}')
        for fixture in CURATED
        for output_format in sorted(READ_BACK)
    ]
    params.extend(
        pytest.param(fixture, output_format, False, id=f'{fixture.name}-{output_format}')
        for fixture in FIXTURES
        if fixture.name not in UNSUPPORTED
        for output_format in sorted({*SUFFIXES, *READ_BACK})
    )
    return params


def _check_golden(fixture, output_format, output):
    golden = GOLDENS_DIR / f'{fixture.name}{SUFFIXES[output_format]}'
    if not output.endswith('\n'):
        output += '\n'
    if os.environ.get('DIACEA_REGEN_GOLDENS') == '1':
        golden.parent.mkdir(parents=True, exist_ok=True)
        golden.write_text(output, encoding='utf-8')
    assert output == golden.read_text(encoding='utf-8')


@pytest.mark.parametrize(('fixture', 'output_format', 'curated'), _params())
def test_output_matches_golden_and_reads_back_with_same_structure(fixture, output_format, curated):
    result = render_diagram(parse_file(fixture).diagram, output_format)

    if not curated and output_format in SUFFIXES:
        _check_golden(fixture, output_format, result.output)
    if output_format in READ_BACK and fixture.name not in NOT_READ_BACK:
        assert verify_conversion(result) == []


def test_verification_reports_a_lost_node():
    result = render_diagram(parse_diagram('flowchart LR\n    a[Web] --> b[DB]\n').diagram, 'mermaid')
    result.output = result.output.replace('b[DB]', 'b[Cache]')

    assert verify_conversion(result) == [
        "node(s) missing from the output: 'DB'",
        "unexpected node(s) in the output: 'Cache'",
        "1 connection(s) lost without a warning, among: 'Web' -> 'DB'",
        "unexpected connection(s) in the output: 'Web' -> 'Cache'",
    ]


def test_verification_reports_output_that_does_not_parse_back():
    result = render_diagram(parse_diagram('flowchart LR\n    a --> b\n').diagram, 'graphviz')
    result.output = 'digraph {'

    problems = verify_conversion(result)

    assert problems is not None
    assert problems[0].startswith('the graphviz output does not parse back: Failed to parse graphviz input: ')


def test_verification_is_unavailable_for_formats_without_a_parser_mapping():
    result = render_diagram(parse_diagram('flowchart LR\n    a --> b\n').diagram, 'svg')

    assert verify_conversion(result) is None
