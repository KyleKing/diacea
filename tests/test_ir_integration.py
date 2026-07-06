"""Integration tests for IR-based parsing and generation."""

import json
import re
from pathlib import Path

import pytest

from diacea.generators import (
    C4PlantUMLGenerator,
    D2Generator,
    GraphVizGenerator,
    MermaidGenerator,
    PlantUMLGenerator,
)
from diacea.ir import Connection, Diagram, Dimensions, Group, Point, SemanticType, Shape
from diacea.parsers import ExcalidrawParser

_ORIGIN = Point(x=0.0, y=0.0)
_SIZE = Dimensions(width=100.0, height=60.0)


def _make_shape(shape_id, label, shape_type="rectangle", semantic_type=None):
    return Shape(
        id=shape_id,
        label=label,
        shape_type=shape_type,
        position=_ORIGIN,
        size=_SIZE,
        semantic_type=semantic_type,
    )


def _make_connection(from_id, to_id, label=""):
    return Connection(
        id=f"{from_id}-{to_id}",
        from_id=from_id,
        to_id=to_id,
        label=label,
        position=_ORIGIN,
        size=_SIZE,
    )


@pytest.fixture
def excalidraw_data():
    """Load test Excalidraw data."""
    data_file = Path("tests/data/excalidraw.json")
    with open(data_file) as f:
        return json.load(f)


class TestExcalidrawParser:
    """Test Excalidraw parser."""

    def test_parse_excalidraw(self, excalidraw_data):
        """Test parsing Excalidraw JSON to IR."""
        parser = ExcalidrawParser()
        diagram = parser.parse(excalidraw_data)

        assert isinstance(diagram, Diagram)
        assert len(diagram.elements) > 0

    def test_parse_shapes(self, excalidraw_data):
        """Test parsing shapes."""
        parser = ExcalidrawParser()
        diagram = parser.parse(excalidraw_data)

        shapes = diagram.get_shapes()
        assert len(shapes) > 0

        # Check shape properties
        for shape in shapes:
            assert shape.id
            assert shape.position
            assert shape.size
            assert shape.size.width >= 0
            assert shape.size.height >= 0

    def test_parse_connections(self, excalidraw_data):
        """Test parsing connections."""
        parser = ExcalidrawParser()
        diagram = parser.parse(excalidraw_data)

        connections = diagram.get_connections()
        assert len(connections) > 0

        # Check connection properties
        for conn in connections:
            assert conn.id
            assert conn.from_id
            assert conn.to_id

    def test_text_association(self, excalidraw_data):
        """Test that text is associated with shapes as labels."""
        parser = ExcalidrawParser()
        diagram = parser.parse(excalidraw_data)

        shapes = diagram.get_shapes()

        # At least one shape should have a label from text association
        shapes_with_labels = [s for s in shapes if s.label]
        assert len(shapes_with_labels) > 0

    def test_semantic_inference(self, excalidraw_data):
        """Test semantic type inference."""
        parser = ExcalidrawParser()
        diagram = parser.parse(excalidraw_data)

        shapes = diagram.get_shapes()

        # Shapes should have semantic types inferred
        shapes_with_semantics = [s for s in shapes if s.semantic_type]
        assert len(shapes_with_semantics) > 0

        # Check confidence scores
        for shape in shapes_with_semantics:
            assert 0.0 <= shape.semantic_confidence <= 1.0


class TestPlantUMLGenerator:
    """Test PlantUML generator."""

    def test_generate_basic_plantuml(self, excalidraw_data):
        """Test generating basic PlantUML."""
        parser = ExcalidrawParser()
        diagram = parser.parse(excalidraw_data)

        generator = PlantUMLGenerator()
        output = generator.generate(diagram)

        assert "@startuml" in output
        assert "@enduml" in output

    def test_plantuml_has_shapes(self, excalidraw_data):
        """Test that PlantUML output includes shapes."""
        parser = ExcalidrawParser()
        diagram = parser.parse(excalidraw_data)

        generator = PlantUMLGenerator()
        output = generator.generate(diagram)

        # Should have rectangle or component declarations
        assert "rectangle" in output or "component" in output or "actor" in output

    def test_plantuml_has_connections(self, excalidraw_data):
        """Test that PlantUML output includes connections."""
        parser = ExcalidrawParser()
        diagram = parser.parse(excalidraw_data)

        generator = PlantUMLGenerator()
        output = generator.generate(diagram)

        # Should have arrows
        assert "-->" in output or "<-->" in output


