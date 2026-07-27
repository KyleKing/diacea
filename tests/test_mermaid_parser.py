"""Tests for the Mermaid flowchart parser."""

import json
import textwrap

import pytest

from diacea.generators.mermaid import MermaidGenerator
from diacea.ir import Connection, Diagram, Group, Shape
from diacea.ir.semantic import SemanticType
from diacea.parsers.excalidraw import ExcalidrawParser
from diacea.parsers.mermaid import (
    MermaidParser,
    is_mermaid,
    is_mermaid_flowchart,
    is_mermaid_sequence,
)

from .configuration import TEST_DATA_DIR

MERMAID_DATA_DIR = TEST_DATA_DIR / 'mermaid'


def _parse(content: str) -> tuple[MermaidParser, Diagram]:
    parser = MermaidParser()
    return parser, parser.parse(textwrap.dedent(content))


def _shape(diagram: Diagram, element_id: str) -> Shape:
    element = diagram.get_element(element_id)
    assert isinstance(element, Shape)
    return element


class TestHeader:
    def test_flowchart_direction_recorded(self):
        _, diagram = _parse('flowchart LR\n    A --> B')
        assert diagram.metadata['mermaid']['direction'] == 'LR'
        assert diagram.metadata['synthesized_layout'] is True

    def test_legacy_graph_header(self):
        _, diagram = _parse('graph TD\n    A --> B')
        assert diagram.metadata['mermaid']['direction'] == 'TD'

    def test_header_defaults_direction(self):
        _, diagram = _parse('flowchart\n    A --> B')
        assert diagram.metadata['mermaid']['direction'] == 'TD'

    def test_inline_statements_after_header(self):
        _, diagram = _parse('graph LR; A-->B; B-->C')
        edges = {(c.from_id, c.to_id) for c in diagram.get_connections()}
        assert edges == {('A', 'B'), ('B', 'C')}


class TestFrontmatter:
    CONTENT = '---\ntitle: My Title\n---\nflowchart LR\n    A --> B'

    def test_parse_strips_frontmatter(self):
        _, diagram = _parse(self.CONTENT)
        assert diagram.name == 'My Title'
        assert {s.id for s in diagram.get_shapes()} == {'A', 'B'}
        assert diagram.metadata['mermaid']['direction'] == 'LR'

    def test_sniffers_accept_frontmatter(self):
        assert is_mermaid(self.CONTENT)
        assert is_mermaid_flowchart(self.CONTENT)

    def test_frontmatter_without_title(self):
        _, diagram = _parse('---\nconfig:\n  theme: dark\n---\ngraph TD\n    A --> B')
        assert diagram.name is None

    def test_unterminated_frontmatter_is_not_flowchart(self):
        assert not is_mermaid_flowchart('---\ntitle: Broken\nflowchart LR\n    A --> B')

    @pytest.mark.parametrize(
        'fixture_name',
        [
            'ai_patent_check_app.mmd',
            'dynamic_loading_mechanism.mmd',
            'mcp_playwright_architecture.mmd',
        ],
    )
    def test_real_frontmatter_fixtures(self, fixture_name):
        content = (TEST_DATA_DIR / 'real' / fixture_name).read_text()
        assert is_mermaid(content)
        assert is_mermaid_flowchart(content)
        diagram = MermaidParser().parse(content)
        assert len(diagram.get_shapes()) > 0
        assert diagram.name


class TestRejection:
    @pytest.mark.parametrize('header', ['C4Context', 'classDiagram', 'gantt'])
    def test_unsupported_diagram_types_rejected(self, header):
        with pytest.raises(ValueError, match=header):
            MermaidParser().parse(f'{header}\n    A->>B: hi')

    def test_arbitrary_text_rejected(self):
        with pytest.raises(ValueError, match='not a Mermaid flowchart'):
            MermaidParser().parse('hello world')

    def test_empty_input_rejected(self):
        with pytest.raises(ValueError, match='no Mermaid diagram'):
            MermaidParser().parse('')

    def test_non_string_rejected(self):
        with pytest.raises(ValueError, match='string'):
            MermaidParser().parse({'not': 'a string'})


