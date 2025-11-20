"""Tests for CLI interface."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from diacea.cli import main


def test_cli_help(capsys):
    """Test CLI help message."""
    with pytest.raises(SystemExit) as exc_info:
        main(['--help'])

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert 'Convert Excalidraw diagrams to PlantUML' in captured.out
    assert '--input' in captured.out
    assert '--output' in captured.out
    assert '--algorithm' in captured.out


def test_cli_version(capsys):
    """Test CLI version flag."""
    with pytest.raises(SystemExit) as exc_info:
        main(['--version'])

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert 'diacea' in captured.out
    assert '0.0.1' in captured.out


def test_cli_missing_input(capsys):
    """Test CLI with missing input argument."""
    with pytest.raises(SystemExit) as exc_info:
        main([])

    assert exc_info.value.code != 0
    captured = capsys.readouterr()
    assert 'required' in captured.err.lower() or 'required' in captured.out.lower()


def test_cli_file_not_found(capsys):
    """Test CLI with non-existent input file."""
    result = main(['-i', 'nonexistent.json'])

    assert result == 1
    captured = capsys.readouterr()
    assert 'not found' in captured.err.lower()


def test_cli_invalid_json(tmp_path: Path, capsys):
    """Test CLI with invalid JSON file."""
    invalid_file = tmp_path / 'invalid.json'
    invalid_file.write_text('not valid json {')

    result = main(['-i', str(invalid_file)])

    assert result == 1
    captured = capsys.readouterr()
    assert 'invalid json' in captured.err.lower()


def test_cli_no_elements(tmp_path: Path, capsys):
    """Test CLI with JSON file without elements key."""
    no_elements_file = tmp_path / 'no_elements.json'
    no_elements_file.write_text('{"other": "data"}')

    result = main(['-i', str(no_elements_file)])

    assert result == 1
    captured = capsys.readouterr()
    assert 'elements' in captured.err.lower()


def test_cli_basic_conversion(tmp_path: Path, capsys):
    """Test basic CLI conversion."""
    # Create test input file
    input_file = tmp_path / 'test_input.json'
    test_data = {
        'elements': [
            {
                'id': 'rect1',
                'type': 'rectangle',
                'x': 0,
                'y': 0,
                'width': 100,
                'height': 100,
            },
            {
                'id': 'text1',
                'type': 'text',
                'x': 10,
                'y': 10,
                'text': 'Box A',
            },
        ],
    }
    input_file.write_text(json.dumps(test_data))

    # Run CLI
    output_file = tmp_path / 'test_output.puml'
    result = main(['-i', str(input_file), '-o', str(output_file)])

    # Verify success
    assert result == 0
    captured = capsys.readouterr()
    assert 'successfully' in captured.out.lower()

    # Verify output file exists and has content
    assert output_file.exists()
    content = output_file.read_text()
    assert '@startuml' in content
    assert '@enduml' in content


def test_cli_default_output_path(tmp_path: Path, capsys):
    """Test CLI with default output path."""
    # Create test input file
    input_file = tmp_path / 'diagram.json'
    test_data = {
        'elements': [
            {
                'id': 'rect1',
                'type': 'rectangle',
                'x': 0,
                'y': 0,
                'width': 100,
                'height': 100,
            },
        ],
    }
    input_file.write_text(json.dumps(test_data))

    # Run CLI without output argument
    result = main(['-i', str(input_file)])

    # Verify success
    assert result == 0

    # Verify default output file exists
    default_output = tmp_path / 'diagram.puml'
    assert default_output.exists()
    content = default_output.read_text()
    assert '@startuml' in content
    assert '@enduml' in content


def test_cli_algorithm_selection(tmp_path: Path, capsys):
    """Test CLI with different algorithm selection."""
    # Create test input file
    input_file = tmp_path / 'test_input.json'
    test_data = {
        'elements': [
            {
                'id': 'rect1',
                'type': 'rectangle',
                'x': 0,
                'y': 0,
                'width': 100,
                'height': 100,
            },
        ],
    }
    input_file.write_text(json.dumps(test_data))

    # Test with different algorithm
    output_file = tmp_path / 'test_output.puml'
    result = main([
        '-i',
        str(input_file),
        '-o',
        str(output_file),
        '-a',
        'convert_to_relative',
    ])

    # Verify success
    assert result == 0
    assert output_file.exists()


def test_cli_with_real_test_data(tmp_path: Path, capsys):
    """Test CLI with actual test data from the project."""
    test_data_path = Path(__file__).parent / 'data' / 'excalidraw.json'
    output_file = tmp_path / 'output.puml'

    result = main(['-i', str(test_data_path), '-o', str(output_file)])

    # Verify success
    assert result == 0
    captured = capsys.readouterr()
    assert 'successfully' in captured.out.lower()

    # Verify output file
    assert output_file.exists()
    content = output_file.read_text()
    assert '@startuml' in content
    assert '@enduml' in content
    # Default format is C4, so check for C4 elements
    assert 'System_Boundary' in content or 'Container' in content or 'component' in content