class TestC4PlantUMLGenerator:
    """Test C4-PlantUML generator."""

    def test_generate_c4_plantuml(self, excalidraw_data):
        """Test generating C4-PlantUML."""
        parser = ExcalidrawParser()
        diagram = parser.parse(excalidraw_data)

        generator = C4PlantUMLGenerator()
        output = generator.generate(diagram)

        assert "@startuml" in output
        assert "@enduml" in output
        assert "C4_Component.puml" in output

    def test_c4_has_elements(self, excalidraw_data):
        """Test that C4-PlantUML output includes C4 elements."""
        parser = ExcalidrawParser()
        diagram = parser.parse(excalidraw_data)

        generator = C4PlantUMLGenerator()
        output = generator.generate(diagram)

        # Should have C4 element types
        c4_elements = ["Person", "System", "Container", "Component", "ComponentDb"]
        assert any(elem in output for elem in c4_elements)

    def test_c4_has_relationships(self, excalidraw_data):
        """Test that C4-PlantUML output includes relationships."""
        parser = ExcalidrawParser()
        diagram = parser.parse(excalidraw_data)

        generator = C4PlantUMLGenerator()
        output = generator.generate(diagram)

        # Should have Rel() calls
        assert "Rel(" in output


class TestMermaidGenerator:
    """Test Mermaid generator."""

    def test_generate_mermaid(self, excalidraw_data):
        """Test generating Mermaid diagram."""
        parser = ExcalidrawParser()
        diagram = parser.parse(excalidraw_data)

        generator = MermaidGenerator()
        output = generator.generate(diagram)

        assert "flowchart" in output or "C4Context" in output or "sequenceDiagram" in output

    def test_mermaid_has_nodes(self, excalidraw_data):
        """Test that Mermaid output includes nodes."""
        parser = ExcalidrawParser()
        diagram = parser.parse(excalidraw_data)

        generator = MermaidGenerator(diagram_type="flowchart")
        output = generator.generate(diagram)

        # Should have node declarations
        assert len(output.split("\n")) > 2

    def test_mermaid_has_connections(self, excalidraw_data):
        """Test that Mermaid output includes connections."""
        parser = ExcalidrawParser()
        diagram = parser.parse(excalidraw_data)

        generator = MermaidGenerator(diagram_type="flowchart")
        output = generator.generate(diagram)

        # Should have arrows
        assert "-->" in output or "<-->" in output or "-.." in output

    def test_c4_declares_all_rel_aliases(self):
        """Every alias referenced by a Rel() must have a declaration."""
        diagram = Diagram(id="c4-test")
        diagram.elements = [
            _make_shape("customer", "Customer", semantic_type=SemanticType.PERSON),
            _make_shape("api", "API", semantic_type=SemanticType.CONTAINER),
            _make_shape("db", "Database", semantic_type=SemanticType.DATABASE),
            _make_shape("bus", "Event Bus", semantic_type=SemanticType.QUEUE),
            _make_shape("warehouse", "Warehouse", semantic_type=SemanticType.DATABASE),
            Group(
                id="platform",
                label="Platform",
                children=["api", "db", "bus"],
                position=_ORIGIN,
                size=_SIZE,
            ),
            _make_connection("customer", "api", "Uses"),
            _make_connection("api", "db", "Reads"),
            _make_connection("api", "bus", "Publishes"),
            _make_connection("bus", "warehouse", "Streams"),
        ]

        output = MermaidGenerator(diagram_type="c4").generate(diagram)

        declared = re.findall(
            r"^\s*(?:Person|System|SystemDb|SystemQueue|Container|ContainerDb|"
            r"ContainerQueue|Component)\((\w+),",
            output,
            flags=re.MULTILINE,
        )
        rel_aliases = {
            alias
            for match in re.findall(r"Rel\((\w+), (\w+),", output)
            for alias in match
        }
        assert sorted(declared) == sorted(set(declared))
        assert rel_aliases <= set(declared)
        assert '        ContainerDb(db, "Database")' in output
        assert '        ContainerQueue(bus, "Event Bus")' in output
        assert '    SystemDb(warehouse, "Warehouse")' in output

    def test_flowchart_quotes_labels_with_special_chars(self):
        """Labels containing Mermaid-special characters use the quoted form."""
        diagram = Diagram(id="quote-test")
        diagram.elements = [
            _make_shape("check", "Valid (yes/no)?", shape_type="diamond"),
            _make_shape("note", 'Say "hi" [now]'),
            _make_shape("pipe", "a|b{c}", shape_type="circle"),
            _make_shape("plain", "Plain label"),
        ]

        output = MermaidGenerator(diagram_type="flowchart").generate(diagram)

        assert '    check{"Valid (yes/no)?"}' in output
        assert '    note["Say #quot;hi#quot; [now]"]' in output
        assert '    pipe(("a|b{c}"))' in output
        assert "    plain[Plain label]" in output


