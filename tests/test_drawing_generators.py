"""Tests for the Excalidraw and SVG generators."""

import json

import pytest
from defusedxml import ElementTree

from diacea.formats import convert, parse_diagram
from diacea.generators import ExcalidrawConfig, ExcalidrawGenerator, SVGGenerator
from diacea.ir import Connection, Diagram, Dimensions, Point, SemanticType, Shape
from diacea.parsers import MermaidParser

SOURCE = (
    'flowchart LR\n'
    '    user([Customer]) -->|orders| api[API Gateway]\n'
    '    subgraph backend[Back end]\n'
    '        api --> db[(Orders DB)]\n'
    '        api -.-> check{Valid?}\n'
    '    end\n'
)


def _scene(source=SOURCE, **config):
    diagram = MermaidParser().parse(source)
    return json.loads(ExcalidrawGenerator(ExcalidrawConfig(**config)).generate(diagram))


def _by_id(scene):
    return {element['id']: element for element in scene['elements']}


class TestExcalidrawScene:
    def test_scene_envelope(self):
        scene = _scene()

        assert scene['type'] == 'excalidraw'
        assert scene['version'] == 2
        assert scene['files'] == {}

    def test_shapes_map_to_excalidraw_types(self):
        elements = _by_id(_scene())

        assert elements['api']['type'] == 'rectangle'
        assert elements['user']['type'] == 'rectangle'
        assert elements['check']['type'] == 'diamond'
        assert elements['db']['customData'] == {'diacea': {'shape_type': 'cylinder', 'semantic_type': 'database'}}

    def test_labels_are_bound_to_their_shapes(self):
        elements = _by_id(_scene())
        label = elements['api-label']

        assert label['containerId'] == 'api'
        assert label['text'] == 'API Gateway'
        assert {'id': 'api-label', 'type': 'text'} in elements['api']['boundElements']

    def test_arrows_are_bound_at_both_ends(self):
        elements = _by_id(_scene())
        arrow = next(e for e in elements.values() if e['type'] == 'arrow' and e['startBinding']['elementId'] == 'user')

        assert arrow['endBinding']['elementId'] == 'api'
        assert arrow['endArrowhead'] == 'arrow'
        assert {'id': arrow['id'], 'type': 'arrow'} in elements['user']['boundElements']
        assert elements[f'{arrow["id"]}-label']['text'] == 'orders'

    def test_dashed_connection_style(self):
        arrows = [e for e in _scene()['elements'] if e['type'] == 'arrow']

        assert 'dashed' in {arrow['strokeStyle'] for arrow in arrows}

    def test_group_is_drawn_behind_its_children_and_contains_them(self):
        scene = _scene()
        elements = _by_id(scene)
        order = [element['id'] for element in scene['elements']]
        group = elements['group-backend']

        assert order.index('group-backend') < order.index('api')
        for child_id in ('api', 'db', 'check'):
            child = elements[child_id]
            assert group['x'] <= child['x']
            assert child['x'] + child['width'] <= group['x'] + group['width']
            assert group['y'] <= child['y']
            assert child['y'] + child['height'] <= group['y'] + group['height']
        assert elements['group-backend-label']['text'] == 'Back end'

    def test_output_is_deterministic(self):
        assert _scene() == _scene()

    def test_roughness_option(self):
        assert {element['roughness'] for element in _scene(roughness=0)['elements']} == {0}

    def test_long_labels_wrap_but_keep_the_original_text(self):
        scene = _scene('flowchart LR\n    a[Extract the required data such as tables and prices]\n')
        label = _by_id(scene)['a-label']

        assert '\n' in label['text']
        assert label['originalText'] == 'Extract the required data such as tables and prices'

    def test_hand_built_diagram_without_positions_is_laid_out(self):
        diagram = Diagram(id='d')
        for name in ('a', 'b'):
            diagram.add_element(
                Shape(id=name, position=Point(0.0, 0.0), size=Dimensions(120.0, 60.0), label=name.upper())
            )
        diagram.add_element(
            Connection(id='c', position=Point(0.0, 0.0), size=Dimensions(0.0, 0.0), from_id='a', to_id='b')
        )

        elements = _by_id(json.loads(ExcalidrawGenerator().generate(diagram)))

        assert (elements['a']['x'], elements['a']['y']) != (elements['b']['x'], elements['b']['y'])
        assert elements['c']['points'][-1] != [0, 0]


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


class TestSVG:
    def _svg(self, source=SOURCE):
        return ElementTree.fromstring(SVGGenerator().generate(MermaidParser().parse(source)))

    def test_output_is_well_formed_svg_with_a_viewbox(self):
        root = self._svg()

        assert root.tag.endswith('svg')
        assert len(root.attrib['viewBox'].split()) == 4

    def test_every_node_and_group_is_drawn_with_its_label(self):
        root = self._svg()
        ids = {element.attrib['id'] for element in root.iter() if 'id' in element.attrib}
        text = ' '.join(''.join(element.itertext()) for element in root.iter() if element.tag.endswith('text'))

        assert {'user', 'api', 'db', 'check', 'group-backend'} <= ids
        for label in ('Customer', 'API Gateway', 'Orders DB', 'Valid?', 'Back end', 'orders'):
            assert label in text

    def test_semantic_type_is_recorded_for_the_svg_parser(self):
        root = self._svg()
        database = next(element for element in root.iter() if element.attrib.get('id') == 'db')

        assert database.attrib['data-semantic'] == 'database'

    def test_labels_are_escaped(self):
        root = self._svg('flowchart LR\n    a["Fish & <Chips>"]\n')

        assert 'Fish & <Chips>' in ''.join(root.itertext())

    @pytest.mark.parametrize('source', ['flowchart LR\n    a', 'sequenceDiagram\n    A->>B: hi\n'])
    def test_small_diagrams_render(self, source):
        assert self._svg(source).tag.endswith('svg')

    def test_empty_diagram_renders(self):
        assert SVGGenerator().generate(Diagram(id='empty')).startswith('<svg')
