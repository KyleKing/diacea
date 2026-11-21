"""Tests for Excalidraw parser."""

import json

import pytest

from diacea.formats import parse_diagram
from diacea.ir import Connection, Dimensions, Point, SemanticType, Shape, Text
from diacea.parsers import ExcalidrawParser

from .configuration import TEST_DATA_DIR
from .ir_summary import summarize

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


def _sketch_box(element_id, x, y, width=160, height=80, **extra):
    return {'id': element_id, 'type': 'rectangle', 'x': x, 'y': y, 'width': width, 'height': height, **extra}


def _sketch_text(element_id, text, x, y, font_size=20, **extra):
    width = len(text) * font_size * 0.5
    return {
        'id': element_id,
        'type': 'text',
        'x': x,
        'y': y,
        'width': width,
        'height': font_size * 1.25,
        'text': text,
        'fontSize': font_size,
        **extra,
    }


def _sketch_arrow(element_id, start, end, **extra):
    return {
        'id': element_id,
        'type': 'arrow',
        'x': start[0],
        'y': start[1],
        'points': [[0, 0], [end[0] - start[0], end[1] - start[1]]],
        'endArrowhead': 'arrow',
        **extra,
    }


def _parse_elements(*elements):
    parser = ExcalidrawParser()
    return parser.parse({'elements': list(elements)})


class TestLabelsFromRealSketches:
    def test_box_with_title_and_description_uses_the_title(self):
        diagram = _parse_elements(
            _sketch_box('box', 0, 0, 300, 160),
            _sketch_text('body', 'Stores every order placed', 10, 80, font_size=14),
            _sketch_text('title', 'Orders API', 10, 10, font_size=24),
        )
        box = diagram.get_shapes()[0]

        assert box.label == 'Orders API'
        assert box.metadata['description'] == 'Stores every order placed'

    def test_label_written_above_a_box_labels_that_box(self):
        diagram = _parse_elements(
            _sketch_box('zone', 0, 0, 400, 300),
            _sketch_text('zone_label', 'Zone', 16, 8),
            _sketch_box('store', 60, 120, 120, 60),
            _sketch_text('store_label', 'Store', 62, 92),
        )
        labels = {shape.id: shape.label for shape in diagram.get_shapes()}

        assert labels == {'zone': 'Zone', 'store': 'Store'}

    def test_text_grouped_with_one_shape_labels_it_from_outside(self):
        diagram = _parse_elements(
            _sketch_box('box', 0, 0, groupIds=['g1']),
            _sketch_text('caption', 'Billing', 0, 140, groupIds=['g1']),
        )

        assert diagram.get_shapes()[0].label == 'Billing'

    def test_bound_text_ignores_auto_wrap_line_breaks(self):
        diagram = _parse_elements(
            _sketch_box('box', 0, 0),
            _sketch_text('label', 'spellchec\nk', 10, 10, containerId='box', originalText='spellcheck'),
        )

        assert diagram.get_shapes()[0].label == 'spellcheck'

    def test_default_pen_is_not_recorded_as_styling(self):
        diagram = _parse_elements(_sketch_box('box', 0, 0, strokeColor='#1e1e1e', strokeWidth=2))
        style = diagram.get_shapes()[0].style

        assert style.stroke_color is None
        assert style.stroke_width is None

    def test_chosen_pen_is_recorded(self):
        diagram = _parse_elements(_sketch_box('box', 0, 0, strokeColor='#e03131', strokeWidth=4))
        style = diagram.get_shapes()[0].style

        assert style.stroke_color == '#e03131'
        assert style.stroke_width == 4.0


