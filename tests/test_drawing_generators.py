"""Tests for the Excalidraw and SVG generators."""

import json
import os

import pytest

from diacea.formats import convert, parse_diagram, render_diagram
from diacea.ir import Connection, Diagram, Dimensions, Point, SemanticType, Shape

from .configuration import TEST_DATA_DIR

GOLDENS_DIR = TEST_DATA_DIR / 'goldens'

SOURCE = (
    'flowchart LR\n'
    '    user([Customer]) -->|orders| api[API Gateway]\n'
    '    subgraph backend[Back end]\n'
    '        api --> db[(Orders DB)]\n'
    '        api -.-> check{Valid?}\n'
    '    end\n'
)


def _hand_built():
    diagram = Diagram(id='d')
    for name in ('a', 'b'):
        diagram.add_element(Shape(id=name, position=Point(0.0, 0.0), size=Dimensions(120.0, 60.0), label=name.upper()))
    diagram.add_element(Connection(id='c', position=Point(0.0, 0.0), size=Dimensions(0.0, 0.0), from_id='a', to_id='b'))
    return diagram


_DRAWINGS = {
    'flow': SOURCE,
    'long-label': 'flowchart LR\n    a[Extract the required data such as tables and prices]\n',
    'escaped': 'flowchart LR\n    a["Fish & <Chips>"]\n',
    'single': 'flowchart LR\n    a',
    'sequence': 'sequenceDiagram\n    A->>B: hi\n',
}


@pytest.mark.parametrize(
    ('case', 'output_format', 'options'),
    [
        ('flow', 'excalidraw', {}),
        ('flow', 'excalidraw', {'excalidraw_roughness': '0'}),
        ('long-label', 'excalidraw', {}),
        ('hand-built', 'excalidraw', {}),
        ('flow', 'svg', {}),
        ('escaped', 'svg', {}),
        ('single', 'svg', {}),
        ('sequence', 'svg', {}),
        ('empty', 'svg', {}),
    ],
)
def test_drawing_matches_golden(case, output_format, options):
    if case == 'hand-built':
        diagram = _hand_built()
    elif case == 'empty':
        diagram = Diagram(id='empty')
    else:
        diagram = parse_diagram(_DRAWINGS[case]).diagram
    output = render_diagram(diagram, output_format, **options).output + '\n'
    suffix = ''.join(f'.{key}-{value}' for key, value in options.items())
    golden = GOLDENS_DIR / f'drawing.{case}{suffix}.{output_format}'

    if os.environ.get('DIACEA_REGEN_GOLDENS') == '1':
        golden.write_text(output, encoding='utf-8')
    assert output == golden.read_text(encoding='utf-8')


def test_excalidraw_scene_binds_labels_and_arrows_and_draws_groups_first():
    scene = json.loads(convert(SOURCE, 'excalidraw').output)
    elements = {element['id']: element for element in scene['elements']}
    order = [element['id'] for element in scene['elements']]
    arrow = next(e for e in elements.values() if e['type'] == 'arrow' and e['startBinding']['elementId'] == 'user')
    group = elements['group-backend']

    assert (scene['type'], scene['version'], scene['files']) == ('excalidraw', 2, {})
    assert elements['api-label']['containerId'] == 'api'
    assert {'id': 'api-label', 'type': 'text'} in elements['api']['boundElements']
    assert arrow['endBinding']['elementId'] == 'api'
    assert {'id': arrow['id'], 'type': 'arrow'} in elements['user']['boundElements']
    assert order.index('group-backend') < order.index('api')
    for child_id in ('api', 'db', 'check'):
        child = elements[child_id]
        assert group['x'] <= child['x'] <= child['x'] + child['width'] <= group['x'] + group['width']
        assert group['y'] <= child['y'] <= child['y'] + child['height'] <= group['y'] + group['height']


class TestExcalidrawRoundTrip:
    def test_structure_shapes_and_semantics_survive(self):
        scene_text = convert(SOURCE, to='excalidraw').output
        back = parse_diagram(scene_text).diagram
        shapes = {shape.id: shape for shape in back.get_shapes()}

        assert shapes['db'].shape_type == 'cylinder'
        assert shapes['db'].semantic_type == SemanticType.DATABASE
        assert shapes['api'].label == 'API Gateway'
        assert {group.label for group in back.get_groups()} == {'Back end'}
        assert ('user', 'api', 'orders') in {(c.from_id, c.to_id, c.label) for c in back.get_connections()}

    def test_text_to_drawing_and_back_is_lossless_for_mermaid(self):
        source = 'flowchart LR\n    a[Web]\n    b[(DB)]\n    a -->|calls| b'
        scene_text = convert(source, to='excalidraw').output

        assert convert(scene_text, to='mermaid', mermaid_type='flowchart').output == source
