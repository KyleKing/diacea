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

    def test_label_binds_to_the_smallest_containing_shape_when_shapes_overlap(self):
        elements = [
            _rect('first', 0.0, 0.0, 400.0, 400.0),
            _rect('second', 0.0, 0.0, 300.0, 300.0),
            _text('t1', 100.0, 100.0, 'Shared'),
        ]

        diagram = ExcalidrawParser().parse({'elements': elements})

        labels = {shape.id: shape.label for shape in diagram.get_shapes()}
        assert labels['second'] == 'Shared'
        assert not labels['first']


class TestExcalidrawGroupDetection:
    """Groups hold direct children only; nested groups are referenced by group id."""

    def test_three_level_nesting_produces_direct_children_groups(self):
        elements = [
            _rect('system', 0.0, 0.0, 1000.0, 1000.0),
            _rect('backend', 100.0, 100.0, 600.0, 600.0),
            _rect('api', 150.0, 150.0, 100.0, 100.0),
            _rect('db', 300.0, 150.0, 100.0, 100.0),
            _rect('web', 750.0, 100.0, 100.0, 100.0),
        ]

        diagram = ExcalidrawParser().parse({'elements': elements})

        groups = {group.id: group for group in diagram.get_groups()}
        assert sorted(groups) == ['group-backend', 'group-system']
        assert sorted(groups['group-backend'].children) == ['api', 'db']
        assert sorted(groups['group-system'].children) == ['group-backend', 'web']

    def test_container_id_binding_beats_geometry_for_labels(self):
        elements = [
            _rect('under', 0.0, 0.0, 100.0, 50.0),
            _rect('over', 5.0, 5.0, 110.0, 55.0),
            {**_text('t-under', 20.0, 15.0, 'under-label'), 'containerId': 'under'},
            {**_text('t-over', 25.0, 25.0, 'over-label'), 'containerId': 'over'},
        ]

        diagram = ExcalidrawParser().parse({'elements': elements})

        labels = {shape.id: shape.label for shape in diagram.get_shapes()}
        assert labels == {'under': 'under-label', 'over': 'over-label'}

    def test_soft_deleted_elements_are_skipped(self):
        elements = [
            _rect('kept', 0.0, 0.0, 100.0, 100.0),
            {**_rect('cleared', 200.0, 0.0, 100.0, 100.0), 'isDeleted': True},
        ]

        diagram = ExcalidrawParser().parse({'elements': elements})

        assert [shape.id for shape in diagram.get_shapes()] == ['kept']

    def test_shape_straddling_a_border_joins_the_container_covering_its_center(self):
        elements = [
            _rect('system', 0.0, 0.0, 1000.0, 1000.0),
            _rect('backend', 400.0, 100.0, 500.0, 800.0),
            _rect('straddler', 300.0, 400.0, 250.0, 100.0),
        ]

        diagram = ExcalidrawParser().parse({'elements': elements})

        groups = {group.id: group for group in diagram.get_groups()}
        assert sorted(groups['group-backend'].children) == ['straddler']
        assert sorted(groups['group-system'].children) == ['group-backend']

    def test_container_label_comes_from_smallest_containing_shape(self):
        elements = [
            _rect('system', 0.0, 0.0, 1000.0, 1000.0),
            _rect('backend', 100.0, 100.0, 600.0, 600.0),
            _rect('api', 150.0, 150.0, 100.0, 100.0),
            _text('t-system', 800.0, 900.0, 'System'),
            _text('t-backend', 500.0, 600.0, 'Backend'),
            _text('t-api', 180.0, 190.0, 'API'),
        ]

        diagram = ExcalidrawParser().parse({'elements': elements})

        labels = {shape.id: shape.label for shape in diagram.get_shapes()}
        assert labels == {'system': 'System', 'backend': 'Backend', 'api': 'API'}

    def test_frame_members_become_a_group(self):
        elements = [
            {'id': 'f1', 'type': 'frame', 'x': 0.0, 'y': 0.0, 'width': 500.0, 'height': 300.0, 'name': 'Backend'},
            {**_rect('api', 20.0, 20.0, 100.0, 60.0), 'frameId': 'f1'},
            {**_rect('db', 200.0, 20.0, 100.0, 60.0), 'frameId': 'f1'},
            _rect('web', 700.0, 20.0, 100.0, 60.0),
        ]

        diagram = ExcalidrawParser().parse({'elements': elements})

        groups = diagram.get_groups()
        assert len(groups) == 1
        group = groups[0]
        assert group.id == 'group-f1'
        assert group.label == 'Backend'
        assert sorted(group.children) == ['api', 'db']

    def test_shared_group_ids_produce_nested_groups(self):
        elements = [
            {**_rect('a', 0.0, 0.0, 100.0, 60.0), 'groupIds': ['inner', 'outer']},
            {**_rect('b', 200.0, 0.0, 100.0, 60.0), 'groupIds': ['inner', 'outer']},
            {**_rect('c', 400.0, 0.0, 100.0, 60.0), 'groupIds': ['outer']},
        ]

        diagram = ExcalidrawParser().parse({'elements': elements})

        groups = {group.id: group for group in diagram.get_groups()}
        assert sorted(groups) == ['group-inner', 'group-outer']
        assert sorted(groups['group-inner'].children) == ['a', 'b']
        assert sorted(groups['group-outer'].children) == ['c', 'group-inner']

    def test_group_id_shared_only_with_a_label_falls_back_to_geometry(self):
        elements = [
            {**_rect('container', 0.0, 0.0, 500.0, 500.0), 'groupIds': ['bundle']},
            {**_text('t1', 10.0, 10.0, 'Container'), 'groupIds': ['bundle']},
            _rect('child', 100.0, 100.0, 100.0, 100.0),
        ]

        diagram = ExcalidrawParser().parse({'elements': elements})

        groups = diagram.get_groups()
        assert len(groups) == 1
        assert groups[0].id == 'group-container'
        assert groups[0].children == ['child']

    def test_real_fixture_groups_hold_direct_children_only(self):
        data = json.loads((REAL_DATA_DIR / 'intertwin_dte_infra_containers.excalidraw').read_text())

        diagram = ExcalidrawParser().parse(data)

        groups = diagram.get_groups()
        assert groups
        child_sets = {group.id: set(group.children) for group in groups}
        seen: dict[str, str] = {}
        for group_id, children in child_sets.items():
            for child_id in children:
                assert child_id not in seen, f'{child_id} claimed by both {seen.get(child_id)} and {group_id}'
                seen[child_id] = group_id
        for group_id, children in child_sets.items():
            for other_id, other_children in child_sets.items():
                if group_id != other_id:
                    assert not (children > other_children)
