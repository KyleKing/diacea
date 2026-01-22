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

    def test_cli_verbose_error(self, tmp_path, capsys):
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not valid json")
        result = main(["-i", str(bad_file), "-f", "mermaid", "-v"])
        assert result == 1
        captured = capsys.readouterr()
        assert "Traceback" in captured.err or "Error" in captured.err

    def test_cli_creates_output_directory(self, tmp_path):
        data = {
            "elements": [
                {"id": "a", "type": "rectangle", "x": 0.0, "y": 0.0, "width": 100.0, "height": 50.0}
            ]
        }
        input_file = tmp_path / "input.json"
        input_file.write_text(json.dumps(data))

        nested_output = tmp_path / "nested" / "dir" / "output.puml"
        result = main(["-i", str(input_file), "-f", "plantuml", "-o", str(nested_output)])
        assert result == 0
        assert nested_output.exists()


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


class TestCLIInputFormats:
    """Test CLI with explicit input format selection."""

    def test_explicit_excalidraw_format(self, tmp_path, capsys):
        data = {
            "elements": [
                {"id": "a", "type": "rectangle", "x": 0.0, "y": 0.0, "width": 100.0, "height": 50.0}
            ]
        }
        f = tmp_path / "test.json"
        f.write_text(json.dumps(data))
        result = main(["-i", str(f), "--input-format", "excalidraw", "-f", "plantuml"])
        assert result == 0
        captured = capsys.readouterr()
        assert "@startuml" in captured.out

    def test_explicit_svg_format(self, tmp_path, capsys):
        svg_content = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" width="200" height="100">
    <rect x="10" y="10" width="80" height="40" fill="blue"/>
