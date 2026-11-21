"""Performance tests for diacea.

These tests verify that diacea can handle large diagrams without crashing
and that performance doesn't regress significantly. Run with:

    pytest tests/test_performance.py -v

To skip slow tests:
    pytest tests/test_performance.py -v -m "not slow"
"""

import time
from typing import Any

import pytest

from diacea.generators import (
    C4PlantUMLGenerator,
    D2Generator,
    GraphVizGenerator,
    MermaidGenerator,
    PlantUMLGenerator,
)
from diacea.parsers import ExcalidrawParser


def generate_excalidraw_diagram(num_shapes: int, num_connections: int) -> dict[str, Any]:
    """Generate a test Excalidraw diagram."""
    elements = []
    shapes = []

    for i in range(num_shapes):
        shape_id = f'shape_{i}'
        x = (i % 20) * 150.0
        y = (i // 20) * 100.0

        shape_type = ('rectangle', 'ellipse', 'diamond')[i % 3]
        element = {
            'id': shape_id,
            'type': shape_type,
            'x': x,
            'y': y,
            'width': 100.0,
            'height': 60.0,
            'strokeColor': '#000000',
            'backgroundColor': 'transparent',
        }
        elements.append(element)
        shapes.append(shape_id)

        text_element = {
            'id': f'text_{i}',
            'type': 'text',
            'x': x + 10,
            'y': y + 20,
            'width': 80.0,
            'height': 20.0,
            'text': f'Shape {i}',
        }
        elements.append(text_element)

    for i in range(min(num_connections, len(shapes) - 1)):
        from_idx = i
        to_idx = (i + 1) % len(shapes)

        arrow = {
            'id': f'arrow_{i}',
            'type': 'arrow',
            'x': 0.0,
            'y': 0.0,
            'points': [[0.0, 0.0], [100.0, 50.0]],
            'startBinding': {'elementId': shapes[from_idx]},
            'endBinding': {'elementId': shapes[to_idx]},
        }
        elements.append(arrow)

    return {'elements': elements, 'type': 'excalidraw'}


@pytest.mark.parametrize(('num_shapes', 'budget'), [(50, 1.0), pytest.param(1000, 5.0, marks=pytest.mark.slow)])
def test_parse_and_generate_every_text_format_within_budget(num_shapes, budget):
    data = generate_excalidraw_diagram(num_shapes, num_shapes * 4 // 5)

    start = time.perf_counter()
    diagram = ExcalidrawParser().parse(data)
    assert time.perf_counter() - start < budget

    assert len(diagram.get_shapes()) == num_shapes
    assert len(diagram.get_connections()) == num_shapes * 4 // 5
    for generator in (
        PlantUMLGenerator(),
        C4PlantUMLGenerator(),
        MermaidGenerator(),
        GraphVizGenerator(),
        D2Generator(),
    ):
        start = time.perf_counter()
        output = generator.generate(diagram)
        assert time.perf_counter() - start < budget, type(generator).__name__
        assert 'Shape 0' in output
        assert f'Shape {num_shapes - 1}' in output


class TestOutputSizeScaling:
    """Test that output size scales reasonably with input size."""

    def test_output_size_scaling(self):
        sizes = [10, 50, 100, 200]
        outputs: dict[int, int] = {}

        parser = ExcalidrawParser()
        gen = PlantUMLGenerator()

        for size in sizes:
            data = generate_excalidraw_diagram(size, size // 2)
            diagram = parser.parse(data)
            output = gen.generate(diagram)
            outputs[size] = len(output)

        assert outputs[50] > outputs[10]
        assert outputs[100] > outputs[50]
        assert outputs[200] > outputs[100]

        ratio_10_50 = outputs[50] / outputs[10]
        ratio_50_100 = outputs[100] / outputs[50]

        assert 2.0 <= ratio_10_50 <= 8.0
        assert 1.5 <= ratio_50_100 <= 4.0