class TestArrowsFromRealSketches:
    def test_arrow_label_is_read_and_not_given_to_the_container(self):
        diagram = _parse_elements(
            _sketch_box('outer', -50, -50, 700, 300),
            _sketch_text('outer_label', 'Platform', -40, -40),
            _sketch_box('a', 0, 60),
            _sketch_box('b', 400, 60),
            _sketch_arrow(
                'link', (160, 100), (400, 100), startBinding={'elementId': 'a'}, endBinding={'elementId': 'b'}
            ),
            _sketch_text('link_label', 'publishes', 240, 90, containerId='link'),
        )
        labels = {shape.id: shape.label for shape in diagram.get_shapes()}

        assert diagram.get_connections()[0].label == 'publishes'
        assert labels['outer'] == 'Platform'

    def test_arrow_bound_to_a_label_follows_it_to_the_shape(self):
        diagram = _parse_elements(
            _sketch_box('a', 0, 0, groupIds=['ga']),
            _sketch_text('a_title', 'Sender', 20, 20, groupIds=['ga']),
            _sketch_box('b', 400, 0),
            _sketch_arrow(
                'link', (160, 40), (400, 40), startBinding={'elementId': 'a_title'}, endBinding={'elementId': 'b'}
            ),
        )
        connection = diagram.get_connections()[0]

        assert (connection.from_id, connection.to_id) == ('a', 'b')

    def test_loose_text_that_arrows_point_at_becomes_a_node(self):
        diagram = _parse_elements(
            _sketch_box('a', 0, 0),
            _sketch_text('note', 'External API', 400, 20),
            _sketch_arrow(
                'link', (160, 40), (400, 30), startBinding={'elementId': 'a'}, endBinding={'elementId': 'note'}
            ),
        )
        shapes = {shape.id: shape.label for shape in diagram.get_shapes()}

        assert shapes['note'] == 'External API'
        assert diagram.get_connections()[0].to_id == 'note'
        assert [element.id for element in diagram.elements].count('note') == 1

    def test_binding_to_a_missing_element_falls_back_to_the_nearest_shape(self):
        diagram = _parse_elements(
            _sketch_box('a', 0, 0),
            _sketch_box('b', 400, 0),
            _sketch_arrow(
                'link', (160, 40), (400, 40), startBinding={'elementId': 'gone'}, endBinding={'elementId': 'b'}
            ),
        )

        assert diagram.get_connections()[0].from_id == 'a'

    def test_arrowhead_at_the_start_reverses_the_connection(self):
        diagram = _parse_elements(
            _sketch_box('a', 0, 0),
            _sketch_box('b', 400, 0),
            _sketch_arrow(
                'link',
                (160, 40),
                (400, 40),
                startArrowhead='arrow',
                endArrowhead=None,
                startBinding={'elementId': 'a'},
                endBinding={'elementId': 'b'},
            ),
        )
        connection = diagram.get_connections()[0]

        assert (connection.from_id, connection.to_id, connection.connection_type) == ('b', 'a', 'directed')

    def test_line_without_arrowheads_is_undirected(self):
        diagram = _parse_elements(
            _sketch_box('a', 0, 0),
            _sketch_box('b', 400, 0),
            _sketch_arrow('link', (160, 40), (400, 40), endArrowhead=None),
        )

        assert diagram.get_connections()[0].connection_type == 'undirected'

    def test_stick_figure_head_and_body_are_one_person(self):
        head = {'id': 'head', 'type': 'ellipse', 'x': 40, 'y': -70, 'width': 60, 'height': 60, 'groupIds': ['p']}
        diagram = _parse_elements(
            head,
            _sketch_box('body', 0, 0, 140, 100, groupIds=['p']),
            _sketch_text('name', 'Shopper', 30, 40, groupIds=['p']),
            _sketch_box('shop', 400, 0),
            _sketch_arrow(
                'link', (100, -40), (400, 40), startBinding={'elementId': 'head'}, endBinding={'elementId': 'shop'}
            ),
        )
        shapes = {shape.id: shape for shape in diagram.get_shapes()}

        assert set(shapes) == {'body', 'shop'}
        assert shapes['body'].label == 'Shopper'
        assert shapes['body'].semantic_type == SemanticType.PERSON
        assert diagram.get_connections()[0].from_id == 'body'
        assert diagram.get_groups() == []


def _ellipse(element_id, x, y, width, height, group):
    return {'id': element_id, 'type': 'ellipse', 'x': x, 'y': y, 'width': width, 'height': height, 'groupIds': [group]}


