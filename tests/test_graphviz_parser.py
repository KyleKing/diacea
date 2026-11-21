"""Tests for the GraphViz DOT parser."""

import re

import pytest

from diacea.formats import parse_diagram
from diacea.generators import GraphVizGenerator
from diacea.ir import SemanticType
from diacea.parsers import GraphVizParser, is_dot

from .ir_summary import summarize

DOT = """
// architecture
digraph "Shop" {
    rankdir=LR;
    node [shape=box, style="rounded,filled", fillcolor="#eef"];
    subgraph cluster_backend {
        label="Back end";
        api [label="API\\nserver"];
        db [shape=cylinder, label="Postgres"];
        subgraph cluster_cache { label="Caches"; redis }
    }
    user [shape=ellipse];
    "web app" -> api -> {db redis} [style=dashed, label="reads"];
    user -> "web app":n [dir=both];
}
"""


def _parse(text):
    parser = GraphVizParser()
    return parser, parser.parse(text)


class TestDetection:
    @pytest.mark.parametrize(
        'content',
        [
            'digraph { a -> b }',
            'graph G {\n a -- b\n}',
            'strict digraph "x" {}',
            '/* c */\ndigraph\n{\n}',
            '# c\ngraph {}',
        ],
    )
    def test_dot_detected(self, content):
        assert is_dot(content)

    @pytest.mark.parametrize(
        'content', ['graph TD\n    A{decision} --> B', 'flowchart LR\n A-->B', '@startuml\n@enduml', '']
    )
    def test_other_text_not_detected(self, content):
        assert not is_dot(content)


class TestStructure:
    def test_nodes_edges_and_clusters(self):
        parser, diagram = _parse(DOT)

        assert parser.warnings == []
        assert diagram.name == 'Shop'
        assert diagram.direction == 'LR'
        assert {shape.id for shape in diagram.get_shapes()} == {'api', 'db', 'redis', 'user', 'web app'}
        groups = {group.id: group for group in diagram.get_groups()}
        assert groups['group-backend'].label == 'Back end'
        assert groups['group-backend'].children == ['api', 'db', 'group-cache']
        assert groups['group-cache'].children == ['redis']

    def test_edge_chain_and_endpoint_set_expand(self):
        _, diagram = _parse(DOT)
        edges = [(c.from_id, c.to_id, c.label, c.style.stroke_style) for c in diagram.get_connections()]

        assert ('web app', 'api', 'reads', 'dashed') in edges
        assert ('api', 'db', 'reads', 'dashed') in edges
        assert ('api', 'redis', 'reads', 'dashed') in edges

    def test_ports_are_dropped_and_dir_both_is_bidirectional(self):
        _, diagram = _parse(DOT)
        link = next(c for c in diagram.get_connections() if c.from_id == 'user')

        assert link.to_id == 'web app'
        assert link.connection_type == 'bidirectional'

    def test_node_defaults_apply_within_scope(self):
        _, diagram = _parse(DOT)
        shapes = {shape.id: shape for shape in diagram.get_shapes()}

        assert shapes['api'].shape_type == 'rounded_rectangle'
        assert shapes['api'].label == 'API\nserver'
        assert shapes['api'].style.fill_color == '#eef'
        assert shapes['db'].shape_type == 'cylinder'
        assert shapes['db'].semantic_type == SemanticType.DATABASE
        assert shapes['user'].shape_type == 'ellipse'

    def test_default_node_shape_is_ellipse(self):
        _, diagram = _parse('digraph { a -> b }')

        assert {shape.shape_type for shape in diagram.get_shapes()} == {'ellipse'}

    def test_undirected_graph(self):
        _, diagram = _parse('graph { a -- b }')

        assert diagram.get_connections()[0].connection_type == 'undirected'

    def test_layout_is_synthesized_without_overlap(self):
        _, diagram = _parse(DOT)
        api, db = (next(s for s in diagram.get_shapes() if s.id == name) for name in ('api', 'db'))

        assert diagram.metadata['synthesized_layout'] is True
        assert (api.position.x, api.position.y) != (db.position.x, db.position.y)

    def test_cluster_sharing_a_node_name_stays_distinct(self):
        _, diagram = _parse('digraph { subgraph cluster_db { label="Data"; pg } db -> pg }')

        assert {shape.id for shape in diagram.get_shapes()} == {'pg', 'db'}
        assert diagram.get_groups()[0].source_shape_id != 'db'

    def test_edge_clipped_at_cluster_links_the_group(self):
        _, diagram = _parse('digraph { compound=true; subgraph cluster_x { label="X"; a } b -> a [lhead="cluster_x"] }')

        assert diagram.get_connections()[0].to_id == 'group-x'


