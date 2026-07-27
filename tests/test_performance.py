"""Performance tests for diacea.

These tests verify that diacea can handle large diagrams without crashing
and that performance doesn't regress significantly. Run with:

    pytest tests/test_performance.py -v

To skip slow tests:
    pytest tests/test_performance.py -v -m "not slow"
"""

import random
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

        shape_type = random.choice(['rectangle', 'ellipse', 'diamond'])
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


class TestSmallDiagramPerformance:
    """Test performance with small diagrams (should be fast)."""

    def test_parse_50_shapes(self):
        data = generate_excalidraw_diagram(50, 30)
        parser = ExcalidrawParser()

        start = time.perf_counter()
        diagram = parser.parse(data)
        elapsed = time.perf_counter() - start

        assert len(diagram.get_shapes()) >= 50
        assert elapsed < 0.5

    def test_generate_50_shapes_all_formats(self):
        data = generate_excalidraw_diagram(50, 30)
        parser = ExcalidrawParser()
        diagram = parser.parse(data)

        generators = [
            PlantUMLGenerator(),
            C4PlantUMLGenerator(),
            MermaidGenerator(),
            GraphVizGenerator(),
            D2Generator(),
        ]

        for gen in generators:
            start = time.perf_counter()
            output = gen.generate(diagram)
            elapsed = time.perf_counter() - start

            assert len(output) > 0
            assert elapsed < 0.5


class TestMediumDiagramPerformance:
    """Test performance with medium diagrams."""

    def test_parse_500_shapes(self):
        data = generate_excalidraw_diagram(500, 400)
        parser = ExcalidrawParser()

        start = time.perf_counter()
        diagram = parser.parse(data)
        elapsed = time.perf_counter() - start

        assert len(diagram.get_shapes()) >= 500
        assert elapsed < 2.0

    def test_generate_500_shapes_all_formats(self):
        data = generate_excalidraw_diagram(500, 400)
        parser = ExcalidrawParser()
        diagram = parser.parse(data)

        generators = [
            ('plantuml', PlantUMLGenerator()),
            ('c4', C4PlantUMLGenerator()),
            ('mermaid', MermaidGenerator()),
            ('graphviz', GraphVizGenerator()),
            ('d2', D2Generator()),
        ]

        for name, gen in generators:
            start = time.perf_counter()
            output = gen.generate(diagram)
            elapsed = time.perf_counter() - start

            assert len(output) > 0, f'{name} produced empty output'
            assert elapsed < 2.0, f'{name} took too long: {elapsed:.2f}s'


@pytest.mark.slow
class TestLargeDiagramPerformance:
    """Test performance with large diagrams (1000+ shapes)."""

    def test_parse_1000_shapes(self):
        data = generate_excalidraw_diagram(1000, 800)
        parser = ExcalidrawParser()

        start = time.perf_counter()
        diagram = parser.parse(data)
        elapsed = time.perf_counter() - start

        assert len(diagram.get_shapes()) >= 1000
        assert elapsed < 5.0

    def test_generate_1000_shapes_all_formats(self):
        data = generate_excalidraw_diagram(1000, 800)
        parser = ExcalidrawParser()
        diagram = parser.parse(data)

        generators = [
            ('plantuml', PlantUMLGenerator()),
            ('c4', C4PlantUMLGenerator()),
            ('mermaid', MermaidGenerator()),
            ('graphviz', GraphVizGenerator()),
            ('d2', D2Generator()),
        ]

        for name, gen in generators:
            start = time.perf_counter()
            output = gen.generate(diagram)
            elapsed = time.perf_counter() - start

            assert len(output) > 0, f'{name} produced empty output'
            assert elapsed < 5.0, f'{name} took too long: {elapsed:.2f}s'


@pytest.mark.slow
class TestVeryLargeDiagramPerformance:
    """Test performance with very large diagrams (2000+ shapes)."""

    def test_parse_2000_shapes(self):
        data = generate_excalidraw_diagram(2000, 1500)
        parser = ExcalidrawParser()

        start = time.perf_counter()
        diagram = parser.parse(data)
        elapsed = time.perf_counter() - start

        assert len(diagram.get_shapes()) >= 2000
        assert elapsed < 10.0

    def test_generate_2000_shapes_mermaid(self):
        """Mermaid is often the slowest generator."""
        data = generate_excalidraw_diagram(2000, 1500)
        parser = ExcalidrawParser()
        diagram = parser.parse(data)

        gen = MermaidGenerator()

        start = time.perf_counter()
        output = gen.generate(diagram)
        elapsed = time.perf_counter() - start

        assert len(output) > 0
        assert elapsed < 10.0


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