class TestNodeShapes:
    @pytest.mark.parametrize(
        ('body', 'shape_type', 'semantic'),
        [
            ('[Plain]', 'rectangle', None),
            ('(Rounded)', 'rounded_rectangle', SemanticType.PROCESS),
            ('([Stadium])', 'stadium', SemanticType.START_END),
            ('[(Cylinder)]', 'cylinder', SemanticType.DATABASE),
            ('((Circle))', 'circle', None),
            ('{Diamond}', 'diamond', SemanticType.DECISION),
            ('{{Hexagon}}', 'hexagon', SemanticType.PROCESS),
            ('[/Parallelogram/]', 'parallelogram', SemanticType.INTERFACE),
        ],
    )
    def test_bracket_shapes(self, body, shape_type, semantic):
        _, diagram = _parse(f'flowchart LR\n    node1{body}')
        shape = _shape(diagram, 'node1')
        assert isinstance(shape, Shape)
        assert shape.shape_type == shape_type
        if semantic is not None:
            assert shape.semantic_type == semantic
            assert shape.semantic_confidence >= 0.8

    def test_bare_id_defaults_to_rectangle(self):
        _, diagram = _parse('flowchart LR\n    lonely')
        shape = _shape(diagram, 'lonely')
        assert shape.shape_type == 'rectangle'
        assert shape.label == 'lonely'

    def test_quoted_label(self):
        _, diagram = _parse('flowchart LR\n    A["Quoted label (with parens)"]')
        assert _shape(diagram, 'A').label == 'Quoted label (with parens)'

    def test_label_special_chars_unescaped(self):
        _, diagram = _parse('flowchart LR\n    A[Tom &amp; Jerry #quot;cartoon#quot; &lt;classic&gt;<br/>second line]')
        assert _shape(diagram, 'A').label == 'Tom & Jerry "cartoon" <classic>\nsecond line'

    def test_cylinder_label_infers_database(self):
        _, diagram = _parse('flowchart LR\n    db[(Users)]')
        assert _shape(diagram, 'db').semantic_type == SemanticType.DATABASE

    def test_all_shapes_have_positive_size(self):
        _, diagram = _parse('flowchart LR\n    A[Short] --> B[A much longer label here]')
        a, b = _shape(diagram, 'A'), _shape(diagram, 'B')
        assert a.size.width > 0 and a.size.height > 0
        assert b.size.width > a.size.width


