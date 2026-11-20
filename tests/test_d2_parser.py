"""Tests for the D2 parser."""

import pytest

from diacea.generators import D2Generator
from diacea.ir import SemanticType
from diacea.parsers import D2Parser, is_d2

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
    def test_unclosed_brace_raises(self):
        with pytest.raises(ValueError, match='unclosed'):
            D2Parser().parse('a: {\n  b\n')

    def test_non_string_input_raises(self):
        with pytest.raises(ValueError, match='expects a string'):
            D2Parser().parse(['a -> b'])


def test_own_output_is_a_fixpoint():
    first = D2Generator().generate(D2Parser().parse(D2))
    second = D2Generator().generate(D2Parser().parse(first))

    assert second == first
