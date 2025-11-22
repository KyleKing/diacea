"""Integration tests for IR-based parsing and generation."""

import json
from pathlib import Path

import pytest

from diacea.generators import C4PlantUMLGenerator, PlantUMLGenerator
from diacea.ir import Diagram, SemanticType
from diacea.parsers import ExcalidrawParser


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