class TestEdges:
    def test_directed_arrow(self):
        _, diagram = _parse('flowchart LR\n    A --> B')
        conn = diagram.get_connections()[0]
        assert (conn.from_id, conn.to_id) == ('A', 'B')
        assert conn.connection_type == 'directed'
        assert conn.style.stroke_style == 'solid'

    def test_open_link_is_undirected(self):
        _, diagram = _parse('flowchart LR\n    A --- B')
        assert diagram.get_connections()[0].connection_type == 'undirected'

    def test_dashed_arrow(self):
        _, diagram = _parse('flowchart LR\n    A -.-> B')
        conn = diagram.get_connections()[0]
        assert conn.style.stroke_style == 'dashed'
        assert conn.connection_type == 'directed'

    def test_thick_arrow(self):
        _, diagram = _parse('flowchart LR\n    A ==> B')
        conn = diagram.get_connections()[0]
        assert conn.style.stroke_width == 3.0
        assert conn.connection_type == 'directed'

    def test_bidirectional_arrow(self):
        _, diagram = _parse('flowchart LR\n    A <--> B')
        assert diagram.get_connections()[0].connection_type == 'bidirectional'

    def test_pipe_label(self):
        _, diagram = _parse('flowchart LR\n    A -->|yes &#124; no| B')
        assert diagram.get_connections()[0].label == 'yes | no'

    def test_inline_text_label(self):
        _, diagram = _parse('flowchart LR\n    A -- maybe --> B')
        assert diagram.get_connections()[0].label == 'maybe'

    def test_inline_nodes_on_edge_line_declared(self):
        _, diagram = _parse('flowchart LR\n    A[Start] --> B{Choice}')
        assert _shape(diagram, 'A').label == 'Start'
        assert _shape(diagram, 'B').shape_type == 'diamond'

    def test_chained_edges(self):
        _, diagram = _parse('flowchart LR\n    A --> B --> C')
        edges = {(c.from_id, c.to_id) for c in diagram.get_connections()}
        assert edges == {('A', 'B'), ('B', 'C')}

    def test_multi_target_edges(self):
        _, diagram = _parse('flowchart LR\n    A --> B & C')
        edges = {(c.from_id, c.to_id) for c in diagram.get_connections()}
        assert edges == {('A', 'B'), ('A', 'C')}

    def test_ampersand_inside_label_not_split(self):
        _, diagram = _parse('flowchart LR\n    A[Salt & Pepper] --> B')
        assert _shape(diagram, 'A').label == 'Salt & Pepper'
        assert len(diagram.get_connections()) == 1

    def test_inline_label_without_spaces(self):
        _, diagram = _parse('flowchart LR\n    A --Prompt with Info--> B')
        conn = diagram.get_connections()[0]
        assert (conn.from_id, conn.to_id) == ('A', 'B')
        assert conn.label == 'Prompt with Info'

    def test_thick_inline_label(self):
        _, diagram = _parse('flowchart LR\n    A ==fast==> B')
        conn = diagram.get_connections()[0]
        assert conn.label == 'fast'
        assert conn.style.stroke_width == 3.0

    def test_dotted_inline_label(self):
        _, diagram = _parse('flowchart LR\n    A -.maybe.-> B')
        conn = diagram.get_connections()[0]
        assert conn.label == 'maybe'
        assert conn.style.stroke_style == 'dashed'

    def test_node_id_with_colon(self):
        _, diagram = _parse('flowchart LR\n    Loop:Result --> State:Config')
        edges = {(c.from_id, c.to_id) for c in diagram.get_connections()}
        assert edges == {('Loop:Result', 'State:Config')}

    def test_class_suffix_stripped_from_node(self):
        _, diagram = _parse('flowchart LR\n    A[Box]:::highlight --> B')
        assert _shape(diagram, 'A').label == 'Box'
        edges = {(c.from_id, c.to_id) for c in diagram.get_connections()}
        assert edges == {('A', 'B')}

    def test_connection_endpoints_synthesized(self):
        _, diagram = _parse('flowchart LR\n    A --> B')
        conn = diagram.get_connections()[0]
        assert conn.start_point is not None
        assert conn.end_point is not None
        assert conn.start_point.x != conn.end_point.x


