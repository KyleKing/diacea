"""Round-trip limitation tests.

These tests document and track what information is preserved vs lost
when parsing source formats to IR and generating output formats.

Round-trip conversion is NOT supported (e.g., Excalidraw -> Mermaid -> Excalidraw).
These tests document the one-way conversion limitations.
"""

import json

import pytest

from diacea.generators import (
    C4PlantUMLGenerator,
    D2Generator,
    GraphVizGenerator,
    MermaidGenerator,
    PlantUMLGenerator,
)
from diacea.ir.elements import Dimensions
from diacea.parsers import ExcalidrawParser, SVGParser, TLDrawParser


class TestExcalidrawToIRPreservation:
    """Test what Excalidraw properties are preserved in IR."""

    def test_shape_positions_preserved(self):
        data = {
            "elements": [
                {
                    "id": "a",
                    "type": "rectangle",
                    "x": 100.0,
                    "y": 200.0,
                    "width": 150.0,
                    "height": 80.0,
                }
            ]
        }
        parser = ExcalidrawParser()
        diagram = parser.parse(data)

        shapes = diagram.get_shapes()
        assert len(shapes) == 1
        assert shapes[0].position.x == 100.0
        assert shapes[0].position.y == 200.0
        assert shapes[0].size.width == 150.0
        assert shapes[0].size.height == 80.0

    def test_text_labels_associated_with_shapes(self):
        data = {
            "elements": [
                {
                    "id": "rect1",
                    "type": "rectangle",
                    "x": 0.0,
                    "y": 0.0,
                    "width": 100.0,
                    "height": 50.0,
                },
                {
                    "id": "text1",
                    "type": "text",
                    "x": 10.0,
                    "y": 15.0,
                    "width": 80.0,
                    "height": 20.0,
                    "text": "My Label",
                },
            ]
        }
        parser = ExcalidrawParser()
        diagram = parser.parse(data)

        shapes = diagram.get_shapes()
        labeled_shapes = [s for s in shapes if s.label]
        assert any(s.label == "My Label" for s in labeled_shapes)

    def test_arrow_connections_preserved(self):
        data = {
            "elements": [
                {"id": "a", "type": "rectangle", "x": 0.0, "y": 0.0, "width": 100.0, "height": 50.0},
                {"id": "b", "type": "rectangle", "x": 200.0, "y": 0.0, "width": 100.0, "height": 50.0},
                {
                    "id": "arr",
                    "type": "arrow",
                    "x": 100.0,
                    "y": 25.0,
                    "points": [[0.0, 0.0], [100.0, 0.0]],
                    "startBinding": {"elementId": "a"},
                    "endBinding": {"elementId": "b"},
                },
            ]
        }
        parser = ExcalidrawParser()
        diagram = parser.parse(data)

        connections = diagram.get_connections()
        assert len(connections) == 1
        assert connections[0].from_id == "a"
        assert connections[0].to_id == "b"

    def test_roughness_not_preserved(self):
        """Excalidraw roughness (hand-drawn style) is not preserved in IR."""
        data = {
            "elements": [
                {
                    "id": "a",
                    "type": "rectangle",
                    "x": 0.0,
                    "y": 0.0,
                    "width": 100.0,
                    "height": 50.0,
                    "roughness": 2,
                }
            ]
        }
        parser = ExcalidrawParser()
        diagram = parser.parse(data)

        shapes = diagram.get_shapes()
        assert shapes[0].style.stroke_style in ("solid", "dashed", None)

    def test_seed_not_preserved(self):
        """Excalidraw seed (randomization) is not preserved in IR."""
        data = {
            "elements": [
                {
                    "id": "a",
                    "type": "rectangle",
                    "x": 0.0,
                    "y": 0.0,
                    "width": 100.0,
                    "height": 50.0,
                    "seed": 12345,
                }
            ]
        }
        parser = ExcalidrawParser()
        diagram = parser.parse(data)

        shapes = diagram.get_shapes()
        assert "seed" not in shapes[0].metadata


