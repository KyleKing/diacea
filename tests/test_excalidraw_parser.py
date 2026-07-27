"""Tests for Excalidraw parser."""

import json

import pytest

from diacea.ir import Connection, Shape, Text
from diacea.parsers import ExcalidrawParser

from .configuration import TEST_DATA_DIR

REAL_DATA_DIR = TEST_DATA_DIR / 'real'

_INTERTWIN_FIXTURES = [
    'intertwin_c4_qa_pipeline.excalidraw',
    'intertwin_dte_infra_containers.excalidraw',
    'intertwin_system_context.excalidraw',
]


def _assert_float_geometry(element) -> None:
    assert isinstance(element.position.x, float)
    assert isinstance(element.position.y, float)
    assert isinstance(element.size.width, float)
    assert isinstance(element.size.height, float)


class TestExcalidrawFloatCoercion:
    """Regression tests: raw JSON ints must be coerced to float for IR constructors."""

    @pytest.mark.parametrize('fixture_name', _INTERTWIN_FIXTURES)
    def test_real_fixture_parses_with_float_geometry(self, fixture_name):
        data = json.loads((REAL_DATA_DIR / fixture_name).read_text())

        parser = ExcalidrawParser()
        diagram = parser.parse(data)

        assert len(diagram.elements) > 0
        for element in diagram.elements:
            _assert_float_geometry(element)

    def test_int_coordinates_coerced(self):
        data = {
            'elements': [
                {'id': 'r1', 'type': 'rectangle', 'x': 0, 'y': 0, 'width': 100, 'height': 60, 'opacity': 100},
                {'id': 'r2', 'type': 'rectangle', 'x': 300, 'y': 0, 'width': 100, 'height': 60},
                {
                    'id': 't1',
                    'type': 'text',
                    'x': 10,
                    'y': 20,
                    'width': 80,
                    'height': 20,
                    'text': 'API',
                    'fontSize': 16,
                },
                {'id': 'a1', 'type': 'arrow', 'x': 100, 'y': 30, 'points': [[0, 0], [100, 10], [200, 0]]},
            ],
        }

        parser = ExcalidrawParser()
        diagram = parser.parse(data)

        shapes = [e for e in diagram.elements if isinstance(e, Shape)]
        texts = [e for e in diagram.elements if isinstance(e, Text)]
        connections = [e for e in diagram.elements if isinstance(e, Connection)]

        assert len(shapes) == 2
        assert len(texts) == 1
        assert len(connections) == 1

        for element in [*shapes, *texts, *connections]:
            _assert_float_geometry(element)

        r1 = next(s for s in shapes if s.id == 'r1')
        assert isinstance(r1.style.opacity, float)
        assert r1.style.opacity == 1.0

        assert isinstance(texts[0].style.font_size, float)
        assert texts[0].style.font_size == 16.0

        arrow = connections[0]
        assert arrow.start_point is not None
        assert arrow.end_point is not None
        assert isinstance(arrow.start_point.x, float)
        assert isinstance(arrow.start_point.y, float)
        assert isinstance(arrow.end_point.x, float)
        assert isinstance(arrow.end_point.y, float)
        assert len(arrow.waypoints) == 1
        assert isinstance(arrow.waypoints[0].x, float)
        assert isinstance(arrow.waypoints[0].y, float)


def _rect(elem_id, x, y, width, height):
    return {'id': elem_id, 'type': 'rectangle', 'x': x, 'y': y, 'width': width, 'height': height}


def _text(elem_id, x, y, content):
    return {'id': elem_id, 'type': 'text', 'x': x, 'y': y, 'width': 40.0, 'height': 20.0, 'text': content}


class TestExcalidrawSpatialIndex:
    """The bucket grid used by label association and group detection must stay exact."""

    def test_container_far_larger_than_the_grid_cell_still_groups_children(self):
        elements = [_rect('outer', 0.0, 0.0, 20000.0, 20000.0)]
        elements += [_rect(f'inner{idx}', 100.0 + idx * 200.0, 100.0, 50.0, 50.0) for idx in range(40)]

        diagram = ExcalidrawParser().parse({'elements': elements})

        groups = diagram.get_groups()
        assert len(groups) == 1
        assert sorted(groups[0].children) == sorted(f'inner{idx}' for idx in range(40))

    def test_label_binds_to_the_first_matching_shape_when_shapes_overlap(self):
        elements = [
            _rect('first', 0.0, 0.0, 400.0, 400.0),
            _rect('second', 0.0, 0.0, 300.0, 300.0),
            _text('t1', 100.0, 100.0, 'Shared'),
        ]

        diagram = ExcalidrawParser().parse({'elements': elements})

        labels = {shape.id: shape.label for shape in diagram.get_shapes()}
        assert labels['first'] == 'Shared'
        assert not labels['second']