</svg>"""
        f = tmp_path / "test.svg"
        f.write_text(svg_content)
        result = main(["-i", str(f), "--input-format", "svg", "-f", "plantuml"])
        assert result == 0
        captured = capsys.readouterr()
        assert "@startuml" in captured.out

    def test_explicit_tldraw_format(self, tmp_path, capsys):
        data = {
            "document": {
                "pages": {
                    "page1": {
                        "id": "page1",
                        "name": "Test Page",
                        "shapes": {
                            "shape1": {
                                "id": "shape1",
                                "type": "rectangle",
                                "point": [0.0, 0.0],
                                "size": [100.0, 50.0],
                            }
                        },
                        "bindings": {},
                    }
                }
            }
        }
        f = tmp_path / "test.json"
        f.write_text(json.dumps(data))
        result = main(["-i", str(f), "--input-format", "tldraw", "-f", "d2"])
        assert result == 0
        captured = capsys.readouterr()
        assert "shape1" in captured.out

    def test_svg_auto_detection(self, tmp_path, capsys):
        svg_content = "<svg><rect x='0' y='0' width='100' height='50'/></svg>"
        f = tmp_path / "test.svg"
        f.write_text(svg_content)
        result = main(["-i", str(f), "-f", "graphviz"])
        assert result == 0
        captured = capsys.readouterr()
        assert "digraph" in captured.out


class TestCLIFormatOptions:
    """Test CLI format-specific options."""

    @pytest.fixture
    def simple_excalidraw_file(self, tmp_path):
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

    def test_mermaid_type_c4(self, simple_excalidraw_file, capsys):
        result = main([
            "-i", str(simple_excalidraw_file),
            "-f", "mermaid",
            "--mermaid-type", "c4",
        ])
        assert result == 0
        captured = capsys.readouterr()
        assert "C4" in captured.out

    def test_mermaid_type_flowchart(self, simple_excalidraw_file, capsys):
        result = main([
            "-i", str(simple_excalidraw_file),
            "-f", "mermaid",
            "--mermaid-type", "flowchart",
        ])
        assert result == 0
        captured = capsys.readouterr()
        assert "flowchart" in captured.out

    def test_graphviz_direction_tb(self, simple_excalidraw_file, capsys):
        result = main([
            "-i", str(simple_excalidraw_file),
            "-f", "graphviz",
            "--graphviz-direction", "TB",
        ])
        assert result == 0
        captured = capsys.readouterr()
        assert 'rankdir="TB"' in captured.out

    def test_graphviz_direction_lr(self, simple_excalidraw_file, capsys):
        result = main([
            "-i", str(simple_excalidraw_file),
            "-f", "graphviz",
            "--graphviz-direction", "LR",
        ])
        assert result == 0
        captured = capsys.readouterr()
        assert 'rankdir="LR"' in captured.out

    def test_graphviz_type_graph(self, simple_excalidraw_file, capsys):
        result = main([
            "-i", str(simple_excalidraw_file),
            "-f", "graphviz",
            "--graphviz-type", "graph",
        ])
        assert result == 0
        captured = capsys.readouterr()
        assert captured.out.strip().startswith("graph")

    def test_d2_direction_up(self, simple_excalidraw_file, capsys):
        result = main([
            "-i", str(simple_excalidraw_file),
            "-f", "d2",
            "--d2-direction", "up",
        ])
        assert result == 0
        captured = capsys.readouterr()
        assert "direction: up" in captured.out

    def test_d2_sketch_mode(self, simple_excalidraw_file, capsys):
        result = main([
            "-i", str(simple_excalidraw_file),
            "-f", "d2",
            "--d2-sketch",
        ])
        assert result == 0
        captured = capsys.readouterr()
        assert "a:" in captured.out or "a ->" in captured.out


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

    def test_plantuml_escapes_ampersand(self):
        diagram = self._make_diagram_with_label("A & B")
        gen = PlantUMLGenerator()
        output = gen.generate(diagram)
        assert "&amp;" in output

    def test_plantuml_escapes_angle_brackets(self):
        diagram = self._make_diagram_with_label("Test <html>")
        gen = PlantUMLGenerator()
        output = gen.generate(diagram)
        assert "~<" in output
        assert "~>" in output

    def test_c4plantuml_escapes_ampersand(self):
        diagram = self._make_diagram_with_label("A & B")
        gen = C4PlantUMLGenerator()
        output = gen.generate(diagram)
        assert "&amp;" in output

    def test_c4plantuml_escapes_angle_brackets(self):
        diagram = self._make_diagram_with_label("Test <html>")
        gen = C4PlantUMLGenerator()
        output = gen.generate(diagram)
        assert "~<" in output
        assert "~>" in output

    def test_mermaid_escapes_ampersand(self):
        diagram = self._make_diagram_with_label("A & B")
        gen = MermaidGenerator(diagram_type="flowchart")
        output = gen.generate(diagram)
        assert "&amp;" in output

    def test_mermaid_c4_escapes_special_chars(self):
        diagram = self._make_diagram_with_label('Test "quoted" & <xml>')
        diagram.elements[0].semantic_type = "person"
        gen = MermaidGenerator(diagram_type="c4")
        output = gen.generate(diagram)
        assert '\\"' in output
        assert "&amp;" in output
        assert "&lt;" in output
        assert "&gt;" in output

    def test_mermaid_connection_escapes_ampersand(self):
        diagram = self._make_diagram_with_connection_label("A & B")
        gen = MermaidGenerator(diagram_type="flowchart")
        output = gen.generate(diagram)
        assert "&amp;" in output

    def test_combined_special_chars_plantuml(self):
        diagram = self._make_diagram_with_label('Hello "World" & <Test>')
        gen = PlantUMLGenerator()
        output = gen.generate(diagram)
        assert '\\"World\\"' in output
        assert "&amp;" in output
        assert "~<Test~>" in output

    def test_combined_special_chars_mermaid(self):
        diagram = self._make_diagram_with_label('Hello "World" & <Test>')
        gen = MermaidGenerator(diagram_type="flowchart")
        output = gen.generate(diagram)
        assert "#quot;" in output
        assert "&amp;" in output
        assert "&lt;Test&gt;" in output


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

    def test_connections_only_diagram(self):
        conn = Connection(
            id="conn",
            from_id="a",
            to_id="b",
            label="link",
            connection_type="directed",
            position=Point(x=100.0, y=25.0),
            size=Dimensions(width=100.0, height=0.0),
            style=Style(),
        )
        diagram = Diagram(id="test", elements=[conn])

        plantuml = PlantUMLGenerator().generate(diagram)
        assert "@startuml" in plantuml
        assert "@enduml" in plantuml
        assert "a --> b" in plantuml

        mermaid = MermaidGenerator(diagram_type="flowchart").generate(diagram)
        assert "flowchart" in mermaid
        assert "a -->" in mermaid

    def test_deeply_nested_groups(self):
        from diacea.ir.elements import Group

        innermost = Shape(
            id="inner",
            label="Inner",
            shape_type="rectangle",
            position=Point(x=50.0, y=50.0),
            size=Dimensions(width=50.0, height=30.0),
            style=Style(),
        )
        level2 = Group(
            id="level2",
            label="Level 2",
            position=Point(x=30.0, y=30.0),
            size=Dimensions(width=100.0, height=80.0),
            style=Style(),
            children=["inner"],
        )
        level1 = Group(
            id="level1",
            label="Level 1",
            position=Point(x=10.0, y=10.0),
            size=Dimensions(width=150.0, height=120.0),
            style=Style(),
            children=["level2"],
        )
        outer = Group(
            id="outer",
            label="Outer",
            position=Point(x=0.0, y=0.0),
            size=Dimensions(width=200.0, height=160.0),
            style=Style(),
            children=["level1"],
        )
        diagram = Diagram(id="test", elements=[innermost, level2, level1, outer])

        plantuml = PlantUMLGenerator().generate(diagram)
        assert "@startuml" in plantuml
        assert "@enduml" in plantuml

        mermaid = MermaidGenerator(diagram_type="flowchart").generate(diagram)
        assert "flowchart" in mermaid

    def test_unicode_labels(self):
        shape = Shape(
            id="unicode",
            label="Hello \u4e16\u754c \u0420\u043e\u0441\u0441\u0438\u044f \ud83d\ude00",
            shape_type="rectangle",
            position=Point(x=0.0, y=0.0),
            size=Dimensions(width=100.0, height=50.0),
            style=Style(),
        )
        diagram = Diagram(id="test", elements=[shape])

        plantuml = PlantUMLGenerator().generate(diagram)
        assert "\u4e16\u754c" in plantuml

        mermaid = MermaidGenerator(diagram_type="flowchart").generate(diagram)
        assert "\u4e16\u754c" in mermaid


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


class TestSemanticInference:
    """Test semantic type inference heuristics."""

    def test_diamond_shape_is_decision(self):
        from diacea.ir.semantic import SemanticType, infer_semantic_type

        semantic, confidence = infer_semantic_type(shape_type="diamond")
        assert semantic == SemanticType.DECISION
        assert confidence >= 0.9

    def test_note_shape_is_note(self):
        from diacea.ir.semantic import SemanticType, infer_semantic_type

        semantic, confidence = infer_semantic_type(shape_type="note")
        assert semantic == SemanticType.NOTE
        assert confidence >= 0.8

    def test_sticky_shape_is_note(self):
        from diacea.ir.semantic import SemanticType, infer_semantic_type

        semantic, confidence = infer_semantic_type(shape_type="sticky")
        assert semantic == SemanticType.NOTE
        assert confidence >= 0.8

    def test_cylinder_shape_is_database(self):
        from diacea.ir.semantic import SemanticType, infer_semantic_type

        semantic, confidence = infer_semantic_type(shape_type="cylinder")
        assert semantic == SemanticType.DATABASE
        assert confidence >= 0.8

    def test_label_database_keyword(self):
        from diacea.ir.semantic import SemanticType, infer_semantic_type

        semantic, confidence = infer_semantic_type(
            shape_type="rectangle", label="PostgreSQL Database"
        )
        assert semantic == SemanticType.DATABASE
        assert confidence >= 0.6

    def test_label_api_keyword(self):
        from diacea.ir.semantic import SemanticType, infer_semantic_type

        semantic, confidence = infer_semantic_type(
            shape_type="rectangle", label="REST API Service"
        )
        assert semantic == SemanticType.SERVICE
        assert confidence >= 0.6

    def test_label_user_keyword(self):
        from diacea.ir.semantic import SemanticType, infer_semantic_type

        semantic, confidence = infer_semantic_type(shape_type="ellipse", label="Admin User")
        assert semantic == SemanticType.PERSON
        assert confidence >= 0.6

    def test_label_queue_keyword(self):
        from diacea.ir.semantic import SemanticType, infer_semantic_type

        semantic, confidence = infer_semantic_type(shape_type="rectangle", label="Kafka Queue")
        assert semantic == SemanticType.QUEUE
        assert confidence >= 0.6

    def test_icon_person_emoji(self):
        from diacea.ir.semantic import SemanticType, infer_semantic_type

        semantic, confidence = infer_semantic_type(shape_type="rectangle", label="👤 Customer")
        assert semantic == SemanticType.PERSON
        assert confidence >= 0.8

    def test_icon_database_emoji(self):
        from diacea.ir.semantic import SemanticType, infer_semantic_type

        semantic, confidence = infer_semantic_type(shape_type="rectangle", label="🗄️ Storage")
        assert semantic == SemanticType.DATABASE
        assert confidence >= 0.8

    def test_icon_cloud_emoji(self):
        from diacea.ir.semantic import SemanticType, infer_semantic_type

        semantic, confidence = infer_semantic_type(shape_type="rectangle", label="☁️ AWS")
        assert semantic == SemanticType.CLOUD
        assert confidence >= 0.8

    def test_yellow_fill_is_note(self):
        from diacea.ir.semantic import SemanticType, infer_semantic_type

        style = Style(fill_color="#ffff00")
        semantic, confidence = infer_semantic_type(
            shape_type="rectangle", label="", style=style
        )
        assert semantic == SemanticType.NOTE
        assert confidence >= 0.6

    def test_gray_dashed_is_external(self):
        from diacea.ir.semantic import SemanticType, infer_semantic_type

        style = Style(fill_color="#808080", stroke_style="dashed")
        semantic, confidence = infer_semantic_type(
            shape_type="rectangle", label="", style=style
        )
        assert semantic == SemanticType.EXTERNAL
        assert confidence >= 0.5

    def test_explicit_metadata_hint(self):
        from diacea.ir.semantic import SemanticType, infer_semantic_type

        semantic, confidence = infer_semantic_type(
            shape_type="rectangle",
            label="Box",
            metadata={"semantic_type": "database"},
        )
        assert semantic == SemanticType.DATABASE
        assert confidence == 1.0

    def test_large_rectangle_is_system(self):
        from diacea.ir.semantic import SemanticType, infer_semantic_type

        size = Dimensions(width=500.0, height=300.0)
        semantic, confidence = infer_semantic_type(
            shape_type="rectangle", label="", size=size
        )
        assert semantic == SemanticType.SYSTEM
        assert confidence >= 0.6

    def test_wide_ellipse_is_database(self):
        from diacea.ir.semantic import SemanticType, infer_semantic_type

        size = Dimensions(width=200.0, height=50.0)
        semantic, confidence = infer_semantic_type(
            shape_type="ellipse", label="", size=size
        )
        assert semantic == SemanticType.DATABASE
        assert confidence >= 0.6

    def test_combined_shape_and_label(self):
        from diacea.ir.semantic import SemanticType, infer_semantic_type

        semantic, confidence = infer_semantic_type(
            shape_type="ellipse", label="Customer", size=Dimensions(width=60.0, height=60.0)
        )
        assert semantic == SemanticType.PERSON
        assert confidence >= 0.6

