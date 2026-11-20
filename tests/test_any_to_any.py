"""Every format diacea writes, it reads back with the same structure.

For each fixture and each output format that is also an input format, the
generated text is re-parsed and compared with the original IR: same node
labels, same group labels, and same connections between the same labels.
The only tolerated differences are ones the generator reported as a
warning: a connection dropped because a container linked to its own content
has no equivalent in most text formats, or a Mermaid C4 relation re-pointed
from a boundary to an element inside it.
"""

from collections import Counter

import pytest

from diacea.formats import parse_diagram, parse_file, render_diagram
from diacea.ir import Diagram

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
    ]
)

# Output format -> the input format that reads it back
READ_BACK = {
    'c4': 'plantuml',
    'd2': 'd2',
    'excalidraw': 'excalidraw',
    'graphviz': 'graphviz',
    'mermaid': 'mermaid',
    'plantuml': 'plantuml',
}


def _normalize(label: str) -> str:
    return ' '.join(label.split())


def _structure(diagram: Diagram) -> tuple[Counter, Counter, Counter]:
    """Node labels, group labels, and (from label, to label) pairs of a diagram."""
    groups = diagram.get_groups()
    source_ids = {group.source_shape_id for group in groups}
    labels = {shape.id: _normalize(shape.label) for shape in diagram.get_shapes() if shape.id not in source_ids}
    for group in groups:
        labels[group.id] = labels[group.source_shape_id] = _normalize(group.label)
    nodes = Counter(_normalize(shape.label) for shape in diagram.get_shapes() if shape.id not in source_ids)
    edges = Counter(
        (labels.get(conn.from_id, conn.from_id), labels.get(conn.to_id, conn.to_id))
        for conn in diagram.get_connections()
    )
    return nodes, Counter(_normalize(group.label) for group in groups), edges


def _params():
    return [
        pytest.param(fixture, output_format, id=f'{fixture.name}-{output_format}')
        for fixture in FIXTURES
        for output_format in READ_BACK
    ]


@pytest.mark.parametrize(('fixture', 'output_format'), _params())
def test_output_reads_back_with_same_structure(fixture, output_format):
    original = parse_file(fixture).diagram
    nodes, groups, edges = _structure(original)

    result = render_diagram(original, output_format)
    reparsed = parse_diagram(result.output, READ_BACK[output_format]).diagram
    nodes_back, groups_back, edges_back = _structure(reparsed)

    dropped = sum(1 for warning in result.warnings if 'ropping' in warning)
    repointed = sum(1 for warning in result.warnings if 'Re-pointing' in warning)
    assert nodes_back == nodes
    assert groups_back == groups
    assert sum((edges_back - edges).values()) <= repointed, 'conversion invented a connection'
    assert sum((edges - edges_back).values()) <= dropped + repointed, 'conversion lost a connection silently'
