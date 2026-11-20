"""Every format diacea writes, it reads back with the same structure.

For each fixture and each output format that is also an input format, the
generated text is re-parsed and compared with the original IR: same node
labels, same group labels, and same connections between the same labels.
The only tolerated differences are ones the generator reported as a
warning: a connection dropped because a container linked to its own content
has no equivalent in most text formats, or a Mermaid C4 relation re-pointed
from a boundary to an element inside it.
"""

import pytest

from diacea.formats import OUTPUT_FORMATS, parse_diagram, parse_file, render_diagram, verify_conversion

from .configuration import TEST_DATA_DIR

REPO_ROOT = TEST_DATA_DIR.parents[1]

FIXTURES = sorted(
    [
        *(TEST_DATA_DIR / 'curated').glob('*.excalidraw'),
        *(TEST_DATA_DIR / 'curated').glob('*.mmd'),
        *(TEST_DATA_DIR / 'curated').glob('*.puml'),
        *(TEST_DATA_DIR / 'mermaid').glob('*.mmd'),
        *(TEST_DATA_DIR / 'plantuml').glob('*.puml'),
        *(TEST_DATA_DIR / 'real').glob('*.mmd'),
        *(TEST_DATA_DIR / 'real').glob('*.excalidraw'),
        *(REPO_ROOT / 'test_diagrams').glob('*.dot'),
        *(REPO_ROOT / 'test_diagrams').glob('*.d2'),
        *(REPO_ROOT / 'test_diagrams').glob('*.mmd'),
        *(REPO_ROOT / 'test_diagrams').glob('*.svg'),
    ]
)

READ_BACK = [name for name, fmt in OUTPUT_FORMATS.items() if fmt.reads_back_as]


def _params():
    return [
        pytest.param(fixture, output_format, id=f'{fixture.name}-{output_format}')
        for fixture in FIXTURES
        for output_format in READ_BACK
    ]


@pytest.mark.parametrize(('fixture', 'output_format'), _params())
def test_output_reads_back_with_same_structure(fixture, output_format):
    parsed = parse_file(fixture)
    result = render_diagram(parsed.diagram, output_format)

    assert verify_conversion(result) == []


def test_verification_reports_a_lost_node():
    result = render_diagram(parse_diagram('flowchart LR\n    a[Web] --> b[DB]\n').diagram, 'mermaid')
    result.output = result.output.replace('b[DB]', 'b[Cache]')

    problems = verify_conversion(result)

    assert problems is not None
    assert problems[:2] == ["node(s) missing from the output: 'DB'", "unexpected node(s) in the output: 'Cache'"]


def test_verification_is_unavailable_for_formats_without_a_parser_mapping():
    result = render_diagram(parse_diagram('flowchart LR\n    a --> b\n').diagram, 'svg')

    assert verify_conversion(result) is None