class TestTLDrawToIRPreservation:
    """Test what TLDraw properties are preserved in IR."""

    def test_shape_positions_preserved(self):
        data = {
            "document": {
                "pages": {
                    "page1": {
                        "id": "page1",
                        "shapes": {
                            "shape1": {
                                "type": "rectangle",
                                "point": [50.0, 100.0],
                                "size": [120.0, 60.0],
                            }
                        },
                        "bindings": {},
                    }
                }
            }
        }
        parser = TLDrawParser()
        diagram = parser.parse(data)

        shapes = diagram.get_shapes()
        assert len(shapes) == 1
        assert shapes[0].position.x == 50.0
        assert shapes[0].position.y == 100.0
        assert shapes[0].size.width == 120.0
        assert shapes[0].size.height == 60.0

    def test_only_first_page_by_default(self):
        """TLDraw parser processes only first page by default."""
        data = {
            "document": {
                "pages": {
                    "page1": {
                        "id": "page1",
                        "shapes": {"shape1": {"type": "rectangle", "point": [0.0, 0.0], "size": [100.0, 50.0]}},
                        "bindings": {},
                    },
                    "page2": {
                        "id": "page2",
                        "shapes": {"shape2": {"type": "ellipse", "point": [0.0, 0.0], "size": [100.0, 50.0]}},
                        "bindings": {},
                    },
                }
            }
        }
        parser = TLDrawParser()
        diagram = parser.parse(data)

        shapes = diagram.get_shapes()
        assert len(shapes) == 1

    def test_all_pages_when_page_index_none(self):
        """TLDraw parser can process all pages."""
        data = {
            "document": {
                "pages": {
                    "page1": {
                        "id": "page1",
                        "shapes": {"shape1": {"type": "rectangle", "point": [0.0, 0.0], "size": [100.0, 50.0]}},
                        "bindings": {},
                    },
                    "page2": {
                        "id": "page2",
                        "shapes": {"shape2": {"type": "ellipse", "point": [0.0, 0.0], "size": [100.0, 50.0]}},
                        "bindings": {},
                    },
                }
            }
        }
        parser = TLDrawParser(page_index=None)
        diagram = parser.parse(data)

        shapes = diagram.get_shapes()
        assert len(shapes) == 2


class TestSVGToIRPreservation:
    """Test what SVG properties are preserved in IR."""

    def test_rect_dimensions_preserved(self):
        svg = """<svg xmlns="http://www.w3.org/2000/svg">
            <rect x="10" y="20" width="100" height="50" fill="blue"/>
        </svg>"""
        parser = SVGParser()
        diagram = parser.parse(svg)

        shapes = diagram.get_shapes()
        assert len(shapes) == 1
        assert shapes[0].position.x == 10.0
        assert shapes[0].position.y == 20.0
        assert shapes[0].size.width == 100.0
        assert shapes[0].size.height == 50.0

    def test_fill_color_preserved(self):
        svg = """<svg xmlns="http://www.w3.org/2000/svg">
            <rect x="0" y="0" width="100" height="50" fill="#ff0000"/>
        </svg>"""
        parser = SVGParser()
        diagram = parser.parse(svg)

        shapes = diagram.get_shapes()
        assert shapes[0].style.fill_color == "#ff0000"

    def test_complex_paths_converted_to_bounding_box(self):
        """Complex SVG paths are converted to bounding box rectangles."""
        svg = """<svg xmlns="http://www.w3.org/2000/svg">
            <path d="M 10 10 L 100 10 L 100 50 L 10 50 Z" fill="green"/>
        </svg>"""
        parser = SVGParser()
        diagram = parser.parse(svg)

        shapes = diagram.get_shapes()
        assert len(shapes) == 1
        assert shapes[0].size.width > 0
        assert shapes[0].size.height > 0


class TestIRToOutputLimitations:
    """Test what IR properties are lost in output formats."""

    def _make_diagram_with_styled_shape(self):
        from diacea.ir import Diagram
        from diacea.ir.elements import Point, Shape, Style

        shape = Shape(
            id="styled",
            label="Styled Shape",
            shape_type="rectangle",
            position=Point(x=100.0, y=200.0),
            size=Dimensions(width=150.0, height=80.0),
            style=Style(
                fill_color="#ff0000",
                stroke_color="#0000ff",
                stroke_width=3.0,
                stroke_style="dashed",
            ),
        )
        return Diagram(id="test", elements=[shape])

    def test_plantuml_preserves_basic_structure(self):
        diagram = self._make_diagram_with_styled_shape()
        gen = PlantUMLGenerator()
        output = gen.generate(diagram)

        assert "@startuml" in output
        assert "Styled Shape" in output
        assert "@enduml" in output

    def test_plantuml_loses_exact_positions(self):
        """PlantUML output doesn't include exact x,y positions."""
        diagram = self._make_diagram_with_styled_shape()
        gen = PlantUMLGenerator()
        output = gen.generate(diagram)

        assert "100.0" not in output
        assert "200.0" not in output

    def test_mermaid_loses_exact_positions(self):
        """Mermaid output doesn't include exact x,y positions."""
        diagram = self._make_diagram_with_styled_shape()
        gen = MermaidGenerator(diagram_type="flowchart")
        output = gen.generate(diagram)

        assert "100" not in output or output.count("100") < 2
        assert "200" not in output

    def test_graphviz_lets_engine_decide_layout(self):
        """GraphViz positions are determined by layout engine, not IR."""
        diagram = self._make_diagram_with_styled_shape()
        gen = GraphVizGenerator()
        output = gen.generate(diagram)

        assert "pos=" not in output

    def test_d2_lets_engine_decide_layout(self):
        """D2 positions are determined by layout engine, not IR."""
        diagram = self._make_diagram_with_styled_shape()
        gen = D2Generator()
        output = gen.generate(diagram)

        assert "position:" not in output.lower()