class TestSubgraphs:
    def test_subgraph_becomes_group(self):
        _, diagram = _parse(
            """
            flowchart TD
                subgraph cluster1[My Cluster]
                    A[One]
                    B[Two]
                end
                A --> B
            """
        )
        groups = diagram.get_groups()
        assert len(groups) == 1
        group = groups[0]
        assert group.label == 'My Cluster'
        assert group.children == ['A', 'B']

    def test_subgraph_without_brackets(self):
        _, diagram = _parse('flowchart TD\n    subgraph Zone One\n        A\n    end')
        group = diagram.get_groups()[0]
        assert group.label == 'Zone One'
        assert group.children == ['A']

    def test_nested_subgraphs(self):
        _, diagram = _parse(
            """
            flowchart TD
                subgraph outer[Outer]
                    A
                    subgraph inner[Inner]
                        B
                    end
                end
            """
        )
        outer = next(g for g in diagram.get_groups() if g.id == 'group-outer')
        inner = next(g for g in diagram.get_groups() if g.id == 'group-inner')
        assert 'group-inner' in outer.children
        assert 'A' in outer.children
        assert inner.children == ['B']

    def test_group_box_contains_children(self):
        _, diagram = _parse('flowchart LR\n    subgraph sg[Box]\n        A --> B\n    end')
        group = diagram.get_groups()[0]
        for child_id in ('A', 'B'):
            child = _shape(diagram, child_id)
            assert group.position.x <= child.position.x
            assert group.position.y <= child.position.y
            assert child.position.x + child.size.width <= group.position.x + group.size.width

    def test_node_referenced_inside_subgraph_joins_it(self):
        _, diagram = _parse(
            """
            flowchart TD
                start --> api
                subgraph backend[Backend]
                    api[API] --> db[(DB)]
                end
            """
        )
        group = diagram.get_groups()[0]
        assert set(group.children) == {'api', 'db'}
        assert 'start' not in group.children

    def test_unclosed_subgraph_warns(self):
        parser, _ = _parse('flowchart TD\n    subgraph sg[Open]\n        A')
        assert any('unclosed subgraph' in w for w in parser.warnings)

    def test_subgraph_and_node_sharing_name(self):
        _, diagram = _parse(
            """
            flowchart LR
                subgraph Results
                    A
                end
                B --> Results
            """
        )
        group = diagram.get_groups()[0]
        assert group.id == 'group-Results'
        node = _shape(diagram, 'Results')
        assert isinstance(node, Shape)
        edges = {(c.from_id, c.to_id) for c in diagram.get_connections()}
        assert edges == {('B', 'Results')}


class TestFaIcons:
    def test_icon_stripped_and_mapped(self):
        _, diagram = _parse('flowchart LR\n    B[fa:fa-database Orders DB]')
        shape = _shape(diagram, 'B')
        assert shape.label == 'Orders DB'
        assert shape.semantic_type == SemanticType.DATABASE
        assert shape.semantic_confidence >= 0.9
        assert shape.metadata['mermaid']['icons'] == ['database']

    @pytest.mark.parametrize(
        ('icon', 'semantic'),
        [
            ('cloud', SemanticType.CLOUD),
            ('cogs', SemanticType.SERVICE),
            ('envelope', SemanticType.QUEUE),
            ('globe', SemanticType.EXTERNAL),
            ('server', SemanticType.SERVER),
            ('user', SemanticType.PERSON),
        ],
    )
    def test_known_icons_map_semantics(self, icon, semantic):
        _, diagram = _parse(f'flowchart LR\n    N(fa:fa-{icon} Something)')
        shape = _shape(diagram, 'N')
        assert shape.label == 'Something'
        assert shape.semantic_type == semantic

    def test_unknown_icon_stripped_without_hint(self):
        _, diagram = _parse('flowchart LR\n    N[fa:fa-creative-commons Licensing]')
        shape = _shape(diagram, 'N')
        assert shape.label == 'Licensing'
        assert 'semantic_type' not in shape.metadata


class TestWarnings:
    @pytest.mark.parametrize(
        'line',
        [
            'classDef important fill:#f96',
            'class A important',
            'style A fill:#bbf',
            'click A "https://example.com"',
            'linkStyle 0 stroke:#ff3',
        ],
    )
    def test_directives_skipped_with_warning(self, line):
        parser, diagram = _parse(f'flowchart LR\n    A --> B\n    {line}')
        keyword = line.split()[0]
        assert any(f"line 3: skipped '{keyword}' directive" in w for w in parser.warnings)
        assert len(diagram.get_connections()) == 1

    def test_comment_skipped_with_warning(self):
        parser, _ = _parse('flowchart LR\n    %% just a note\n    A --> B')
        assert any('line 2: skipped comment' in w for w in parser.warnings)

    def test_unrecognized_line_warns_with_line_number(self):
        parser, diagram = _parse('flowchart LR\n    A --> B\n    ??? gibberish ???')
        assert any(w.startswith('line 3: unrecognized line') for w in parser.warnings)
        assert len(diagram.get_connections()) == 1

    def test_warnings_reset_between_parses(self):
        parser = MermaidParser()
        parser.parse('flowchart LR\n    %% note\n    A --> B')
        parser.parse('flowchart LR\n    A --> B')
        assert parser.warnings == []