class TestGraphVizGenerator:
    """Test GraphViz generator."""

    def test_generate_graphviz(self, excalidraw_data):
        """Test generating GraphViz DOT."""
        parser = ExcalidrawParser()
        diagram = parser.parse(excalidraw_data)

        generator = GraphVizGenerator()
        output = generator.generate(diagram)

        assert "digraph" in output or "graph" in output
        assert output.strip().endswith("}")

    def test_graphviz_has_nodes(self, excalidraw_data):
        """Test that GraphViz output includes nodes."""
        parser = ExcalidrawParser()
        diagram = parser.parse(excalidraw_data)

        generator = GraphVizGenerator()
        output = generator.generate(diagram)

        # Should have node declarations with attributes
        assert "[" in output and "]" in output

    def test_graphviz_has_edges(self, excalidraw_data):
        """Test that GraphViz output includes edges."""
        parser = ExcalidrawParser()
        diagram = parser.parse(excalidraw_data)

        generator = GraphVizGenerator()
        output = generator.generate(diagram)

        # Should have arrows
        assert "->" in output or "--" in output


class TestD2Generator:
    """Test D2 generator."""

    def test_generate_d2(self, excalidraw_data):
        """Test generating D2 diagram."""
        parser = ExcalidrawParser()
        diagram = parser.parse(excalidraw_data)

        generator = D2Generator()
        output = generator.generate(diagram)

        # D2 output should have content
        assert len(output) > 0
        assert len(output.split("\n")) > 1

    def test_d2_has_shapes(self, excalidraw_data):
        """Test that D2 output includes shapes."""
        parser = ExcalidrawParser()
        diagram = parser.parse(excalidraw_data)

        generator = D2Generator()
        output = generator.generate(diagram)

        # Should have shape declarations with labels
        assert ":" in output

    def test_d2_has_connections(self, excalidraw_data):
        """Test that D2 output includes connections."""
        parser = ExcalidrawParser()
        diagram = parser.parse(excalidraw_data)

        generator = D2Generator()
        output = generator.generate(diagram)

        # Should have arrows
        assert "->" in output or "<->" in output

    def test_d2_with_direction(self, excalidraw_data):
        """Test D2 with explicit direction."""
        parser = ExcalidrawParser()
        diagram = parser.parse(excalidraw_data)

        from diacea.generators.d2 import D2Config

        config = D2Config(direction="right")
        generator = D2Generator(config=config)
        output = generator.generate(diagram)

        assert "direction: right" in output


class TestEndToEndConversion:
    """Test complete end-to-end conversion workflow."""

    def test_excalidraw_to_plantuml(self, excalidraw_data):
        """Test Excalidraw → IR → PlantUML conversion."""
        # Parse Excalidraw
        parser = ExcalidrawParser()
        diagram = parser.parse(excalidraw_data)

        # Verify IR
        assert len(diagram.elements) > 0
        assert len(diagram.get_shapes()) > 0

        # Generate PlantUML
        generator = PlantUMLGenerator()
        plantuml = generator.generate(diagram)

        # Verify output
        assert plantuml.startswith("@startuml")
        assert plantuml.endswith("@enduml")
        assert len(plantuml.split("\n")) > 3  # Has content

    def test_excalidraw_to_c4(self, excalidraw_data):
        """Test Excalidraw → IR → C4-PlantUML conversion."""
        # Parse Excalidraw
        parser = ExcalidrawParser()
        diagram = parser.parse(excalidraw_data)

        # Generate C4-PlantUML
        generator = C4PlantUMLGenerator()
        c4_plantuml = generator.generate(diagram)

        # Verify output
        assert c4_plantuml.startswith("@startuml")
        assert c4_plantuml.endswith("@enduml")
        assert "!include" in c4_plantuml
        assert len(c4_plantuml.split("\n")) > 5  # Has content

    def test_excalidraw_to_mermaid(self, excalidraw_data):
        """Test Excalidraw → IR → Mermaid conversion."""
        parser = ExcalidrawParser()
        diagram = parser.parse(excalidraw_data)

        generator = MermaidGenerator()
        mermaid = generator.generate(diagram)

        # Verify output
        assert len(mermaid.split("\n")) > 2
        assert "flowchart" in mermaid or "C4Context" in mermaid or "sequenceDiagram" in mermaid

    def test_excalidraw_to_graphviz(self, excalidraw_data):
        """Test Excalidraw → IR → GraphViz conversion."""
        parser = ExcalidrawParser()
        diagram = parser.parse(excalidraw_data)

        generator = GraphVizGenerator()
        graphviz = generator.generate(diagram)

        # Verify output
        assert "digraph" in graphviz or "graph" in graphviz
        assert graphviz.strip().endswith("}")

    def test_excalidraw_to_d2(self, excalidraw_data):
        """Test Excalidraw → IR → D2 conversion."""
        parser = ExcalidrawParser()
        diagram = parser.parse(excalidraw_data)

        generator = D2Generator()
        d2 = generator.generate(diagram)

        # Verify output
        assert len(d2.split("\n")) > 1
        assert "->" in d2 or "<->" in d2
