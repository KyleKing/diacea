"""Property-based tests using Hypothesis.

These tests generate random but valid input data to find edge cases.

Run property-based tests:
    pytest tests/test_property_based.py -v
"""

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from diacea.formats import OUTPUT_FORMATS, parse_diagram, render_diagram, verify_conversion
from diacea.generators import (
    C4PlantUMLGenerator,
    D2Generator,
    GraphVizGenerator,
    MermaidGenerator,
    PlantUMLGenerator,
)
from diacea.ir import Connection, Diagram, Group
from diacea.ir.elements import Dimensions, Point, Shape, Style
from diacea.parsers import ExcalidrawParser

# beartype checks a randomly sampled list item with the `random` module, which Hypothesis flags when it
# happens while a strategy builds IR objects; the sampling does not affect what the tests generate
pytestmark = pytest.mark.filterwarnings('ignore:Do not use the `random` module inside strategies')


def excalidraw_shape_strategy():
    """Generate random Excalidraw shape data."""
    return st.fixed_dictionaries(
        {
            'id': st.text(alphabet='abcdefghijklmnopqrstuvwxyz0123456789_', min_size=1, max_size=20),
            'type': st.sampled_from(['rectangle', 'ellipse', 'diamond', 'text']),
            'x': st.floats(min_value=-10000.0, max_value=10000.0, allow_nan=False),
            'y': st.floats(min_value=-10000.0, max_value=10000.0, allow_nan=False),
            'width': st.floats(min_value=1.0, max_value=1000.0, allow_nan=False),
            'height': st.floats(min_value=1.0, max_value=1000.0, allow_nan=False),
        }
    )


def excalidraw_text_strategy():
    """Generate random Excalidraw text element data."""
    return st.fixed_dictionaries(
        {
            'id': st.text(alphabet='abcdefghijklmnopqrstuvwxyz0123456789_', min_size=1, max_size=20),
            'type': st.just('text'),
            'x': st.floats(min_value=-10000.0, max_value=10000.0, allow_nan=False),
            'y': st.floats(min_value=-10000.0, max_value=10000.0, allow_nan=False),
            'width': st.floats(min_value=1.0, max_value=500.0, allow_nan=False),
            'height': st.floats(min_value=1.0, max_value=100.0, allow_nan=False),
            'text': st.text(min_size=0, max_size=200),
        }
    )


def excalidraw_diagram_strategy():
    """Generate random Excalidraw diagram data."""
    return st.fixed_dictionaries(
        {
            'type': st.just('excalidraw'),
            'elements': st.lists(
                st.one_of(excalidraw_shape_strategy(), excalidraw_text_strategy()),
                min_size=0,
                max_size=50,
            ),
        }
    )


def ir_shape_strategy():
    """Generate random IR Shape objects."""
    return st.builds(
        Shape,
        id=st.text(alphabet='abcdefghijklmnopqrstuvwxyz0123456789_', min_size=1, max_size=20),
        label=st.text(min_size=0, max_size=100),
        shape_type=st.sampled_from(['rectangle', 'ellipse', 'diamond', 'circle', 'text']),
        position=st.builds(
            Point,
            x=st.floats(min_value=-10000.0, max_value=10000.0, allow_nan=False),
            y=st.floats(min_value=-10000.0, max_value=10000.0, allow_nan=False),
        ),
        size=st.builds(
            Dimensions,
            width=st.floats(min_value=1.0, max_value=1000.0, allow_nan=False),
            height=st.floats(min_value=1.0, max_value=1000.0, allow_nan=False),
        ),
        style=st.builds(
            Style,
            fill_color=st.one_of(st.none(), st.from_regex(r'#[0-9a-fA-F]{6}', fullmatch=True)),
            stroke_color=st.one_of(st.none(), st.from_regex(r'#[0-9a-fA-F]{6}', fullmatch=True)),
            stroke_width=st.one_of(st.none(), st.floats(min_value=0.5, max_value=10.0, allow_nan=False)),
            stroke_style=st.sampled_from(['solid', 'dashed']),
        ),
    )


def ir_diagram_strategy():
    """Generate random IR Diagram with just shapes (no connections)."""
    return st.builds(
        Diagram,
        id=st.text(alphabet='abcdefghijklmnopqrstuvwxyz0123456789_', min_size=1, max_size=20),
        name=st.text(min_size=0, max_size=50),
        elements=st.lists(ir_shape_strategy(), min_size=0, max_size=30),
    )


class TestParserPropertyBased:
    """Property-based tests for parsers."""

    @given(data=excalidraw_diagram_strategy())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_excalidraw_parser_handles_any_valid_input(self, data):
        """Parser should never crash on valid input structure."""
        parser = ExcalidrawParser()
        diagram = parser.parse(data)

        assert isinstance(diagram, Diagram)
        assert diagram.id is not None
        assert isinstance(diagram.elements, list)

    @given(data=excalidraw_diagram_strategy())
    @settings(max_examples=20, suppress_health_check=[HealthCheck.too_slow])
    def test_shape_count_matches_input(self, data):
        """Number of parsed shapes should relate to input elements."""
        parser = ExcalidrawParser()
        diagram = parser.parse(data)

        non_arrow_elements = [e for e in data['elements'] if e.get('type') != 'arrow']
        assert len(diagram.elements) <= len(non_arrow_elements) + len(non_arrow_elements)


