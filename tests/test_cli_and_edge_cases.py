"""CLI integration tests and edge case tests."""

import json
import subprocess
import sys
from io import StringIO

import pytest

from diacea.cli import detect_input_format, main
from diacea.generators import (
    C4PlantUMLGenerator,
    D2Generator,
    GraphVizGenerator,
    MermaidGenerator,
    PlantUMLGenerator,
)
from diacea.ir import Diagram
from diacea.ir.elements import Connection, Dimensions, Point, Shape, Style
from diacea.parsers import ExcalidrawParser


class TestCLIBasics:
    """Test CLI basic functionality."""

    def test_cli_help(self):
        result = subprocess.run(
            [sys.executable, "-m", "diacea.cli", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "Universal diagram converter" in result.stdout

    def test_cli_version(self):
        result = subprocess.run(
            [sys.executable, "-m", "diacea.cli", "--version"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "diacea" in result.stdout

    def test_cli_nonexistent_file(self):
        result = main(["-i", "nonexistent.json", "-f", "mermaid"])
        assert result == 1

    def test_cli_invalid_json(self, tmp_path):
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not valid json")
        result = main(["-i", str(bad_file), "-f", "mermaid"])
        assert result == 1

    def test_cli_unknown_format(self, tmp_path):
        unknown_file = tmp_path / "unknown.json"
        unknown_file.write_text('{"not": "excalidraw"}')
        result = main(["-i", str(unknown_file), "-f", "mermaid"])
        assert result == 1


class TestCLIFormats:
    """Test CLI with different input/output formats."""

    @pytest.fixture
    def excalidraw_file(self, tmp_path):
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
        f = tmp_path / "test.json"
        f.write_text(json.dumps(data))
        return f

    @pytest.mark.parametrize("output_format", ["plantuml", "c4", "mermaid", "graphviz", "d2"])
    def test_cli_output_formats(self, excalidraw_file, output_format, tmp_path):
        output_file = tmp_path / f"output.{output_format}"
        result = main(["-i", str(excalidraw_file), "-f", output_format, "-o", str(output_file)])
        assert result == 0
        assert output_file.exists()
        content = output_file.read_text()
        assert len(content) > 0

    def test_cli_stdout_output(self, excalidraw_file, capsys):
        result = main(["-i", str(excalidraw_file), "-f", "plantuml", "-o", "-"])
        assert result == 0
        captured = capsys.readouterr()
        assert "@startuml" in captured.out

    def test_cli_stdin_input(self, monkeypatch, capsys):
        data = json.dumps(
            {
                "elements": [
                    {"id": "a", "type": "rectangle", "x": 0.0, "y": 0.0, "width": 100.0, "height": 50.0}
                ]
            }
        )
        monkeypatch.setattr("sys.stdin", StringIO(data))
        result = main(["-i", "-", "-f", "plantuml"])
        assert result == 0
        captured = capsys.readouterr()
        assert "@startuml" in captured.out


class TestFormatDetection:
    """Test input format auto-detection."""

    def test_detect_excalidraw(self):
        data = {"elements": []}
        assert detect_input_format(data) == "excalidraw"

    def test_detect_excalidraw_clipboard(self):
        data = {"type": "excalidraw/clipboard", "elements": []}
        assert detect_input_format(data) == "excalidraw"

    def test_detect_tldraw(self):
        data = {"document": {"pages": {}}}
        assert detect_input_format(data) == "tldraw"

    def test_detect_svg_xml_header(self):
        data = '<?xml version="1.0"?><svg></svg>'
        assert detect_input_format(data) == "svg"

    def test_detect_svg_no_header(self):
        data = "<svg></svg>"
        assert detect_input_format(data) == "svg"

    def test_detect_unknown_dict(self):
        with pytest.raises(ValueError, match="Unknown input format"):
            detect_input_format({"random": "data"})

    def test_detect_unknown_string(self):
        with pytest.raises(ValueError, match="Unknown string format"):
            detect_input_format("random string")


class TestLabelEscaping:
    """Test that special characters in labels are properly escaped."""

    def _make_diagram_with_label(self, label: str) -> Diagram:
        shape = Shape(
            id="test_shape",
            label=label,
            shape_type="rectangle",
            position=Point(x=0.0, y=0.0),
            size=Dimensions(width=100.0, height=50.0),
            style=Style(),
        )
        return Diagram(id="test", elements=[shape])

    def _make_diagram_with_connection_label(self, label: str) -> Diagram:
        shape1 = Shape(
            id="a",
            label="A",
            shape_type="rectangle",
            position=Point(x=0.0, y=0.0),
            size=Dimensions(width=100.0, height=50.0),
            style=Style(),
        )
        shape2 = Shape(
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
            label=label,
            connection_type="directed",
            position=Point(x=100.0, y=25.0),
            size=Dimensions(width=100.0, height=0.0),
            style=Style(),
        )
        return Diagram(id="test", elements=[shape1, shape2, conn])

    def test_plantuml_escapes_quotes(self):
        diagram = self._make_diagram_with_label('Test "quoted"')
        gen = PlantUMLGenerator()
        output = gen.generate(diagram)
        assert '\\"quoted\\"' in output

    def test_plantuml_escapes_newlines(self):
        diagram = self._make_diagram_with_label("Line1\nLine2")
        gen = PlantUMLGenerator()
        output = gen.generate(diagram)
        assert "\\n" in output

    def test_c4plantuml_escapes_quotes(self):
        diagram = self._make_diagram_with_label('Test "quoted"')
        gen = C4PlantUMLGenerator()
        output = gen.generate(diagram)
        assert '\\"quoted\\"' in output

    def test_mermaid_escapes_quotes_in_flowchart(self):
        diagram = self._make_diagram_with_label('Test "quoted"')
        gen = MermaidGenerator(diagram_type="flowchart")
        output = gen.generate(diagram)
        assert "#quot;" in output

    def test_mermaid_escapes_angle_brackets(self):
        diagram = self._make_diagram_with_label("Test <html>")
        gen = MermaidGenerator(diagram_type="flowchart")
        output = gen.generate(diagram)
        assert "&lt;" in output
        assert "&gt;" in output

    def test_mermaid_escapes_newlines(self):
        diagram = self._make_diagram_with_label("Line1\nLine2")
        gen = MermaidGenerator(diagram_type="flowchart")
        output = gen.generate(diagram)
        assert "<br/>" in output

    def test_mermaid_escapes_pipe_in_connection(self):
        diagram = self._make_diagram_with_connection_label("A | B")
        gen = MermaidGenerator(diagram_type="flowchart")
        output = gen.generate(diagram)
        assert "&#124;" in output

    def test_graphviz_escapes_quotes(self):
        diagram = self._make_diagram_with_label('Test "quoted"')
        gen = GraphVizGenerator()
        output = gen.generate(diagram)
        assert '\\"' in output

    def test_d2_escapes_newlines(self):
        diagram = self._make_diagram_with_label("Line1\nLine2")
        gen = D2Generator()
        output = gen.generate(diagram)
        assert "\\n" in output


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_diagram(self):
        diagram = Diagram(id="empty", elements=[])
        gen = PlantUMLGenerator()
        output = gen.generate(diagram)
        assert "@startuml" in output
        assert "@enduml" in output

    def test_single_shape_no_connections(self):
        shape = Shape(
            id="alone",
            label="Alone",
            shape_type="rectangle",
            position=Point(x=0.0, y=0.0),
            size=Dimensions(width=100.0, height=50.0),
            style=Style(),
        )
        diagram = Diagram(id="test", elements=[shape])
        gen = PlantUMLGenerator()
        output = gen.generate(diagram)
        assert "Alone" in output
        assert "-->" not in output

    def test_connection_without_label(self):
        shape1 = Shape(
            id="a",
            label="A",
            shape_type="rectangle",
            position=Point(x=0.0, y=0.0),
            size=Dimensions(width=100.0, height=50.0),
            style=Style(),
        )
        shape2 = Shape(
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
            label="",
            connection_type="directed",
            position=Point(x=100.0, y=25.0),
            size=Dimensions(width=100.0, height=0.0),
            style=Style(),
        )
        diagram = Diagram(id="test", elements=[shape1, shape2, conn])
        gen = PlantUMLGenerator()
        output = gen.generate(diagram)
        assert "a --> b" in output

    def test_shape_without_label(self):
        shape = Shape(
            id="nolabel",
            label="",
            shape_type="rectangle",
            position=Point(x=0.0, y=0.0),
            size=Dimensions(width=100.0, height=50.0),
            style=Style(),
        )
        diagram = Diagram(id="test", elements=[shape])
        gen = PlantUMLGenerator()
        output = gen.generate(diagram)
        assert "nolabel" in output

    def test_very_long_label(self):
        long_label = "A" * 1000
        shape = Shape(
            id="long",
            label=long_label,
            shape_type="rectangle",
            position=Point(x=0.0, y=0.0),
            size=Dimensions(width=100.0, height=50.0),
            style=Style(),
        )
        diagram = Diagram(id="test", elements=[shape])
        gen = PlantUMLGenerator()
        output = gen.generate(diagram)
        assert long_label in output

    def test_special_id_characters(self):
        shape = Shape(
            id="special-id:with.chars",
            label="Test",
            shape_type="rectangle",
            position=Point(x=0.0, y=0.0),
            size=Dimensions(width=100.0, height=50.0),
            style=Style(),
        )
        diagram = Diagram(id="test", elements=[shape])
        gen = PlantUMLGenerator()
        output = gen.generate(diagram)
        assert "special_id_with_chars" in output

    def test_bidirectional_connection(self):
        shape1 = Shape(
            id="a",
            label="A",
            shape_type="rectangle",
            position=Point(x=0.0, y=0.0),
            size=Dimensions(width=100.0, height=50.0),
            style=Style(),
        )
        shape2 = Shape(
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
            label="bidirectional",
            connection_type="bidirectional",
            position=Point(x=100.0, y=25.0),
            size=Dimensions(width=100.0, height=0.0),
            style=Style(),
        )
        diagram = Diagram(id="test", elements=[shape1, shape2, conn])

        plantuml = PlantUMLGenerator().generate(diagram)
        assert "<-->" in plantuml

        mermaid = MermaidGenerator(diagram_type="flowchart").generate(diagram)
        assert "<-->" in mermaid


class TestDuplicateElementFix:
    """Test that shapes converted to groups don't appear twice."""

    def test_no_duplicate_container_shapes(self):
        data = {
            "elements": [
                {"id": "outer", "type": "rectangle", "x": 0.0, "y": 0.0, "width": 300.0, "height": 200.0},
                {"id": "inner", "type": "rectangle", "x": 50.0, "y": 50.0, "width": 100.0, "height": 50.0},
                {
                    "id": "text",
                    "type": "text",
                    "x": 10.0,
                    "y": 10.0,
                    "width": 50.0,
                    "height": 20.0,
                    "text": "Container",
                },
            ]
        }
        parser = ExcalidrawParser()
        diagram = parser.parse(data)

        plantuml = PlantUMLGenerator().generate(diagram)
        assert plantuml.count("Container") == 1

        mermaid = MermaidGenerator(diagram_type="flowchart").generate(diagram)
        lines_with_container = [line for line in mermaid.split("\n") if "Container" in line]
        assert len(lines_with_container) == 1

    def test_group_children_inside_group_only(self):
        data = {
            "elements": [
                {"id": "outer", "type": "rectangle", "x": 0.0, "y": 0.0, "width": 300.0, "height": 200.0},
                {"id": "inner1", "type": "rectangle", "x": 20.0, "y": 20.0, "width": 80.0, "height": 40.0},
                {"id": "inner2", "type": "rectangle", "x": 120.0, "y": 20.0, "width": 80.0, "height": 40.0},
            ]
        }
        parser = ExcalidrawParser()
        diagram = parser.parse(data)

        plantuml = PlantUMLGenerator().generate(diagram)
        assert "inner1" in plantuml
        assert "inner2" in plantuml
        lines = plantuml.split("\n")
        inner1_declarations = [l for l in lines if "rectangle" in l and "inner1" in l]
        inner2_declarations = [l for l in lines if "rectangle" in l and "inner2" in l]
        assert len(inner1_declarations) == 1
        assert len(inner2_declarations) == 1

