"""Tests for agent-oriented CLI features: --json envelope, inspect, formats, exit codes."""

import json

import pytest

from diacea.cli import EXIT_EMPTY_DIAGRAM, EXIT_ERROR, EXIT_OK, main


@pytest.fixture
def excalidraw_file(tmp_path):
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


@pytest.fixture
def empty_excalidraw_file(tmp_path):
    f = tmp_path / "empty.json"
    f.write_text(json.dumps({"elements": []}))
    return f


@pytest.fixture
def curved_svg_file(tmp_path):
    svg_content = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" width="300" height="200">
    <rect id="a" x="10" y="10" width="80" height="40" fill="blue"/>
    <rect id="b" x="150" y="10" width="80" height="40" fill="red"/>
    <path d="M 10 100 C 40 80, 80 80, 110 100 L 150 150 Z" fill="green"/>
</svg>"""
    f = tmp_path / "curved.svg"
    f.write_text(svg_content)
    return f


@pytest.fixture
def multipage_tldraw_file(tmp_path):
    data = {
        "document": {
            "pages": {
                "page1": {
                    "id": "page1",
                    "shapes": {
                        "shape1": {"id": "shape1", "type": "rectangle", "point": [0.0, 0.0], "size": [100.0, 50.0]}
                    },
                    "bindings": {},
                },
                "page2": {
                    "id": "page2",
                    "shapes": {
                        "shape2": {"id": "shape2", "type": "ellipse", "point": [0.0, 0.0], "size": [100.0, 50.0]}
                    },
                    "bindings": {},
                },
            }
        }
    }
    f = tmp_path / "multipage.json"
    f.write_text(json.dumps(data))
    return f


class TestJsonEnvelope:
    def test_envelope_fields(self, excalidraw_file, capsys):
        result = main(["-i", str(excalidraw_file), "-f", "mermaid", "--json"])
        assert result == EXIT_OK
        envelope = json.loads(capsys.readouterr().out)
        assert set(envelope) == {
            "output",
            "input_format",
            "output_format",
            "diagram_type",
            "elements",
            "warnings",
        }
        assert envelope["input_format"] == "excalidraw"
        assert envelope["output_format"] == "mermaid"
        assert envelope["diagram_type"] in ("flowchart", "c4", "sequence")
        assert envelope["diagram_type"] in envelope["output"].lower() or envelope["diagram_type"] == "c4"
        assert isinstance(envelope["warnings"], list)

    def test_envelope_elements_have_semantic_fields(self, excalidraw_file, capsys):
        result = main(["-i", str(excalidraw_file), "-f", "mermaid", "--json"])
        assert result == EXIT_OK
        envelope = json.loads(capsys.readouterr().out)
        element_ids = {e["id"] for e in envelope["elements"]}
        assert {"a", "b", "arr"} <= element_ids
        for element in envelope["elements"]:
            assert set(element) == {"id", "label", "semantic_type", "confidence"}
            assert 0.0 <= element["confidence"] <= 1.0

    def test_envelope_reports_forced_mermaid_type(self, excalidraw_file, capsys):
        result = main(["-i", str(excalidraw_file), "-f", "mermaid", "--mermaid-type", "c4", "--json"])
        assert result == EXIT_OK
        envelope = json.loads(capsys.readouterr().out)
        assert envelope["diagram_type"] == "c4"

    def test_envelope_diagram_type_null_for_non_mermaid(self, excalidraw_file, capsys):
        result = main(["-i", str(excalidraw_file), "-f", "plantuml", "--json"])
        assert result == EXIT_OK
        envelope = json.loads(capsys.readouterr().out)
        assert envelope["diagram_type"] is None
        assert "@startuml" in envelope["output"]

    def test_envelope_with_output_file(self, excalidraw_file, tmp_path, capsys):
        output_file = tmp_path / "out.mmd"
        result = main(["-i", str(excalidraw_file), "-f", "mermaid", "-o", str(output_file), "--json"])
        assert result == EXIT_OK
        envelope = json.loads(capsys.readouterr().out)
        assert output_file.read_text() == envelope["output"]

    def test_convert_subcommand_alias(self, excalidraw_file, capsys):
        result = main(["convert", "-i", str(excalidraw_file), "-f", "mermaid", "--json"])
        assert result == EXIT_OK
        envelope = json.loads(capsys.readouterr().out)
        assert envelope["input_format"] == "excalidraw"


class TestStructuredFailures:
    def test_file_not_found(self, capsys):
        result = main(["-i", "nonexistent.json", "-f", "mermaid"])
        assert result == EXIT_ERROR
        assert "not found" in capsys.readouterr().err

    def test_file_not_found_json(self, capsys):
        result = main(["-i", "nonexistent.json", "-f", "mermaid", "--json"])
        assert result == EXIT_ERROR
        captured = capsys.readouterr()
        assert captured.out == ""
        error = json.loads(captured.err)
        assert "not found" in error["error"]
        assert error["exit_code"] == EXIT_ERROR

    def test_unrecognized_format(self, tmp_path, capsys):
        f = tmp_path / "unknown.json"
        f.write_text('{"not": "a diagram"}')
        result = main(["-i", str(f), "-f", "mermaid"])
        assert result == EXIT_ERROR
        assert "Unrecognized input format" in capsys.readouterr().err

    def test_unrecognized_format_json(self, tmp_path, capsys):
        f = tmp_path / "unknown.json"
        f.write_text('{"not": "a diagram"}')
        result = main(["-i", str(f), "-f", "mermaid", "--json"])
        assert result == EXIT_ERROR
        error = json.loads(capsys.readouterr().err)
        assert "Unrecognized input format" in error["error"]

    def test_empty_diagram_exit_code(self, empty_excalidraw_file, capsys):
        result = main(["-i", str(empty_excalidraw_file), "-f", "mermaid"])
        assert result == EXIT_EMPTY_DIAGRAM
        assert "parsed 0 elements" in capsys.readouterr().err

    def test_empty_diagram_json(self, empty_excalidraw_file, capsys):
        result = main(["-i", str(empty_excalidraw_file), "-f", "mermaid", "--json"])
        assert result == EXIT_EMPTY_DIAGRAM
        error = json.loads(capsys.readouterr().err)
        assert "parsed 0 elements" in error["error"]
        assert error["exit_code"] == EXIT_EMPTY_DIAGRAM


class TestConversionLossWarnings:
    def test_svg_curve_warning_in_envelope(self, curved_svg_file, capsys):
        result = main(["-i", str(curved_svg_file), "-f", "mermaid", "--json"])
        assert result == EXIT_OK
        envelope = json.loads(capsys.readouterr().out)
        assert any("curve" in w for w in envelope["warnings"])

    def test_svg_curve_warning_on_stderr_in_text_mode(self, curved_svg_file, capsys):
        result = main(["-i", str(curved_svg_file), "-f", "mermaid"])
        assert result == EXIT_OK
        captured = capsys.readouterr()
        assert "Warning:" in captured.err
        assert "curve" in captured.err
        assert "Warning" not in captured.out

    def test_tldraw_multipage_warning(self, multipage_tldraw_file, capsys):
        result = main(["-i", str(multipage_tldraw_file), "-f", "d2", "--json"])
        assert result == EXIT_OK
        envelope = json.loads(capsys.readouterr().out)
        assert any("2 pages" in w for w in envelope["warnings"])

    def test_no_warnings_for_clean_input(self, excalidraw_file, capsys):
        result = main(["-i", str(excalidraw_file), "-f", "mermaid", "--json"])
        assert result == EXIT_OK
        envelope = json.loads(capsys.readouterr().out)
        assert envelope["warnings"] == []


class TestFormatsSubcommand:
    def test_formats_text(self, capsys):
        result = main(["formats"])
        assert result == EXIT_OK
        captured = capsys.readouterr().out
        assert "Input formats:" in captured
        assert "Output formats:" in captured
        for name in ("excalidraw", "obsidian", "svg", "tldraw", "mermaid", "plantuml", "graphviz", "d2", "c4"):
            assert name in captured

    def test_formats_json(self, capsys):
        result = main(["formats", "--json"])
        assert result == EXIT_OK
        listing = json.loads(capsys.readouterr().out)
        assert set(listing) == {"input_formats", "output_formats"}
        input_names = {f["name"] for f in listing["input_formats"]}
        assert input_names == {"excalidraw", "obsidian", "svg", "tldraw"}
        for input_format in listing["input_formats"]:
            assert input_format["detection"]
        output_names = {f["name"] for f in listing["output_formats"]}
        assert output_names == {"c4", "d2", "graphviz", "mermaid", "plantuml"}
        for output_format in listing["output_formats"]:
            assert isinstance(output_format["options"], list)


class TestInspectSubcommand:
    def test_inspect_text(self, excalidraw_file, capsys):
        result = main(["inspect", str(excalidraw_file)])
        assert result == EXIT_OK
        captured = capsys.readouterr().out
        assert "Format: excalidraw" in captured
        assert "Elements:" in captured
        assert "confidence=" in captured

    def test_inspect_json(self, excalidraw_file, capsys):
        result = main(["inspect", str(excalidraw_file), "--json"])
        assert result == EXIT_OK
        report = json.loads(capsys.readouterr().out)
        assert set(report) == {"input_format", "element_count", "elements", "warnings"}
        assert report["input_format"] == "excalidraw"
        assert report["element_count"] == len(report["elements"]) >= 3
        for element in report["elements"]:
            assert set(element) == {"id", "label", "semantic_type", "confidence"}

    def test_inspect_svg_detects_format_and_warnings(self, curved_svg_file, capsys):
        result = main(["inspect", str(curved_svg_file), "--json"])
        assert result == EXIT_OK
        report = json.loads(capsys.readouterr().out)
        assert report["input_format"] == "svg"
        assert any("curve" in w for w in report["warnings"])

    def test_inspect_empty_diagram_reports_warning(self, empty_excalidraw_file, capsys):
        result = main(["inspect", str(empty_excalidraw_file), "--json"])
        assert result == EXIT_OK
        report = json.loads(capsys.readouterr().out)
        assert report["element_count"] == 0
        assert any("parsed 0 elements" in w for w in report["warnings"])

    def test_inspect_missing_file(self, capsys):
        result = main(["inspect", "nonexistent.json"])
        assert result == EXIT_ERROR
        assert "not found" in capsys.readouterr().err

    def test_inspect_missing_file_json(self, capsys):
        result = main(["inspect", "nonexistent.json", "--json"])
        assert result == EXIT_ERROR
        error = json.loads(capsys.readouterr().err)
        assert "not found" in error["error"]


class TestBackwardCompatibility:
    def test_bare_invocation_still_converts(self, excalidraw_file, capsys):
        result = main(["-i", str(excalidraw_file), "-f", "mermaid"])
        assert result == EXIT_OK
        output = capsys.readouterr().out
        assert output.startswith(("flowchart", "C4Context", "sequenceDiagram"))

    def test_text_mode_stdout_unchanged(self, excalidraw_file, capsys):
        result = main(["-i", str(excalidraw_file), "-f", "plantuml"])
        assert result == EXIT_OK
        assert "@startuml" in capsys.readouterr().out