@pytest.mark.parametrize(
    ('elements', 'expected'),
    [
        pytest.param(
            [_sketch_box('b', 0, 100), _sketch_text('t', 'Cache', 10, 70)],
            {'nodes': [('b', 'Cache', 'rectangle', 'database')]},
            id='loose-text-above-a-box-labels-it',
        ),
        pytest.param(
            [_sketch_box('c', 0, 0, 600, 400), _sketch_box('b', 100, 200), _sketch_text('t', 'Near', 110, 170)],
            {
                'nodes': [('c', 'Near', 'rectangle', 'system'), ('b', '', 'rectangle', 'component')],
                'groups': [('group-c', 'Near', ['b'])],
            },
            id='container-keeps-its-sole-text',
        ),
        pytest.param(
            [
                _sketch_box('c', 0, 0, 600, 400),
                _sketch_text('ct', 'Region', 10, 10),
                _sketch_box('b', 100, 200),
                _sketch_text('t', 'Near', 110, 170),
            ],
            {
                'nodes': [('c', 'Region', 'rectangle', 'cloud'), ('b', 'Near', 'rectangle', 'component')],
                'groups': [('group-c', 'Region', ['b'])],
            },
            id='container-with-two-texts-gives-one-away',
        ),
        pytest.param(
            [_ellipse('h', 50, 0, 40, 40, 'g1'), _ellipse('bd', 30, 50, 80, 100, 'g1')],
            {
                'nodes': [('h', '', 'ellipse', 'person'), ('bd', '', 'ellipse', 'person')],
                'groups': [('group-g1', '', ['h', 'bd'])],
            },
            id='two-grouped-ellipses-are-not-a-stick-figure',
        ),
        pytest.param(
            [
                _sketch_box('a', 0, 0, 200, 40),
                _sketch_text('at', 'A', 10, 10),
                _sketch_box('b', 210, 0, 20, 40),
                _sketch_text('bt', 'B', 212, 10, font_size=8),
                _sketch_box('z', 0, 300),
                _sketch_text('zt', 'Z', 10, 310),
                _sketch_arrow('r', (80, 330), (200, 20)),
            ],
            {
                'nodes': [
                    ('a', 'A', 'rectangle', 'database'),
                    ('b', 'B', 'rectangle', 'component'),
                    ('z', 'Z', 'rectangle', 'component'),
                ],
                'edges': [('z', 'a', '')],
            },
            id='unbound-arrow-ending-on-a-right-border-joins-that-shape',
        ),
        pytest.param(
            [
                _sketch_box('a', 0, 0, 200, 40),
                _sketch_text('at', 'A', 10, 10),
                _sketch_box('b', 90, 42, 20, 20),
                _sketch_text('bt', 'B', 92, 44, font_size=8),
                _sketch_box('z', 400, 300),
                _sketch_text('zt', 'Z', 410, 310),
                _sketch_arrow('r', (480, 330), (100, 40)),
            ],
            {
                'nodes': [
                    ('a', 'A', 'rectangle', 'database'),
                    ('b', 'B', 'rectangle', 'component'),
                    ('z', 'Z', 'rectangle', 'component'),
                ],
                'edges': [('z', 'a', '')],
            },
            id='unbound-arrow-ending-on-a-bottom-border-joins-that-shape',
        ),
        pytest.param(
            [
                _sketch_box('a', 300, 0, 200, 40),
                _sketch_text('at', 'A', 310, 10),
                _sketch_box('c', 270, 0, 20, 40),
                _sketch_text('ct', 'C', 272, 10, font_size=8),
                _sketch_box('z', 300, 300),
                _sketch_text('zt', 'Z', 310, 310),
                _sketch_arrow('r', (380, 330), (300, 20)),
            ],
            {
                'nodes': [
                    ('a', 'A', 'rectangle', 'database'),
                    ('c', 'C', 'rectangle', 'component'),
                    ('z', 'Z', 'rectangle', 'component'),
                ],
                'edges': [('z', 'a', '')],
            },
            id='unbound-arrow-ending-on-a-left-border-joins-that-shape',
        ),
        pytest.param(
            [
                _sketch_box('a', 0, 100, 200, 40),
                _sketch_text('at', 'A', 10, 110),
                _sketch_box('c', 90, 75, 20, 20),
                _sketch_text('ct', 'C', 92, 78, font_size=8),
                _sketch_box('z', 400, 300),
                _sketch_text('zt', 'Z', 410, 310),
                _sketch_arrow('r', (480, 330), (100, 100)),
            ],
            {
                'nodes': [
                    ('a', 'A', 'rectangle', 'database'),
                    ('c', 'C', 'rectangle', 'component'),
                    ('z', 'Z', 'rectangle', 'component'),
                ],
                'edges': [('z', 'a', '')],
            },
            id='unbound-arrow-ending-on-a-top-border-joins-that-shape',
        ),
    ],
)
def test_sketch_parses_to(elements, expected):
    assert summarize(parse_diagram(json.dumps({'elements': elements}), 'excalidraw').diagram) == expected


def test_missing_geometry_and_opacity_default_to_zero_and_opaque():
    diagram = parse_diagram(
        json.dumps({'elements': [{'id': 'r', 'type': 'rectangle'}, {'id': 'tx', 'type': 'text', 'text': 'Hi'}]}),
        'excalidraw',
    ).diagram

    assert [(e.id, e.position, e.size, e.style.opacity) for e in diagram.elements] == [
        ('r', Point(0.0, 0.0), Dimensions(0.0, 0.0), 1.0),
        ('tx', Point(0.0, 0.0), Dimensions(0.0, 0.0), None),
    ]
