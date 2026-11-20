"""Tests for the synthesized compound layout."""

from itertools import combinations

import pytest

from diacea.formats import parse_diagram, parse_file
from diacea.ir import Connection, Diagram, Dimensions, Group, Point, Shape
from diacea.layout import estimate_label_size, layout_diagram, wrap_label

from .configuration import TEST_DATA_DIR

TEXT_FIXTURES = sorted(
    [
        *(TEST_DATA_DIR / 'curated').glob('*.mmd'),
        *(TEST_DATA_DIR / 'curated').glob('*.puml'),
        *(TEST_DATA_DIR / 'real').glob('*.mmd'),
        *(TEST_DATA_DIR / 'real').glob('bigbank*.puml'),
        *(TEST_DATA_DIR.parents[1] / 'test_diagrams').glob('*.dot'),
        *(TEST_DATA_DIR.parents[1] / 'test_diagrams').glob('*.d2'),
    ]
)


def _box(element):
    return (
        element.position.x,
        element.position.y,
        element.position.x + element.size.width,
        element.position.y + element.size.height,
    )


def _overlap(first, second):
    return first[0] < second[2] and second[0] < first[2] and first[1] < second[3] and second[1] < first[3]


def _contains(outer, inner):
    return outer[0] <= inner[0] and outer[1] <= inner[1] and inner[2] <= outer[2] and inner[3] <= outer[3]


def _descendants(diagram, group):
    groups = {candidate.id: candidate for candidate in diagram.get_groups()}
    found, pending = set(), list(group.children)
    while pending:
        child_id = pending.pop()
        found.add(child_id)
        if child_id in groups:
            pending.extend(groups[child_id].children)
    return found


@pytest.mark.parametrize('fixture', TEXT_FIXTURES, ids=lambda path: path.name)
def test_real_diagrams_lay_out_without_overlap(fixture):
    diagram = parse_file(fixture).diagram
    shapes = diagram.get_shapes()
    groups = diagram.get_groups()

    for first, second in combinations(shapes, 2):
        assert not _overlap(_box(first), _box(second)), f'{first.id} overlaps {second.id}'

    by_id = {element.id: element for element in [*shapes, *groups]}
    for group in groups:
        inside = _descendants(diagram, group)
        for member_id in inside:
            assert _contains(_box(group), _box(by_id[member_id])), f'{member_id} escapes {group.id}'
        for shape in shapes:
            if shape.id not in inside:
                assert not _overlap(_box(group), _box(shape)), f'{shape.id} intrudes on {group.id}'


@pytest.mark.parametrize(
    ('header', 'axis', 'increasing'),
    [('LR', 'x', True), ('RL', 'x', False), ('TD', 'y', True), ('BT', 'y', False)],
)
def test_flow_follows_declared_direction(header, axis, increasing):
    diagram = parse_diagram(f'flowchart {header}\n    a --> b --> c\n').diagram
    coordinates = [getattr(shape.position, axis) for shape in diagram.get_shapes()]

    assert coordinates == sorted(coordinates, reverse=not increasing)
    assert len(set(coordinates)) == 3


def test_connections_end_on_shape_borders():
    diagram = parse_diagram('flowchart LR\n    a --> b\n').diagram
    first, second = diagram.get_shapes()
    connection = diagram.get_connections()[0]

    assert connection.start_point.x == pytest.approx(first.position.x + first.size.width)
    assert connection.end_point.x == pytest.approx(second.position.x)


def test_edge_spanning_layers_bends_around_the_node_between():
    diagram = parse_diagram('flowchart TD\n    a --> b --> c\n    a --> c\n').diagram
    long_edge = next(c for c in diagram.get_connections() if (c.from_id, c.to_id) == ('a', 'c'))
    middle = next(shape for shape in diagram.get_shapes() if shape.id == 'b')

    assert len(long_edge.waypoints) == 1
    bend = long_edge.waypoints[0]
    assert not (middle.position.x <= bend.x <= middle.position.x + middle.size.width)


def test_cycles_do_not_hang_or_stack_nodes():
    diagram = parse_diagram('flowchart LR\n    a --> b --> c --> a\n').diagram
    positions = {(shape.position.x, shape.position.y) for shape in diagram.get_shapes()}

    assert len(positions) == 3


def test_unconnected_nodes_form_a_grid():
    diagram = parse_diagram('flowchart TD\n' + ''.join(f'    n{index}\n' for index in range(9))).diagram

    assert len({shape.position.x for shape in diagram.get_shapes()}) == 3
    assert len({shape.position.y for shape in diagram.get_shapes()}) == 3


def test_group_membership_cycle_is_tolerated():
    diagram = Diagram(id='d')
    diagram.add_element(Shape(id='leaf', position=Point(0.0, 0.0), size=Dimensions(100.0, 50.0), label='Leaf'))
    for group_id, child_id in (('g1', 'g2'), ('g2', 'g1')):
        diagram.add_element(
            Group(
                id=group_id,
                position=Point(0.0, 0.0),
                size=Dimensions(1.0, 1.0),
                label=group_id,
                children=[child_id, 'leaf'],
            )
        )

    layout_diagram(diagram)

    assert diagram.metadata['synthesized_layout'] is True


def test_long_chain_is_laid_out_quickly():
    diagram = Diagram(id='chain')
    for index in range(1500):
        diagram.add_element(
            Shape(id=f'n{index}', position=Point(0.0, 0.0), size=Dimensions(100.0, 50.0), label=str(index))
        )
    for index in range(1499):
        diagram.add_element(
            Connection(
                id=f'e{index}',
                position=Point(0.0, 0.0),
                size=Dimensions(0.0, 0.0),
                from_id=f'n{index}',
                to_id=f'n{index + 1}',
            )
        )

    layout_diagram(diagram, 'LR')

    xs = [shape.position.x for shape in diagram.get_shapes()]
    assert xs == sorted(xs)


def test_labels_wrap_at_word_boundaries_and_keep_authored_breaks():
    assert wrap_label('one two three', columns=7) == 'one two\nthree'
    assert wrap_label('first\nsecond') == 'first\nsecond'
    assert estimate_label_size('a\nb\nc').height > estimate_label_size('a').height
