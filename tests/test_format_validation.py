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

import pytest

from diacea.formats import OUTPUT_FORMATS, render_diagram
from diacea.ir import Diagram, Group
from diacea.ir.elements import Connection, Dimensions, Point, Shape, Style


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
    shapes[0].semantic_type = 'person'
    shapes[1].semantic_type = 'container'
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


_AWKWARD_LABELS = [
    'a/b',
    '--',
    '1--Y',
    "User's (laptop)",
    'x: y; z',
    '[Queue]',
    '{decide?}',
    '<tag> & "quote"',
    'pipe | bar',
    '#hash @at $dollar',
    'back\\slash',
    '50% ~ ^caret',
    '`tick` = eq',
    '==> arrow',
    'end',
    'multi\nline',
]


def _make_awkward_label_diagram() -> Diagram:
    """A chain of nodes whose node, edge, and group labels hold the punctuation each format treats as syntax."""
    diagram = Diagram(id='awkward', metadata={'explicit_shapes': True})
    for index, label in enumerate(_AWKWARD_LABELS):
        diagram.add_element(
            Shape(id=f'n{index}', label=label, position=Point(x=index * 200.0, y=0.0), size=Dimensions(120.0, 60.0))
        )
    for index, label in enumerate(_AWKWARD_LABELS[:-1]):
        diagram.add_element(
            Connection(
                id=f'e{index}',
                from_id=f'n{index}',
                to_id=f'n{index + 1}',
                label=label,
                position=Point(x=0.0, y=0.0),
                size=Dimensions(1.0, 1.0),
            )
        )
    diagram.add_element(
        Group(
            id='group-g',
            label='Group: "a" & <b> / [c]',
            position=Point(x=0.0, y=0.0),
            size=Dimensions(1.0, 1.0),
            children=['n0', 'n1', 'n2'],
        )
    )
    return diagram


_AWKWARD_LABEL_CASES = [
    pytest.param('mermaid', {'mermaid_type': 'flowchart'}, 'mmdc', id='mermaid-flowchart'),
    pytest.param('mermaid', {'mermaid_type': 'c4'}, 'mmdc', id='mermaid-c4'),
    pytest.param('d2', {}, 'd2', id='d2'),
    pytest.param('graphviz', {}, 'dot', id='graphviz'),
    pytest.param('graphviz', {'graphviz_type': 'graph'}, 'dot', id='graphviz-undirected'),
    pytest.param('plantuml', {}, 'plantuml', id='plantuml'),
    pytest.param('c4', {}, 'plantuml', id='c4-plantuml'),
]


@pytest.mark.parametrize('make_diagram', [_make_awkward_label_diagram, _make_test_diagram])
@pytest.mark.parametrize(('output_format', 'options', 'tool'), _AWKWARD_LABEL_CASES)
def test_output_is_accepted_by_the_native_tool(output_format, options, tool, make_diagram, tmp_path):
    """Semantic macros, and labels full of each format's own syntax characters, must render in that format's tool."""
    if shutil.which(tool) is None:
        pytest.skip(f'{tool} not installed')
    source = tmp_path / f'awkward{OUTPUT_FORMATS[output_format].suffix}'
    source.write_text(render_diagram(make_diagram(), output_format, **options).output + '\n')
    commands = {
        'mmdc': ['mmdc', '-i', str(source), '-o', str(tmp_path / 'out.svg')],
        'd2': ['d2', str(source), str(tmp_path / 'out.svg')],
        'dot': ['dot', '-Tsvg', str(source), '-o', str(tmp_path / 'out.svg')],
        'plantuml': ['plantuml', '-tsvg', str(source)],
    }

    result = subprocess.run(commands[tool], capture_output=True, text=True, timeout=180)

    assert result.returncode == 0, f'{tool} rejected the output:\n{result.stdout}\n{result.stderr}'
