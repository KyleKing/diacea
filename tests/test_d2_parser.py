"""Tests for the D2 parser."""

import re

import pytest

from diacea.formats import parse_diagram
from diacea.generators import D2Generator
from diacea.ir import SemanticType
from diacea.parsers import D2Parser, is_d2

from .ir_summary import summarize

D2 = """
direction: right
title: |md # Shop | {near: top-center}
# a comment
aws: AWS Cloud {
  vpc: {
    api: "API: v2" {shape: hexagon; style.fill: "#fff"}
    db: Orders {shape: cylinder}
    api -> db: reads {style.stroke-dash: 3}
  }
  s3.shape: stored_data
  vpc.api -> s3
}
user: User's laptop {shape: person}
user -> aws.vpc.api -> aws.s3: uses
user <- aws.vpc.db
a -- b; b <-> c
"""


def _parse(text):
    parser = D2Parser()
    return parser, parser.parse(text)


class TestDetection:
    def test_statements_detected(self):
        assert is_d2('a -> b: hi {\n  style.stroke: red\n}\n')
        assert is_d2('x: X {\n  y: Y\n}\n')

    @pytest.mark.parametrize('content', ['', 'hello world\nfoo', '{"a": 1}', 'Some text: with colon\nAnother line'])
    def test_prose_and_json_not_detected(self, content):
        assert not is_d2(content)


class TestStructure:
    def test_containers_become_nested_groups(self):
        parser, diagram = _parse(D2)
        groups = {group.id: group for group in diagram.get_groups()}

        assert parser.warnings == []
        assert diagram.name == 'Shop'
        assert diagram.direction == 'LR'
        assert groups['aws'].label == 'AWS Cloud'
        assert groups['aws'].children == ['vpc', 's3']
        assert groups['vpc'].children == ['api', 'db']

    def test_shapes_labels_and_styles(self):
        _, diagram = _parse(D2)
        shapes = {shape.id: shape for shape in diagram.get_shapes()}

        assert shapes['api'].label == 'API: v2'
        assert shapes['api'].shape_type == 'hexagon'
        assert shapes['api'].style.fill_color == '#fff'
        assert shapes['db'].semantic_type == SemanticType.DATABASE
        assert shapes['s3'].shape_type == 'cylinder'
        assert shapes['user'].label == "User's laptop"
        assert shapes['user'].shape_type == 'person'

    def test_connections_resolve_relative_to_their_container(self):
        _, diagram = _parse(D2)
        edges = [(c.from_id, c.to_id, c.label, c.connection_type) for c in diagram.get_connections()]

        assert ('api', 'db', 'reads', 'directed') in edges
        assert ('api', 's3', '', 'directed') in edges
        assert ('user', 'api', 'uses', 'directed') in edges
        assert ('api', 's3', 'uses', 'directed') in edges
        assert ('db', 'user', '', 'directed') in edges
        assert ('a', 'b', '', 'undirected') in edges
        assert ('b', 'c', '', 'bidirectional') in edges

    def test_dashed_connection_style(self):
        _, diagram = _parse(D2)
        reads = next(c for c in diagram.get_connections() if c.label == 'reads')

        assert reads.style.stroke_style == 'dashed'

    def test_same_name_in_two_containers_gets_distinct_ids(self):
        _, diagram = _parse('a: {x}\nb: {x}\na.x -> b.x\n')

        assert {shape.id for shape in diagram.get_shapes()} == {'a_x', 'b_x'}
        assert [(c.from_id, c.to_id) for c in diagram.get_connections()] == [('a_x', 'b_x')]

    def test_parent_reference(self):
        _, diagram = _parse('outer: {\n  inner\n  inner -> _.sibling\n}\nsibling\n')

        assert [(c.from_id, c.to_id) for c in diagram.get_connections()] == [('inner', 'sibling')]


class TestSkippedSyntax:
    @pytest.mark.parametrize(
        ('line', 'reason'),
        [
            ('vars: {\n  d2-config: {sketch: true}\n}', "'vars' block"),
            ('*.style.fill: red', 'glob'),
            ('(a -> b)[0].style.stroke: red', 'connection reference'),
            ('...@shared', 'import'),
        ],
    )
    def test_skipped_with_warning(self, line, reason):
        parser, diagram = _parse(f'a -> b\n{line}\n')

        assert any(reason in warning for warning in parser.warnings)
        assert {shape.id for shape in diagram.get_shapes()} == {'a', 'b'}

    def test_sql_table_fields_are_dropped_with_warning(self):
        parser, diagram = _parse('users: {\n  shape: sql_table\n  id: int\n  name: text\n}\n')

        assert [shape.id for shape in diagram.get_shapes()] == ['users']
        assert any('fields of sql_table' in warning for warning in parser.warnings)


