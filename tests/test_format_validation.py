"""Format validation tests.

These tests verify that generated output is syntactically valid for the target tools.
Tests are skipped if the required external tool is not installed.

Required tools for full validation:
- plantuml: `brew install plantuml` or download from https://plantuml.com/download
- mermaid-cli (mmdc): `npm install -g @mermaid-js/mermaid-cli`
- d2: `brew install d2` or download from https://d2lang.com/
- graphviz (dot): `brew install graphviz`

Run validation tests:
    pytest tests/test_format_validation.py -v

Skip if tools not installed:
    pytest tests/test_format_validation.py -v  # auto-skips unavailable tools
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from diacea.generators import (
    C4PlantUMLGenerator,
    D2Generator,
    GraphVizGenerator,
    MermaidGenerator,
    PlantUMLGenerator,
)
from diacea.ir import Diagram
from diacea.ir.elements import Connection, Dimensions, Point, Shape, Style

HAS_PLANTUML = shutil.which('plantuml') is not None
HAS_MERMAID = shutil.which('mmdc') is not None
HAS_D2 = shutil.which('d2') is not None
HAS_GRAPHVIZ = shutil.which('dot') is not None


def _make_test_diagram() -> Diagram:
    """Create a test diagram with shapes and connections."""
    shapes = [
        Shape(
            id='user',
            label='User',
            shape_type='ellipse',
            position=Point(x=0.0, y=0.0),
            size=Dimensions(width=100.0, height=60.0),
            style=Style(),
        ),
        Shape(
            id='api',
            label='API Service',
            shape_type='rectangle',
            position=Point(x=200.0, y=0.0),
            size=Dimensions(width=120.0, height=60.0),
            style=Style(),
        ),
        Shape(
            id='db',
            label='Database',
            shape_type='rectangle',
            position=Point(x=400.0, y=0.0),
            size=Dimensions(width=100.0, height=60.0),
            style=Style(),
        ),
    ]
    shapes[2].semantic_type = 'database'

    connections = [
        Connection(
            id='conn1',
            from_id='user',
            to_id='api',
            label='HTTP',
            connection_type='directed',
            position=Point(x=150.0, y=30.0),
            size=Dimensions(width=50.0, height=0.0),
            style=Style(),
        ),
        Connection(
            id='conn2',
            from_id='api',
            to_id='db',
            label='SQL',
            connection_type='directed',
            position=Point(x=350.0, y=30.0),
            size=Dimensions(width=50.0, height=0.0),
            style=Style(),
        ),
    ]

    return Diagram(id='test', name='Test Diagram', elements=[*shapes, *connections])


@pytest.mark.skipif(not HAS_PLANTUML, reason='plantuml not installed')
class TestPlantUMLValidation:
    """Validate PlantUML output with plantuml tool."""

    def test_plantuml_syntax_valid(self, tmp_path):
        diagram = _make_test_diagram()
        gen = PlantUMLGenerator()
        output = gen.generate(diagram)

        puml_file = tmp_path / 'test.puml'
        puml_file.write_text(output)

        result = subprocess.run(
            ['plantuml', '-checkonly', str(puml_file)],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f'PlantUML syntax error:\n{result.stdout}\n{result.stderr}'

    def test_c4plantuml_syntax_valid(self, tmp_path):
        diagram = _make_test_diagram()
        gen = C4PlantUMLGenerator()
        output = gen.generate(diagram)

        puml_file = tmp_path / 'test.puml'
        puml_file.write_text(output)

        result = subprocess.run(
            ['plantuml', '-checkonly', str(puml_file)],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f'C4 PlantUML syntax error:\n{result.stdout}\n{result.stderr}'


@pytest.mark.skipif(not HAS_MERMAID, reason='mermaid-cli (mmdc) not installed')
class TestMermaidValidation:
    """Validate Mermaid output with mermaid-cli tool."""

    def test_mermaid_flowchart_syntax_valid(self, tmp_path):
        diagram = _make_test_diagram()
        gen = MermaidGenerator(diagram_type='flowchart')
        output = gen.generate(diagram)

        mmd_file = tmp_path / 'test.mmd'
        mmd_file.write_text(output)
        svg_file = tmp_path / 'test.svg'

        result = subprocess.run(
            ['mmdc', '-i', str(mmd_file), '-o', str(svg_file)],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f'Mermaid syntax error:\n{result.stderr}'
        assert svg_file.exists()

    def test_mermaid_c4_syntax_valid(self, tmp_path):
        diagram = _make_test_diagram()
        diagram.elements[0].semantic_type = 'person'
        diagram.elements[1].semantic_type = 'container'
        diagram.elements[2].semantic_type = 'container'
        gen = MermaidGenerator(diagram_type='c4')
        output = gen.generate(diagram)

        mmd_file = tmp_path / 'test.mmd'
        mmd_file.write_text(output)
        svg_file = tmp_path / 'test.svg'

        result = subprocess.run(
            ['mmdc', '-i', str(mmd_file), '-o', str(svg_file)],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f'Mermaid C4 syntax error:\n{result.stderr}'


@pytest.mark.skipif(not HAS_D2, reason='d2 not installed')
class TestD2Validation:
    """Validate D2 output with d2 tool."""

    def test_d2_syntax_valid(self, tmp_path):
        diagram = _make_test_diagram()
        gen = D2Generator()
        output = gen.generate(diagram)

        d2_file = tmp_path / 'test.d2'
        d2_file.write_text(output)
        svg_file = tmp_path / 'test.svg'

        result = subprocess.run(
            ['d2', str(d2_file), str(svg_file)],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f'D2 syntax error:\n{result.stderr}'
        assert svg_file.exists()


@pytest.mark.skipif(not HAS_GRAPHVIZ, reason='graphviz (dot) not installed')
class TestGraphVizValidation:
    """Validate GraphViz output with dot tool."""

    def test_graphviz_syntax_valid(self, tmp_path):
        diagram = _make_test_diagram()
        gen = GraphVizGenerator()
        output = gen.generate(diagram)

        dot_file = tmp_path / 'test.dot'
        dot_file.write_text(output)
        svg_file = tmp_path / 'test.svg'

        result = subprocess.run(
            ['dot', '-Tsvg', str(dot_file), '-o', str(svg_file)],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f'GraphViz syntax error:\n{result.stderr}'
        assert svg_file.exists()

    def test_graphviz_undirected_valid(self, tmp_path):
        from diacea.generators import GraphVizConfig

        diagram = _make_test_diagram()
        gen = GraphVizGenerator(config=GraphVizConfig(graph_type='graph'))
        output = gen.generate(diagram)

        dot_file = tmp_path / 'test.dot'
        dot_file.write_text(output)
        svg_file = tmp_path / 'test.svg'

        result = subprocess.run(
            ['dot', '-Tsvg', str(dot_file), '-o', str(svg_file)],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f'GraphViz syntax error:\n{result.stderr}'


class TestToolAvailability:
    """Report which validation tools are available."""

    def test_report_tool_availability(self, capsys):
        tools = {
            'plantuml': HAS_PLANTUML,
            'mermaid-cli (mmdc)': HAS_MERMAID,
            'd2': HAS_D2,
            'graphviz (dot)': HAS_GRAPHVIZ,
        }

        available = [t for t, v in tools.items() if v]
        missing = [t for t, v in tools.items() if not v]

        print('\n--- Format Validation Tools ---')
        print(f'Available: {", ".join(available) if available else "none"}')
        print(f'Missing: {", ".join(missing) if missing else "none"}')

        if missing:
            print('\nTo install missing tools:')
            if 'plantuml' in missing:
                print('  plantuml: brew install plantuml')
            if 'mermaid-cli (mmdc)' in missing:
                print('  mmdc: npm install -g @mermaid-js/mermaid-cli')
            if 'd2' in missing:
                print('  d2: brew install d2')
            if 'graphviz (dot)' in missing:
                print('  dot: brew install graphviz')
