"""Tests for Obsidian Excalidraw plugin (.excalidraw.md) input support."""

import pytest

from diacea.cli import detect_input_format, main
from diacea.parsers import ExcalidrawParser, extract_excalidraw_json, is_obsidian_excalidraw
from diacea.parsers import obsidian as obsidian_module

from .configuration import TEST_DATA_DIR

PLAIN_FIXTURE = TEST_DATA_DIR / "obsidian_plain.excalidraw.md"
COMPRESSED_FIXTURE = TEST_DATA_DIR / "obsidian_compressed.excalidraw.md"


class TestExtraction:
    """Test extraction of Excalidraw JSON from markdown notes."""

    def test_extract_plain_json(self):
        scene = extract_excalidraw_json(PLAIN_FIXTURE.read_text())

        assert scene["type"] == "excalidraw"
        element_ids = {elem["id"] for elem in scene["elements"]}
        assert element_ids == {"rectClient", "textCli1", "rectServer", "textSrv1", "arrowReq1"}

    def test_extract_compressed_json(self):
        pytest.importorskip("lzstring")

        scene = extract_excalidraw_json(COMPRESSED_FIXTURE.read_text())

        plain_scene = extract_excalidraw_json(PLAIN_FIXTURE.read_text())
        assert scene == plain_scene

    def test_extract_missing_drawing_section(self):
        content = "---\nexcalidraw-plugin: parsed\n---\n\n# Text Elements\n"

        with pytest.raises(ValueError, match="No '# Drawing' section"):
            extract_excalidraw_json(content)

    def test_extract_compressed_without_lzstring(self, monkeypatch):
        monkeypatch.setattr(obsidian_module, "_HAS_LZSTRING", False)

        with pytest.raises(ValueError, match=r"pip install 'diacea\[obsidian\]'"):
            extract_excalidraw_json(COMPRESSED_FIXTURE.read_text())


class TestDetection:
    """Test auto-detection of the Obsidian markdown format."""

    def test_is_obsidian_excalidraw(self):
        assert is_obsidian_excalidraw(PLAIN_FIXTURE.read_text())
        assert is_obsidian_excalidraw(COMPRESSED_FIXTURE.read_text())
        assert not is_obsidian_excalidraw('{"elements": []}')
        assert not is_obsidian_excalidraw("# A regular markdown note\n\nSome text.")

    def test_detect_input_format(self):
        assert detect_input_format(PLAIN_FIXTURE.read_text()) == "obsidian"

        with pytest.raises(ValueError, match="Unknown string format"):
            detect_input_format("plain text that is not a diagram")


class TestEndToEnd:
    """Test parsing and CLI conversion of Obsidian fixtures."""

    def test_parse_extracted_scene(self):
        scene = extract_excalidraw_json(PLAIN_FIXTURE.read_text())

        diagram = ExcalidrawParser().parse(scene)

        shapes = [shape for shape in diagram.get_shapes() if shape.shape_type == "rectangle"]
        assert {shape.label for shape in shapes} == {"Client", "Server"}
        connections = diagram.get_connections()
        assert len(connections) == 1
        assert connections[0].from_id == "rectClient"
        assert connections[0].to_id == "rectServer"

    def test_cli_plain_auto_detect(self, capsys):
        result = main(["-i", str(PLAIN_FIXTURE), "-f", "mermaid", "--mermaid-type", "flowchart"])

        assert result == 0
        output = capsys.readouterr().out
        assert "rectClient" in output
        assert "rectClient --> rectServer" in output

    def test_cli_compressed_auto_detect(self, capsys):
        pytest.importorskip("lzstring")

        result = main(["-i", str(COMPRESSED_FIXTURE), "-f", "mermaid", "--mermaid-type", "flowchart"])

        assert result == 0
        assert "rectClient --> rectServer" in capsys.readouterr().out

    def test_cli_explicit_input_format(self, capsys):
        result = main(["-i", str(PLAIN_FIXTURE), "--input-format", "obsidian", "-f", "plantuml"])

        assert result == 0
        output = capsys.readouterr().out
        assert "@startuml" in output
        assert "Client" in output

    def test_cli_compressed_without_lzstring(self, monkeypatch, capsys):
        monkeypatch.setattr(obsidian_module, "_HAS_LZSTRING", False)

        result = main(["-i", str(COMPRESSED_FIXTURE), "-f", "mermaid"])

        assert result == 1
        assert "diacea[obsidian]" in capsys.readouterr().err