class TestGeneratorPropertyBased:
    """Property-based tests for generators."""

    @given(diagram=ir_diagram_strategy())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_plantuml_never_crashes(self, diagram):
        """PlantUML generator should never crash on valid IR."""
        gen = PlantUMLGenerator()
        output = gen.generate(diagram)

        assert isinstance(output, str)
        assert '@startuml' in output
        assert '@enduml' in output

    @given(diagram=ir_diagram_strategy())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_mermaid_never_crashes(self, diagram):
        """Mermaid generator should never crash on valid IR."""
        gen = MermaidGenerator(diagram_type='flowchart')
        output = gen.generate(diagram)

        assert isinstance(output, str)
        assert 'flowchart' in output.lower()

    @given(diagram=ir_diagram_strategy())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_graphviz_never_crashes(self, diagram):
        """GraphViz generator should never crash on valid IR."""
        gen = GraphVizGenerator()
        output = gen.generate(diagram)

        assert isinstance(output, str)
        assert 'digraph' in output or 'graph' in output

    @given(diagram=ir_diagram_strategy())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_d2_never_crashes(self, diagram):
        """D2 generator should never crash on valid IR."""
        gen = D2Generator()
        output = gen.generate(diagram)

        assert isinstance(output, str)

    @given(diagram=ir_diagram_strategy())
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    def test_all_generators_produce_output(self, diagram):
        """All generators should produce non-empty output for non-empty diagrams."""
        generators = [
            PlantUMLGenerator(),
            C4PlantUMLGenerator(),
            MermaidGenerator(diagram_type='flowchart'),
            GraphVizGenerator(),
            D2Generator(),
        ]

        for gen in generators:
            output = gen.generate(diagram)
            assert isinstance(output, str)
            if diagram.elements:
                assert output.strip()


class TestEscapingPropertyBased:
    """Property-based tests for label escaping."""

    @given(
        label=st.text(
            alphabet=st.characters(blacklist_categories=['Cs']),
            min_size=0,
            max_size=200,
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_labels_never_break_plantuml(self, label):
        """Any label should be escapable for PlantUML."""
        shape = Shape(
            id='test',
            label=label,
            shape_type='rectangle',
            position=Point(x=0.0, y=0.0),
            size=Dimensions(width=100.0, height=50.0),
            style=Style(),
        )
        diagram = Diagram(id='test', elements=[shape])

        gen = PlantUMLGenerator()
        output = gen.generate(diagram)

        assert '@startuml' in output
        assert '@enduml' in output

    @given(
        label=st.text(
            alphabet=st.characters(blacklist_categories=['Cs']),
            min_size=0,
            max_size=200,
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_labels_never_break_mermaid(self, label):
        """Any label should be escapable for Mermaid."""
        shape = Shape(
            id='test',
            label=label,
            shape_type='rectangle',
            position=Point(x=0.0, y=0.0),
            size=Dimensions(width=100.0, height=50.0),
            style=Style(),
        )
        diagram = Diagram(id='test', elements=[shape])

        gen = MermaidGenerator(diagram_type='flowchart')
        output = gen.generate(diagram)

        assert 'flowchart' in output.lower()


class TestIdempotency:
    """Test that operations are idempotent."""

    @given(diagram=ir_diagram_strategy())
    @settings(max_examples=20, suppress_health_check=[HealthCheck.too_slow])
    def test_generation_is_idempotent(self, diagram):
        """Generating from the same diagram should produce the same output."""
        gen = PlantUMLGenerator()

        output1 = gen.generate(diagram)
        output2 = gen.generate(diagram)

        assert output1 == output2


_PUNCTUATED_LABEL = (
    st.text(alphabet='abcXYZ 019-_.,:;()[]{}<>|&"\'#/\\?!=+*%@$`~^', min_size=1, max_size=18)
    .map(str.strip)
    .filter(bool)
)


@st.composite
def labelled_graph_strategy(draw):
    """Node labels, labelled edges between them, and how many nodes sit in one group."""
    count = draw(st.integers(1, 6))
    labels = draw(st.lists(_PUNCTUATED_LABEL, min_size=count, max_size=count))
    endpoint = st.integers(0, count - 1)
    edges = draw(st.lists(st.tuples(endpoint, endpoint, st.one_of(st.just(''), _PUNCTUATED_LABEL)), max_size=6))
    return labels, edges, draw(st.integers(0, count)), draw(_PUNCTUATED_LABEL)


def _build_labelled_graph(labels, edges, grouped, group_label):
    diagram = Diagram(id='graph', metadata={'explicit_shapes': True})
    for index, label in enumerate(labels):
        diagram.add_element(
            Shape(id=f'n{index}', position=Point(index * 200.0, 0.0), size=Dimensions(120.0, 60.0), label=label)
        )
    for index, (source, target, label) in enumerate(edges):
        if source != target:
            diagram.add_element(
                Connection(
                    id=f'e{index}',
                    position=Point(0.0, 0.0),
                    size=Dimensions(1.0, 1.0),
                    from_id=f'n{source}',
                    to_id=f'n{target}',
                    label=label,
                )
            )
    if grouped:
        diagram.add_element(
            Group(
                id='group-g',
                position=Point(0.0, 0.0),
                size=Dimensions(1.0, 1.0),
                label=group_label,
                children=[f'n{index}' for index in range(grouped)],
            )
        )
    return diagram


class TestLabelsSurviveEveryFormat:
    """Whatever punctuation a label holds, each format must write it so that it reads back intact."""

    @given(labelled_graph_strategy())
    @settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_structure_and_labels_read_back(self, graph):
        diagram = _build_labelled_graph(*graph)
        edge_labels = sorted(conn.label for conn in diagram.get_connections())

        for name, output_format in OUTPUT_FORMATS.items():
            if output_format.reads_back_as is None:
                continue
            options = {'mermaid_type': 'flowchart'} if name == 'mermaid' else {}
            result = render_diagram(diagram, name, **options)

            assert verify_conversion(result) == [], name
            reparsed = parse_diagram(result.output, output_format.reads_back_as).diagram
            assert sorted(conn.label for conn in reparsed.get_connections()) == edge_labels, name