class TestLossyInput:
    def test_html_label_is_flattened_with_warning(self):
        parser, diagram = _parse('digraph { a [label=<<b>Bold</b><br/>line>] }')

        assert diagram.get_shapes()[0].label == 'Bold\nline'
        assert any('HTML label' in warning for warning in parser.warnings)

    def test_record_label_is_flattened_with_warning(self):
        parser, diagram = _parse('digraph { a [shape=record, label="{<f0> left|right}"] }')

        assert diagram.get_shapes()[0].label == 'left\nright'
        assert any('record label' in warning for warning in parser.warnings)

    def test_unknown_shape_warns(self):
        parser, _ = _parse('digraph { a [shape=star] }')

        assert any("unsupported shape 'star'" in warning for warning in parser.warnings)


class TestErrors:
    @pytest.mark.parametrize(
        ('text', 'message'),
        [
            ('digraph { a -> b', "Line 1: unclosed '{' in DOT input"),
            ('flowchart LR', "Line 1: not a DOT document (expected 'graph' or 'digraph')"),
            ('digraph { a [label= }', "Line 1: expected an identifier but found '}'"),
            ('digraph x', "Line 1: expected '{' but found 'end of input'"),
            ('digraph {\n a [label=<x\ny>\n];\n subgraph s ;\n}', "Line 5: expected '{' but found ';'"),
            ({'not': 'text'}, 'GraphViz parser expects a string input'),
        ],
    )
    def test_invalid_dot_raises(self, text, message):
        with pytest.raises(ValueError, match=f'^{re.escape(message)}$'):
            GraphVizParser().parse(text)


def test_own_output_is_a_fixpoint():
    first = GraphVizGenerator().generate(GraphVizParser().parse(DOT))
    second = GraphVizGenerator().generate(GraphVizParser().parse(first))

    assert second == first


@pytest.mark.parametrize(
    ('source', 'expected', 'warnings'),
    [
        pytest.param(
            'digraph { subgraph cluster { a } subgraph cluster { b } '
            'subgraph cluster_x { c } subgraph cluster_x { d } }',
            {
                'nodes': [
                    ('a', 'a', 'ellipse', 'person'),
                    ('b', 'b', 'ellipse', 'person'),
                    ('c', 'c', 'ellipse', 'person'),
                    ('d', 'd', 'ellipse', 'person'),
                ],
                'groups': [
                    ('group-cluster_1', 'cluster_1', ['a']),
                    ('group-cluster_2', 'cluster_2', ['b']),
                    ('group-x', 'x', ['c', 'd']),
                ],
            },
            [],
            id='anonymous-and-reopened-clusters',
        ),
        pytest.param(
            'digraph { a [label="foo" + "bar"]; "x" + "y" -> b }',
            {
                'nodes': [
                    ('a', 'foobar', 'ellipse', 'person'),
                    ('xy', 'xy', 'ellipse', 'person'),
                    ('b', 'b', 'ellipse', 'person'),
                ],
                'edges': [('xy', 'b', '')],
            },
            [],
            id='quoted-string-concatenation',
        ),
        pytest.param(
            'digraph { a [penwidth=3]; b [penwidth=abc] }',
            {
                'nodes': [('a', 'a', 'ellipse', 'person'), ('b', 'b', 'ellipse', 'person')],
                'styles': {'a': (None, None, 3.0)},
            },
            [],
            id='numeric-penwidth-only',
        ),
        pytest.param(
            'digraph { api [label="\\N service"]; b [label="C:\\\\Nodes"]; c [label="\\\\N"] }',
            {
                'nodes': [
                    ('api', 'api service', 'ellipse', 'service'),
                    ('b', 'C:\\Nodes', 'ellipse', 'person'),
                    ('c', '\\N', 'ellipse', 'person'),
                ],
            },
            [],
            id='node-name-escape-is-not-read-inside-an-escaped-backslash',
        ),
    ],
)
def test_source_parses_to(source, expected, warnings):
    parsed = parse_diagram(source, 'graphviz')

    assert summarize(parsed.diagram) == expected
    assert parsed.warnings == warnings