class TestLayout:
    def test_layers_follow_topology_lr(self):
        _, diagram = _parse('flowchart LR\n    A --> B --> C')
        a, b, c = (_shape(diagram, i) for i in 'ABC')
        assert a.position.x < b.position.x < c.position.x

    def test_layers_follow_topology_td(self):
        _, diagram = _parse('flowchart TD\n    A --> B --> C')
        a, b, c = (_shape(diagram, i) for i in 'ABC')
        assert a.position.y < b.position.y < c.position.y

    def test_reversed_directions_flip_axis(self):
        _, diagram = _parse('flowchart RL\n    A --> B')
        assert _shape(diagram, 'A').position.x > _shape(diagram, 'B').position.x
        _, diagram = _parse('flowchart BT\n    A --> B')
        assert _shape(diagram, 'A').position.y > _shape(diagram, 'B').position.y

    def test_cycle_does_not_crash(self):
        _, diagram = _parse('flowchart LR\n    A --> B --> A')
        assert len(diagram.get_shapes()) == 2
        assert len(diagram.get_connections()) == 2


class TestSniffers:
    def test_is_mermaid_flowchart(self):
        assert is_mermaid_flowchart('flowchart LR\n    A --> B')
        assert is_mermaid_flowchart('%% comment first\ngraph TD\n    A')
        assert not is_mermaid_flowchart('sequenceDiagram\n    A->>B: hi')
        assert not is_mermaid_flowchart('{"elements": []}')

    def test_is_mermaid(self):
        assert is_mermaid('flowchart LR\n    A')
        assert is_mermaid('sequenceDiagram\n    A->>B: hi')
        assert is_mermaid('C4Context\n    title x')
        assert not is_mermaid('<svg></svg>')
        assert not is_mermaid('')


class TestRealWorldFixtures:
    def test_ci_pipeline_fixture(self):
        content = (MERMAID_DATA_DIR / 'ci_pipeline.mmd').read_text()
        parser = MermaidParser()
        diagram = parser.parse(content)
        shapes = {s.id: s for s in diagram.get_shapes()}
        assert set(shapes) == {
            'dev',
            'gh',
            'ci',
            'build',
            'notify',
            'registry',
            'deploy',
            'smoke',
            'prod',
        }
        assert shapes['ci'].shape_type == 'diamond'
        assert shapes['registry'].semantic_type == SemanticType.DATABASE
        edges = {(c.from_id, c.to_id) for c in diagram.get_connections()}
        assert ('ci', 'notify') in edges
        assert len(edges) == 8
        labels = {c.label for c in diagram.get_connections() if c.label}
        assert labels == {'git push', 'pass', 'fail'}

    def test_architecture_fixture(self):
        content = (MERMAID_DATA_DIR / 'architecture.mmd').read_text()
        parser = MermaidParser()
        diagram = parser.parse(content)
        group = diagram.get_groups()[0]
        assert set(group.children) == {'api', 'worker', 'db', 'cache', 'queue'}
        client = _shape(diagram, 'client')
        assert client.label == 'Web Client'
        lb = _shape(diagram, 'lb')
        assert lb.shape_type == 'parallelogram'
        edges = {(c.from_id, c.to_id) for c in diagram.get_connections()}
        assert {('lb', 'api'), ('lb', 'worker')} <= edges
        skipped = {w.split("'")[1] for w in parser.warnings if 'directive' in w}
        assert skipped == {'classDef', 'class', 'click', 'linkStyle'}

    def test_infra_topology_fixture(self):
        content = (TEST_DATA_DIR / 'real' / 'mermaid_infra_topology.mmd').read_text()
        parser = MermaidParser()
        diagram = parser.parse(content)
        assert len(diagram.get_shapes()) == 22
        assert len(diagram.get_connections()) == 40
        assert not any('unrecognized' in w or 'unsupported' in w for w in parser.warnings)
        db_instance = _shape(diagram, 'f4112290_1ec3_e711_8c5a_005056ad0002')
        assert db_instance.semantic_type == SemanticType.DATABASE
        assert db_instance.label == '[DBServer\\SharedDbInstance]'


