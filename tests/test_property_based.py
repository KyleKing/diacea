"""Property-based tests using Hypothesis.

These tests generate random but valid input data to find edge cases.

Run property-based tests:
    pytest tests/test_property_based.py -v
"""

from collections.abc import Callable

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
from diacea.ir.base import Generator
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
        diagram = ExcalidrawParser().parse(data)

        non_arrow_elements = [e for e in data['elements'] if e.get('type') != 'arrow']
        assert isinstance(diagram.elements, list)
        assert len(diagram.elements) <= 2 * len(non_arrow_elements)


_GENERATOR_MARKERS: list[tuple[Callable[[], Generator], str, str]] = [
    (PlantUMLGenerator, '@startuml', '@enduml'),
    (C4PlantUMLGenerator, '@startuml', '@enduml'),
    (lambda: MermaidGenerator(diagram_type='flowchart'), 'flowchart', ''),
    (GraphVizGenerator, 'digraph', '}'),
    (D2Generator, '', ''),
]


class TestGeneratorPropertyBased:
    @given(diagram=ir_diagram_strategy())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_every_generator_writes_a_complete_deterministic_document(self, diagram):
        for make_generator, head, tail in _GENERATOR_MARKERS:
            output = make_generator().generate(diagram)

            assert output.startswith(head)
            assert output.endswith(tail)
            assert make_generator().generate(diagram) == output
            if diagram.elements:
                assert output.strip()

    @pytest.mark.parametrize(
        ('make_generator', 'head', 'tail'),
        [
            (PlantUMLGenerator, '@startuml', '@enduml'),
            (lambda: MermaidGenerator(diagram_type='flowchart'), 'flowchart', ''),
        ],
    )
    @given(label=st.text(alphabet=st.characters(blacklist_categories=['Cs']), min_size=0, max_size=200))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_any_label_keeps_the_document_intact(self, make_generator, head, tail, label):
        shape = Shape(
            id='test', label=label, shape_type='rectangle', position=Point(0.0, 0.0), size=Dimensions(100.0, 50.0)
        )

        output = make_generator().generate(Diagram(id='test', elements=[shape]))

        assert output.startswith(head)
        assert output.endswith(tail)
        assert len(output.split('\n')) == (3 if head == '@startuml' else 2)


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
