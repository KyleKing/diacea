"""Tests for PlantUML generation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from diacea.experiments import graph_based_approach
from diacea.plantuml import _sanitize_id, generate_plantuml


def test_sanitize_id():
    """Test ID sanitization for PlantUML."""
    assert _sanitize_id('R3tckAe0ed5CKf6cwsUAo') == 'Element_R3tckAe0'
    assert _sanitize_id('short') == 'Element_short'
    assert _sanitize_id('12345678') == 'Element_12345678'
    assert _sanitize_id('123456789') == 'Element_12345678'


def test_generate_plantuml_simple():
    """Test basic PlantUML generation with simple data."""
    relative_data = [
        {'id': 'rect1', 'type': 'rectangle', 'label': 'Box A', 'parent': ''},
        {'id': 'rect2', 'type': 'rectangle', 'label': 'Box B', 'parent': ''},
        {'id': 'arrow1', 'type': 'arrow', 'label': 'connects', 'from': 'rect1', 'to': 'rect2'},
    ]

    result = generate_plantuml(relative_data)

    # Verify structure
    assert result.startswith('@startuml')
    assert result.endswith('@enduml')

    # Verify components
    assert 'component "Box A" as Element_rect1' in result
    assert 'component "Box B" as Element_rect2' in result

    # Verify relationship
    assert 'Element_rect1 --> Element_rect2 : connects' in result


def test_generate_plantuml_no_labels():
    """Test PlantUML generation without arrow labels."""
    relative_data = [
        {'id': 'rect1', 'type': 'rectangle', 'label': 'Box A', 'parent': ''},
        {'id': 'rect2', 'type': 'rectangle', 'label': 'Box B', 'parent': ''},
        {'id': 'arrow1', 'type': 'arrow', 'label': '', 'from': 'rect1', 'to': 'rect2'},
    ]

    result = generate_plantuml(relative_data)

    # Verify relationship without label
    assert 'Element_rect1 --> Element_rect2' in result
    # Should not have a colon for empty labels
    assert 'Element_rect1 --> Element_rect2 :' not in result


def test_generate_plantuml_with_parent():
    """Test PlantUML generation with nested rectangles."""
    relative_data = [
        {'id': 'parent1', 'type': 'rectangle', 'label': 'Parent', 'parent': ''},
        {'id': 'child1', 'type': 'rectangle', 'label': 'Child', 'parent': 'parent1'},
    ]

    result = generate_plantuml(relative_data)

    # Both should be defined as components
    assert 'component "Parent" as Element_parent1' in result
    assert 'component "Child" as Element_child1' in result


def test_generate_plantuml_empty():
    """Test PlantUML generation with empty data."""
    result = generate_plantuml([])

    assert result == '@startuml\n\n\n@enduml'


def test_generate_plantuml_only_rectangles():
    """Test PlantUML generation with only rectangles, no arrows."""
    relative_data = [
        {'id': 'rect1', 'type': 'rectangle', 'label': 'Box A', 'parent': ''},
        {'id': 'rect2', 'type': 'rectangle', 'label': 'Box B', 'parent': ''},
    ]

    result = generate_plantuml(relative_data)

    assert 'component "Box A" as Element_rect1' in result
    assert 'component "Box B" as Element_rect2' in result
    assert '-->' not in result


def test_generate_plantuml_with_test_data(tmp_path: Path):
    """Test PlantUML generation with actual test data."""
    # Load test data
    test_data_path = Path(__file__).parent / 'data' / 'excalidraw.json'
    with test_data_path.open() as f:
        data = json.load(f)

    # Convert using graph-based approach
    elements = data['elements']
    relative = graph_based_approach(elements)

    # Generate PlantUML
    plantuml = generate_plantuml(relative)

    # Verify basic structure
    assert plantuml.startswith('@startuml')
    assert plantuml.endswith('@enduml')

    # Verify it's not empty
    lines = plantuml.split('\n')
    assert len(lines) > 4  # More than just start/end tags

    # Verify it contains components or relationships
    assert 'component' in plantuml or 'rectangle' in plantuml

    # Save output for manual inspection
    output_path = tmp_path / 'test_output.puml'
    output_path.write_text(plantuml)


def test_generate_plantuml_multiple_arrows():
    """Test PlantUML generation with multiple arrows."""
    relative_data = [
        {'id': 'rect1', 'type': 'rectangle', 'label': 'A', 'parent': ''},
        {'id': 'rect2', 'type': 'rectangle', 'label': 'B', 'parent': ''},
        {'id': 'rect3', 'type': 'rectangle', 'label': 'C', 'parent': ''},
        {'id': 'arrow1', 'type': 'arrow', 'label': 'to B', 'from': 'rect1', 'to': 'rect2'},
        {'id': 'arrow2', 'type': 'arrow', 'label': 'to C', 'from': 'rect2', 'to': 'rect3'},
    ]

    result = generate_plantuml(relative_data)

    assert 'Element_rect1 --> Element_rect2 : to B' in result
    assert 'Element_rect2 --> Element_rect3 : to C' in result
