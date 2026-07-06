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
                {'id': 't1', 'type': 'text', 'x': 10, 'y': 20, 'width': 80, 'height': 20, 'text': 'API', 'fontSize': 16},
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
        assert isinstance(arrow.start_point.x, float)
        assert isinstance(arrow.start_point.y, float)
        assert isinstance(arrow.end_point.x, float)
        assert isinstance(arrow.end_point.y, float)
        assert len(arrow.waypoints) == 1
        assert isinstance(arrow.waypoints[0].x, float)
        assert isinstance(arrow.waypoints[0].y, float)