class TestRoundTrip:
    def test_excalidraw_mermaid_round_trip(self):
        """Round-trip diacea's own flowchart output through the parser.

        Exact equality holds for the structural portion of the output. The
        trailing 'style' block cannot round-trip because the parser skips
        style directives by design (recorded as warnings), and one style line
        targets the group's source container shape, which has no Shape
        counterpart in text-based IR.
        """
        data = json.loads((TEST_DATA_DIR / 'excalidraw.json').read_text())
        generator = MermaidGenerator(diagram_type='flowchart')
        first = generator.generate(ExcalidrawParser().parse(data))

        parser = MermaidParser()
        diagram = parser.parse(first)
        second = MermaidGenerator(diagram_type='flowchart').generate(diagram)

        structural = first.split('\n\n')[0]
        assert second == structural
        assert all("skipped 'style' directive" in w for w in parser.warnings)
        assert len(parser.warnings) == 3

    def test_round_trip_is_fixpoint(self):
        data = json.loads((TEST_DATA_DIR / 'excalidraw.json').read_text())
        first = MermaidGenerator(diagram_type='flowchart').generate(ExcalidrawParser().parse(data))
        second = MermaidGenerator(diagram_type='flowchart').generate(MermaidParser().parse(first))
        third = MermaidGenerator(diagram_type='flowchart').generate(MermaidParser().parse(second))
        assert third == second

    def test_round_trip_structure_matches(self):
        data = json.loads((TEST_DATA_DIR / 'excalidraw.json').read_text())
        source = ExcalidrawParser().parse(data)
        first = MermaidGenerator(diagram_type='flowchart').generate(source)
        reparsed = MermaidParser().parse(first)

        group_source_ids = {g.source_shape_id for g in source.get_groups()}
        source_labels = {s.label for s in source.get_shapes() if s.id not in group_source_ids}
        reparsed_labels = {s.label for s in reparsed.get_shapes()}
        assert reparsed_labels == source_labels

        source_edges = {(c.from_id, c.to_id) for c in source.get_connections()}
        reparsed_edges = {(c.from_id, c.to_id) for c in reparsed.get_connections()}
        assert reparsed_edges == source_edges

        source_group = source.get_groups()[0]
        reparsed_group = reparsed.get_groups()[0]
        assert reparsed_group.label == source_group.label
        assert set(reparsed_group.children) == set(source_group.children)