class TestErrors:
    @pytest.mark.parametrize(
        ('text', 'message'),
        [
            ('a: {\n  b\n', "Line 1: unclosed '{' in D2 input"),
            ('\n\na: {\n', "Line 3: unclosed '{' in D2 input"),
            (['a -> b'], 'D2 parser expects a string input'),
        ],
    )
    def test_invalid_d2_raises(self, text, message):
        with pytest.raises(ValueError, match=f'^{re.escape(message)}$'):
            D2Parser().parse(text)


def test_own_output_is_a_fixpoint():
    first = D2Generator().generate(D2Parser().parse(D2))
    second = D2Generator().generate(D2Parser().parse(first))

    assert second == first


@pytest.mark.parametrize(
    ('source', 'expected', 'warnings'),
    [
        pytest.param(
            'a: {\n  b: {\n    x -> _.y\n    x -> _._.z\n  }\n}\n',
            {
                'nodes': [
                    ('x', 'x', 'rectangle', 'component'),
                    ('y', 'y', 'rectangle', 'component'),
                    ('z', 'z', 'rectangle', 'component'),
                ],
                'groups': [('a', 'a', ['b', 'y']), ('b', 'b', ['x'])],
                'edges': [('x', 'y', ''), ('x', 'z', '')],
            },
            [],
            id='parent-references-resolve-one-level-each',
        ),
        pytest.param(
            'a -> b -> c -> d\n',
            {
                'nodes': [
                    ('a', 'a', 'rectangle', 'component'),
                    ('b', 'b', 'rectangle', 'component'),
                    ('c', 'c', 'rectangle', 'component'),
                    ('d', 'd', 'rectangle', 'component'),
                ],
                'edges': [('a', 'b', ''), ('b', 'c', ''), ('c', 'd', '')],
            },
            [],
            id='connection-chain',
        ),
        pytest.param(
            'x:"a;b"\ny: "c;d"\nx->y\n',
            {
                'nodes': [('x', 'a;b', 'rectangle', 'component'), ('y', 'c;d', 'rectangle', 'component')],
                'edges': [('x', 'y', '')],
            },
            [],
            id='quoted-labels-hide-separators',
        ),
        pytest.param(
            'a: A {style.stroke: "#f00"}\n',
            {'nodes': [('a', 'A', 'rectangle', 'component')], 'styles': {'a': (None, '#f00', None)}},
            [],
            id='stroke-only-style',
        ),
        pytest.param(
            'a: |md # Hi | there|\nb: c\na -> b\n',
            {
                'nodes': [('a', 'Hi | there', 'rectangle', 'component'), ('b', 'c', 'rectangle', 'component')],
                'edges': [('a', 'b', '')],
            },
            [],
            id='block-string-with-pipe',
        ),
        pytest.param(
            'a: ||md x | y||\nb\na -> b\n',
            {
                'nodes': [('a', 'x | y', 'rectangle', 'component'), ('b', 'b', 'rectangle', 'component')],
                'edges': [('a', 'b', '')],
            },
            [],
            id='double-pipe-block-string',
        ),
        pytest.param(
            'a: |`md x | y`|\nb\na -> b\n',
            {
                'nodes': [('a', 'x | y', 'rectangle', 'component'), ('b', 'b', 'rectangle', 'component')],
                'edges': [('a', 'b', '')],
            },
            [],
            id='backtick-block-string',
        ),
        pytest.param(
            'g: {\n  a: ||md x | y } z {||\n}\nb -> g.a\n',
            {
                'nodes': [('a', 'x | y } z {', 'rectangle', 'component'), ('b', 'b', 'rectangle', 'component')],
                'groups': [('g', 'g', ['a'])],
                'edges': [('b', 'a', '')],
            },
            [],
            id='double-pipe-block-string-hides-pipe-and-brace',
        ),
        pytest.param(
            'a: |`md x | y; z`|; b -> a\n',
            {
                'nodes': [('a', 'x | y; z', 'rectangle', 'component'), ('b', 'b', 'rectangle', 'component')],
                'edges': [('b', 'a', '')],
            },
            [],
            id='backtick-block-string-hides-pipe-and-semicolon',
        ),
        pytest.param(
            'g."x.y": X\nb -> g."x.y"\n',
            {
                'nodes': [('x.y', 'X', 'rectangle', 'component'), ('b', 'b', 'rectangle', 'component')],
                'groups': [('g', 'g', ['x.y'])],
                'edges': [('b', 'x.y', '')],
            },
            [],
            id='quoted-key-segment-keeps-its-dot',
        ),
    ],
)
def test_source_parses_to(source, expected, warnings):
    parsed = parse_diagram(source, 'd2')

    assert summarize(parsed.diagram) == expected
    assert parsed.warnings == warnings