class TestSemanticTypePreservation:
    """Test semantic type inference and preservation."""

    def test_database_cylinder_recognized(self):
        from diacea.ir.semantic import SemanticType, infer_semantic_type

        semantic, confidence = infer_semantic_type(shape_type="cylinder")
        assert semantic == SemanticType.DATABASE

    def test_diamond_is_decision(self):
        from diacea.ir.semantic import SemanticType, infer_semantic_type

        semantic, confidence = infer_semantic_type(shape_type="diamond")
        assert semantic == SemanticType.DECISION

    def test_semantic_type_affects_output(self):
        from diacea.ir import Diagram
        from diacea.ir.elements import Point, Shape, Style

        shape = Shape(
            id="db",
            label="Database",
            shape_type="rectangle",
            position=Point(x=0.0, y=0.0),
            size=Dimensions(width=100.0, height=50.0),
            style=Style(),
        )
        shape.semantic_type = "database"
        diagram = Diagram(id="test", elements=[shape])

        graphviz = GraphVizGenerator().generate(diagram)
        assert "cylinder" in graphviz

        d2 = D2Generator().generate(diagram)
        assert "cylinder" in d2


class TestConnectionPreservation:
    """Test connection information preservation."""

    def test_connection_endpoints_preserved(self):
        from diacea.ir import Diagram
        from diacea.ir.elements import Connection, Point, Shape, Style

        shape_a = Shape(
            id="a",
            label="A",
            shape_type="rectangle",
            position=Point(x=0.0, y=0.0),
            size=Dimensions(width=100.0, height=50.0),
            style=Style(),
        )
        shape_b = Shape(
            id="b",
            label="B",
            shape_type="rectangle",
            position=Point(x=200.0, y=0.0),
            size=Dimensions(width=100.0, height=50.0),
            style=Style(),
        )
        conn = Connection(
            id="conn",
            from_id="a",
            to_id="b",
            label="connects",
            connection_type="directed",
            position=Point(x=100.0, y=25.0),
            size=Dimensions(width=100.0, height=0.0),
            style=Style(),
        )
        diagram = Diagram(id="test", elements=[shape_a, shape_b, conn])

        plantuml = PlantUMLGenerator().generate(diagram)
        assert "a -->" in plantuml
        assert "b" in plantuml

        mermaid = MermaidGenerator(diagram_type="flowchart").generate(diagram)
        assert "a -->" in mermaid

    def test_connection_label_preserved(self):
        from diacea.ir import Diagram
        from diacea.ir.elements import Connection, Point, Shape, Style

        shape_a = Shape(
            id="a",
            label="A",
            shape_type="rectangle",
            position=Point(x=0.0, y=0.0),
            size=Dimensions(width=100.0, height=50.0),
            style=Style(),
        )
        shape_b = Shape(
            id="b",
            label="B",
            shape_type="rectangle",
            position=Point(x=200.0, y=0.0),
            size=Dimensions(width=100.0, height=50.0),
            style=Style(),
        )
        conn = Connection(
            id="conn",
            from_id="a",
            to_id="b",
            label="HTTP",
            connection_type="directed",
            position=Point(x=100.0, y=25.0),
            size=Dimensions(width=100.0, height=0.0),
            style=Style(),
        )
        diagram = Diagram(id="test", elements=[shape_a, shape_b, conn])

        plantuml = PlantUMLGenerator().generate(diagram)
        assert "HTTP" in plantuml

        graphviz = GraphVizGenerator().generate(diagram)
        assert "HTTP" in graphviz

    def test_bidirectional_connection_preserved(self):
        from diacea.ir import Diagram
        from diacea.ir.elements import Connection, Point, Shape, Style

        shape_a = Shape(
            id="a",
            label="A",
            shape_type="rectangle",
            position=Point(x=0.0, y=0.0),
            size=Dimensions(width=100.0, height=50.0),
            style=Style(),
        )
        shape_b = Shape(
            id="b",
            label="B",
            shape_type="rectangle",
            position=Point(x=200.0, y=0.0),
            size=Dimensions(width=100.0, height=50.0),
            style=Style(),
        )
        conn = Connection(
            id="conn",
            from_id="a",
            to_id="b",
            label="sync",
            connection_type="bidirectional",
            position=Point(x=100.0, y=25.0),
            size=Dimensions(width=100.0, height=0.0),
            style=Style(),
        )
        diagram = Diagram(id="test", elements=[shape_a, shape_b, conn])

        plantuml = PlantUMLGenerator().generate(diagram)
        assert "<-->" in plantuml

        mermaid = MermaidGenerator(diagram_type="flowchart").generate(diagram)
        assert "<-->" in mermaid