class TestSequenceDiagrams:
    def test_participants_and_messages(self):
        content = textwrap.dedent("""
            sequenceDiagram
                participant web as Web App
                actor alice as Alice
                web->>api: GET /orders
                api-->>web: 200 OK
        """)
        parser = MermaidParser()
        diagram = parser.parse(content)

        shapes = diagram.get_shapes()
        assert [s.id for s in shapes] == ['web', 'alice', 'api']
        assert shapes[0].label == 'Web App'
        assert shapes[1].semantic_type == SemanticType.PERSON
        assert shapes[1].semantic_confidence == 1.0

        connections = diagram.get_connections()
        assert [(c.from_id, c.to_id, c.label) for c in connections] == [
            ('web', 'api', 'GET /orders'),
            ('api', 'web', '200 OK'),
        ]
        assert connections[0].style.stroke_style == 'solid'
        assert connections[1].style.stroke_style == 'dashed'
        assert diagram.metadata['mermaid']['diagram_type'] == 'sequence'
        assert diagram.metadata['synthesized_layout'] is True

    def test_implicit_participants_declared_in_order(self):
        diagram = MermaidParser().parse('sequenceDiagram\n    A->>B: hi\n    B->>C: bye')
        assert [s.id for s in diagram.get_shapes()] == ['A', 'B', 'C']

    @pytest.mark.parametrize(
        ('arrow', 'connection_type', 'stroke_style'),
        [
            ('->>', 'directed', 'solid'),
            ('-->>', 'directed', 'dashed'),
            ('->', 'directed', 'solid'),
            ('-->', 'directed', 'dashed'),
            ('-x', 'directed', 'solid'),
            ('--x', 'directed', 'dashed'),
            ('-)', 'directed', 'solid'),
            ('--)', 'directed', 'dashed'),
            ('<<->>', 'bidirectional', 'solid'),
            ('<<-->>', 'bidirectional', 'dashed'),
        ],
    )
    def test_arrow_variants(self, arrow, connection_type, stroke_style):
        diagram = MermaidParser().parse(f'sequenceDiagram\n    A{arrow}B: msg')
        connection = diagram.get_connections()[0]
        assert connection.connection_type == connection_type
        assert connection.style.stroke_style == stroke_style
        assert connection.metadata['mermaid']['arrow'] == arrow

    def test_activation_shorthand(self):
        diagram = MermaidParser().parse('sequenceDiagram\n    A->>+B: start\n    B-->>-A: done')
        edges = [(c.from_id, c.to_id) for c in diagram.get_connections()]
        assert edges == [('A', 'B'), ('B', 'A')]

    def test_blocks_and_notes_skipped_but_messages_kept(self):
        content = textwrap.dedent("""
            sequenceDiagram
                autonumber
                A->>B: request
                alt success
                    B-->>A: ok
                else failure
                    B-->>A: error
                end
                Note over A,B: retries not shown
                loop every minute
                    A->>B: poll
                end
        """)
        parser = MermaidParser()
        diagram = parser.parse(content)

        assert len(diagram.get_connections()) == 4
        skipped = [w for w in parser.warnings if 'sequence directive' in w]
        assert len(skipped) == 7

    def test_self_message(self):
        diagram = MermaidParser().parse('sequenceDiagram\n    A->>A: think')
        connection = diagram.get_connections()[0]
        assert connection.from_id == connection.to_id == 'A'

    def test_frontmatter_title(self):
        content = '---\ntitle: Checkout Flow\n---\nsequenceDiagram\n    A->>B: hi'
        diagram = MermaidParser().parse(content)
        assert diagram.name == 'Checkout Flow'

    def test_inline_title(self):
        diagram = MermaidParser().parse('sequenceDiagram\n    title Checkout\n    A->>B: hi')
        assert diagram.name == 'Checkout'

    def test_layout_places_participants_along_x(self):
        diagram = MermaidParser().parse('sequenceDiagram\n    A->>B: hi\n    B->>C: bye')
        xs = [s.position.x for s in diagram.get_shapes()]
        assert xs == sorted(xs)
        assert len(set(xs)) == 3

    def test_sniffers(self):
        assert is_mermaid_sequence('sequenceDiagram\n    A->>B: hi')
        assert not is_mermaid_sequence('flowchart LR\n    A --> B')
        assert is_mermaid('sequenceDiagram\n    A->>B: hi')

    def test_generator_honors_sequence_metadata(self):
        diagram = MermaidParser().parse('sequenceDiagram\n    A->>B: hi\n    A->>C: also')
        generator = MermaidGenerator()
        output = generator.generate(diagram)
        assert generator.detected_type == 'sequence'
        assert output.startswith('sequenceDiagram')

    def test_round_trip_is_fixpoint(self):
        content = textwrap.dedent("""
            sequenceDiagram
                participant web as Web App
                actor alice as Alice
                web->>api: GET /orders
                api-->>web: 200 OK
                alice->>web: click
        """)
        first = MermaidGenerator().generate(MermaidParser().parse(content))
        second = MermaidGenerator().generate(MermaidParser().parse(first))
        assert second == first
