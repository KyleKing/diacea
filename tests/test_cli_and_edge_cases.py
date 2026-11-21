"""CLI integration tests and edge case tests."""

import json
from io import StringIO

import pytest

from diacea.cli import main
from diacea.formats import render_diagram
from diacea.generators import (
    C4PlantUMLGenerator,
    MermaidGenerator,
    PlantUMLGenerator,
)
from diacea.ir import Diagram
from diacea.ir.elements import Connection, Dimensions, Element, Group, Point, Shape, Style
from diacea.ir.semantic import SemanticType
from diacea.parsers import ExcalidrawParser


class TestCLIBasics:
    """Test CLI basic functionality."""

    def test_cli_help(self, capsys):
        with pytest.raises(SystemExit) as exit_:
            main(['--help'])

        assert exit_.value.code == 0
        assert 'Universal diagram converter' in capsys.readouterr().out

    @pytest.mark.parametrize(
        ('name', 'content', 'extra', 'error'),
        [
            ('nonexistent.json', None, [], 'Input file not found: nonexistent.json'),
            (
                'bad.json',
                'not valid json',
                ['-v'],
                (
                    'Could not detect input format (supported: d2, excalidraw, graphviz, mermaid, obsidian, '
                    'plantuml, svg, tldraw); if the file is valid, name its format with --input-format '
                    '(or input_format= in Python)'
                ),
            ),
            (
                'unknown.json',
                '{"not": "excalidraw"}',
                [],
                'Unrecognized input format: JSON is neither an Excalidraw scene nor a TLDraw document',
            ),
        ],
    )
    def test_cli_input_errors(self, name, content, extra, error, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        if content is not None:
            (tmp_path / name).write_text(content)

        assert main(['-i', name, '-f', 'mermaid', *extra]) == 1
        assert capsys.readouterr() == ('', f'Error: {error}\n')


_SIMPLE_SCENE = {
    'elements': [
        {'id': 'a', 'type': 'rectangle', 'x': 0.0, 'y': 0.0, 'width': 100.0, 'height': 50.0},
        {'id': 'b', 'type': 'rectangle', 'x': 200.0, 'y': 0.0, 'width': 100.0, 'height': 50.0},
        {
            'id': 'arr',
            'type': 'arrow',
            'x': 100.0,
            'y': 25.0,
            'points': [[0.0, 0.0], [100.0, 0.0]],
            'startBinding': {'elementId': 'a'},
            'endBinding': {'elementId': 'b'},
        },
    ]
}
_CLI_INPUTS = {
    'simple.json': json.dumps(_SIMPLE_SCENE),
    'box.svg': '<?xml version="1.0"?>\n<svg xmlns="http://www.w3.org/2000/svg" width="200" height="100">'
    '<rect x="10" y="10" width="80" height="40" fill="blue"/></svg>',
    'legacy.json': json.dumps(
        {
            'document': {
                'pages': {
                    'page1': {
                        'id': 'page1',
                        'name': 'Test Page',
                        'shapes': {
                            'shape1': {'id': 'shape1', 'type': 'rectangle', 'point': [0.0, 0.0], 'size': [100.0, 50.0]}
                        },
                        'bindings': {},
                    }
                }
            }
        }
    ),
}
_DOT_AB = (
    '"diagram" {{\n    rankdir="{rankdir}";\n    node [shape="box", fontname="Helvetica"];\n'
    '    edge [fontname="Helvetica"];\n\n    a [label="a"];\n    b [label="b"];\n\n    a {arrow} b;\n}}\n'
)
_C4_AB = 'C4Context\n    title Architecture Diagram\n    Component(a, "a")\n    Component(b, "b")\n    Rel(a, b, " ")\n'


@pytest.mark.parametrize(
    ('argv', 'expected'),
    [
        (['simple.json', '-f', 'plantuml'], '@startuml\nrectangle "a" as a\nrectangle "b" as b\na --> b\n@enduml\n'),
        (
            ['simple.json', '-f', 'c4'],
            (
                '@startuml\n!include https://raw.githubusercontent.com/plantuml-stdlib/C4-PlantUML/master/C4_Component.puml'
                '\n\nLAYOUT_WITH_LEGEND()\n\nComponent(a, "a")\nComponent(b, "b")\n\n\nRel(a, b, "")\n@enduml\n'
            ),
        ),
        (['simple.json', '-f', 'mermaid'], _C4_AB),
        (['simple.json', '-f', 'mermaid', '--mermaid-type', 'c4'], _C4_AB),
        (
            ['simple.json', '-f', 'mermaid', '--mermaid-type', 'flowchart'],
            'flowchart LR\n    a[a]\n    b[b]\n    a --> b\n',
        ),
        (['simple.json', '-f', 'graphviz'], 'digraph ' + _DOT_AB.format(rankdir='LR', arrow='->')),
        (
            ['simple.json', '-f', 'graphviz', '--graphviz-direction', 'TB'],
            'digraph ' + _DOT_AB.format(rankdir='TB', arrow='->'),
        ),
        (
            ['simple.json', '-f', 'graphviz', '--graphviz-type', 'graph'],
            'graph ' + _DOT_AB.format(rankdir='LR', arrow='--'),
        ),
        (['simple.json', '-f', 'd2'], 'direction: right\n\na: a\nb: b\n\na -> b\n'),
        (['simple.json', '-f', 'd2', '--d2-direction', 'up'], 'direction: up\n\na: a\nb: b\n\na -> b\n'),
        (['simple.json', '-f', 'd2', '--d2-sketch', '-o', '-'], 'direction: right\n\na: a\nb: b\n\na -> b\n'),
        (
            ['-i', 'box.svg', '--input-format', 'svg', '-f', 'plantuml'],
            '@startuml\nrectangle "elem_1" as elem_1\n@enduml\n',
        ),
        (
            ['legacy.json', '--input-format', 'tldraw', '-f', 'd2'],
            'direction: right\n\nshape1: shape1 {\n  style: {\n    stroke: "#1d1d1d"\n    stroke-width: 3\n  }\n}\n',
        ),
        (
            ['box.svg', '-f', 'graphviz'],
            (
                'digraph "SVG Diagram" {\n    rankdir="LR";\n    node [shape="box", fontname="Helvetica"];\n'
                '    edge [fontname="Helvetica"];\n\n'
                '    elem_1 [label="elem_1", fillcolor="blue", style="filled"];\n\n}\n'
            ),
        ),
    ],
)
def test_cli_converts_to_stdout(argv, expected, tmp_path, monkeypatch, capsys):
    for name, content in _CLI_INPUTS.items():
        (tmp_path / name).write_text(content)
    monkeypatch.chdir(tmp_path)

    assert main(argv) == 0
    assert capsys.readouterr().out == expected


def test_cli_reads_stdin_and_writes_into_new_directories(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr('sys.stdin', StringIO(json.dumps(_SIMPLE_SCENE)))
    target = tmp_path / 'nested' / 'dir' / 'output.puml'

    assert main(['-i', '-', '-f', 'plantuml', '-o', str(target)]) == 0
    assert target.read_text() == '@startuml\nrectangle "a" as a\nrectangle "b" as b\na --> b\n@enduml'


def _escaping_diagram() -> Diagram:
    def shape(shape_id, label):
        return Shape(
            id=shape_id, label=label, shape_type='rectangle', position=Point(0.0, 0.0), size=Dimensions(100.0, 50.0)
        )

    connection = Connection(
        id='c', from_id='q', to_id='n', label='A | B & C', position=Point(0.0, 0.0), size=Dimensions(0.0, 0.0)
    )
    return Diagram(id='t', elements=[shape('q', 'Hello "World" & <Test>'), shape('n', 'Line1\nLine2'), connection])


@pytest.mark.parametrize(
    ('output_format', 'options', 'expected'),
    [
        (
            'plantuml',
            {},
            (
                '@startuml\nrectangle "Hello \\"World\\" &amp; ~<Test~>" as q\nrectangle "Line1\\nLine2" as n\n'
                'q --> n : "A | B &amp; C"\n@enduml'
            ),
        ),
        (
            'c4',
            {},
            (
                '@startuml\n!include https://raw.githubusercontent.com/plantuml-stdlib/C4-PlantUML/master/C4_Component.puml'
                '\n\nLAYOUT_WITH_LEGEND()\n\nContainer(q, "Hello <U+0022>World<U+0022> &amp; ~<Test~>")\n'
                'Container(n, "Line1\\nLine2")\n\n\nRel(q, n, "A | B &amp; C")\n@enduml'
            ),
        ),
        (
            'mermaid',
            {'mermaid_type': 'flowchart'},
            (
                'flowchart LR\n    q["Hello #quot;World#quot; &amp; &lt;Test&gt;"]\n    n[Line1<br/>Line2]\n'
                '    q -->|"A &#124; B &amp; C"| n'
            ),
        ),
        (
            'mermaid',
            {'mermaid_type': 'c4'},
            (
                'C4Context\n    title Architecture Diagram\n'
                '    System(q, "Hello #quot;World#quot; &amp; &lt;Test&gt;")\n'
                '    System(n, "Line1<br/>Line2")\n    Rel(q, n, "A | B &amp; C")'
            ),
        ),
        (
            'graphviz',
            {},
            (
                'digraph "diagram" {\n    rankdir="LR";\n    node [shape="box", fontname="Helvetica"];\n'
                '    edge [fontname="Helvetica"];\n\n    q [label="Hello \\"World\\" & <Test>"];\n'
                '    n [label="Line1\\nLine2"];\n\n    q -> n [label="A | B & C"];\n}'
            ),
        ),
        (
            'd2',
            {},
            'direction: right\n\nq: "Hello \\"World\\" & <Test>"\nn: Line1\\nLine2\n\nq -> n: "A | B & C"',
        ),
    ],
)
def test_labels_are_escaped_for_each_format(output_format, options, expected):
    assert render_diagram(_escaping_diagram(), output_format, **options).output == expected


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_diagram(self):
        diagram = Diagram(id='empty', elements=[])
        gen = PlantUMLGenerator()
        output = gen.generate(diagram)
        assert '@startuml' in output
        assert '@enduml' in output

    def test_single_shape_no_connections(self):
        shape = Shape(
            id='alone',
            label='Alone',
            shape_type='rectangle',
            position=Point(x=0.0, y=0.0),
            size=Dimensions(width=100.0, height=50.0),
            style=Style(),
        )
        diagram = Diagram(id='test', elements=[shape])
        gen = PlantUMLGenerator()
        output = gen.generate(diagram)
        assert 'Alone' in output
        assert '-->' not in output

    def test_connection_without_label(self):
        shape1 = Shape(
            id='a',
            label='A',
            shape_type='rectangle',
            position=Point(x=0.0, y=0.0),
            size=Dimensions(width=100.0, height=50.0),
            style=Style(),
        )
        shape2 = Shape(
            id='b',
            label='B',
            shape_type='rectangle',
            position=Point(x=200.0, y=0.0),
            size=Dimensions(width=100.0, height=50.0),
            style=Style(),
        )
        conn = Connection(
            id='conn',
            from_id='a',
            to_id='b',
            label='',
            connection_type='directed',
            position=Point(x=100.0, y=25.0),
            size=Dimensions(width=100.0, height=0.0),
            style=Style(),
        )
        diagram = Diagram(id='test', elements=[shape1, shape2, conn])
        gen = PlantUMLGenerator()
        output = gen.generate(diagram)
        assert 'a --> b' in output

    def test_shape_without_label(self):
        shape = Shape(
            id='nolabel',
            label='',
            shape_type='rectangle',
            position=Point(x=0.0, y=0.0),
            size=Dimensions(width=100.0, height=50.0),
            style=Style(),
        )
        diagram = Diagram(id='test', elements=[shape])
        gen = PlantUMLGenerator()
        output = gen.generate(diagram)
        assert 'nolabel' in output

    def test_very_long_label(self):
        long_label = 'A' * 1000
        shape = Shape(
            id='long',
            label=long_label,
            shape_type='rectangle',
            position=Point(x=0.0, y=0.0),
            size=Dimensions(width=100.0, height=50.0),
            style=Style(),
        )
        diagram = Diagram(id='test', elements=[shape])
        gen = PlantUMLGenerator()
        output = gen.generate(diagram)
        assert long_label in output

    def test_special_id_characters(self):
        shape = Shape(
            id='special-id:with.chars',
            label='Test',
            shape_type='rectangle',
            position=Point(x=0.0, y=0.0),
            size=Dimensions(width=100.0, height=50.0),
            style=Style(),
        )
        diagram = Diagram(id='test', elements=[shape])
        gen = PlantUMLGenerator()
        output = gen.generate(diagram)
        assert 'special_id_with_chars' in output

    def test_bidirectional_connection(self):
        shape1 = Shape(
            id='a',
            label='A',
            shape_type='rectangle',
            position=Point(x=0.0, y=0.0),
            size=Dimensions(width=100.0, height=50.0),
            style=Style(),
        )
        shape2 = Shape(
            id='b',
            label='B',
            shape_type='rectangle',
            position=Point(x=200.0, y=0.0),
            size=Dimensions(width=100.0, height=50.0),
            style=Style(),
        )
        conn = Connection(
            id='conn',
            from_id='a',
            to_id='b',
            label='bidirectional',
            connection_type='bidirectional',
            position=Point(x=100.0, y=25.0),
            size=Dimensions(width=100.0, height=0.0),
            style=Style(),
        )
        diagram = Diagram(id='test', elements=[shape1, shape2, conn])

        plantuml = PlantUMLGenerator().generate(diagram)
        assert '<-->' in plantuml

        mermaid = MermaidGenerator(diagram_type='flowchart').generate(diagram)
        assert '<-->' in mermaid

    def test_connections_only_diagram(self):
        conn = Connection(
            id='conn',
            from_id='a',
            to_id='b',
            label='link',
            connection_type='directed',
            position=Point(x=100.0, y=25.0),
            size=Dimensions(width=100.0, height=0.0),
            style=Style(),
        )
        diagram = Diagram(id='test', elements=[conn])

        plantuml = PlantUMLGenerator().generate(diagram)
        assert '@startuml' in plantuml
        assert '@enduml' in plantuml
        assert 'a --> b' in plantuml

        mermaid = MermaidGenerator(diagram_type='flowchart').generate(diagram)
        assert 'flowchart' in mermaid
        assert 'a -->' in mermaid

    def test_deeply_nested_groups(self):
        from diacea.ir.elements import Group

        innermost = Shape(
            id='inner',
            label='Inner',
            shape_type='rectangle',
            position=Point(x=50.0, y=50.0),
            size=Dimensions(width=50.0, height=30.0),
            style=Style(),
        )
        level2 = Group(
            id='level2',
            label='Level 2',
            position=Point(x=30.0, y=30.0),
            size=Dimensions(width=100.0, height=80.0),
            style=Style(),
            children=['inner'],
        )
        level1 = Group(
            id='level1',
            label='Level 1',
            position=Point(x=10.0, y=10.0),
            size=Dimensions(width=150.0, height=120.0),
            style=Style(),
            children=['level2'],
        )
        outer = Group(
            id='outer',
            label='Outer',
            position=Point(x=0.0, y=0.0),
            size=Dimensions(width=200.0, height=160.0),
            style=Style(),
            children=['level1'],
        )
        diagram = Diagram(id='test', elements=[innermost, level2, level1, outer])

        plantuml = PlantUMLGenerator().generate(diagram)
        assert '@startuml' in plantuml
        assert '@enduml' in plantuml
        assert plantuml.index('rectangle "Outer" as outer {') < plantuml.index('rectangle "Level 1" as level1 {')
        assert plantuml.index('rectangle "Level 1" as level1 {') < plantuml.index('rectangle "Level 2" as level2 {')
        assert plantuml.index('rectangle "Level 2" as level2 {') < plantuml.index('rectangle "Inner" as inner')
        assert plantuml.count('rectangle') == 4

        mermaid = MermaidGenerator(diagram_type='flowchart').generate(diagram)
        assert 'flowchart' in mermaid
        assert mermaid.count('subgraph') == 3
        assert mermaid.index('subgraph outer[Outer]') < mermaid.index('subgraph level1[Level 1]')
        assert mermaid.index('subgraph level1[Level 1]') < mermaid.index('subgraph level2[Level 2]')
        assert mermaid.index('subgraph level2[Level 2]') < mermaid.index('inner[Inner]')
        assert mermaid.count('end') == 3

    def test_unicode_labels(self):
        shape = Shape(
            id='unicode',
            label='Hello \u4e16\u754c \u0420\u043e\u0441\u0441\u0438\u044f \ud83d\ude00',
            shape_type='rectangle',
            position=Point(x=0.0, y=0.0),
            size=Dimensions(width=100.0, height=50.0),
            style=Style(),
        )
        diagram = Diagram(id='test', elements=[shape])

        plantuml = PlantUMLGenerator().generate(diagram)
        assert '\u4e16\u754c' in plantuml

        mermaid = MermaidGenerator(diagram_type='flowchart').generate(diagram)
        assert '\u4e16\u754c' in mermaid


class TestDuplicateElementFix:
    """Test that shapes converted to groups don't appear twice."""

    def test_no_duplicate_container_shapes(self):
        data = {
            'elements': [
                {'id': 'outer', 'type': 'rectangle', 'x': 0.0, 'y': 0.0, 'width': 300.0, 'height': 200.0},
                {'id': 'inner', 'type': 'rectangle', 'x': 50.0, 'y': 50.0, 'width': 100.0, 'height': 50.0},
                {
                    'id': 'text',
                    'type': 'text',
                    'x': 10.0,
                    'y': 10.0,
                    'width': 50.0,
                    'height': 20.0,
                    'text': 'Container',
                },
            ]
        }
        parser = ExcalidrawParser()
        diagram = parser.parse(data)

        plantuml = PlantUMLGenerator().generate(diagram)
        assert plantuml.count('Container') == 1

        mermaid = MermaidGenerator(diagram_type='flowchart').generate(diagram)
        lines_with_container = [line for line in mermaid.split('\n') if 'Container' in line]
        assert len(lines_with_container) == 1

    def test_group_children_inside_group_only(self):
        data = {
            'elements': [
                {'id': 'outer', 'type': 'rectangle', 'x': 0.0, 'y': 0.0, 'width': 300.0, 'height': 200.0},
                {'id': 'inner1', 'type': 'rectangle', 'x': 20.0, 'y': 20.0, 'width': 80.0, 'height': 40.0},
                {'id': 'inner2', 'type': 'rectangle', 'x': 120.0, 'y': 20.0, 'width': 80.0, 'height': 40.0},
            ]
        }
        parser = ExcalidrawParser()
        diagram = parser.parse(data)

        plantuml = PlantUMLGenerator().generate(diagram)
        assert 'inner1' in plantuml
        assert 'inner2' in plantuml
        lines = plantuml.split('\n')
        inner1_declarations = [line for line in lines if 'rectangle' in line and 'inner1' in line]
        inner2_declarations = [line for line in lines if 'rectangle' in line and 'inner2' in line]
        assert len(inner1_declarations) == 1
        assert len(inner2_declarations) == 1


def _c4_shape(shape_id: str, label: str, semantic: str | None = None) -> Shape:
    return Shape(
        id=shape_id,
        label=label,
        shape_type='rectangle',
        position=Point(x=0.0, y=0.0),
        size=Dimensions(width=100.0, height=50.0),
        style=Style(),
        semantic_type=semantic,
    )


def _c4_connection(conn_id: str, from_id: str, to_id: str, label: str) -> Connection:
    return Connection(
        id=conn_id,
        from_id=from_id,
        to_id=to_id,
        label=label,
        position=Point(x=0.0, y=0.0),
        size=Dimensions(width=1.0, height=1.0),
        style=Style(),
    )


def _nested_c4_diagram(*, include_empty_group: bool = False) -> Diagram:
    elements: list[Element] = [
        _c4_shape('user', 'User', SemanticType.PERSON),
        _c4_shape('sys', 'Payment System', SemanticType.SYSTEM),
        _c4_shape('api', 'API Service', SemanticType.CONTAINER),
        _c4_shape('svc', ''),
        _c4_shape('db', 'Postgres', SemanticType.DATABASE),
        Group(
            id='group-sys',
            label='Payment System',
            position=Point(x=0.0, y=0.0),
            size=Dimensions(width=400.0, height=300.0),
            style=Style(),
            children=['api', 'svc', 'group-inner'],
        ),
        Group(
            id='group-inner',
            label='Data Layer',
            position=Point(x=0.0, y=0.0),
            size=Dimensions(width=200.0, height=150.0),
            style=Style(),
            children=['db'],
        ),
        _c4_connection('c1', 'user', 'sys', 'uses'),
        _c4_connection('c2', 'api', 'db', 'reads'),
    ]
    if include_empty_group:
        elements.append(
            Group(
                id='group-empty',
                label='Empty',
                position=Point(x=0.0, y=0.0),
                size=Dimensions(width=50.0, height=50.0),
                style=Style(),
                children=[],
            )
        )
    return Diagram(id='nested-c4', name='Nested C4', elements=elements)


class TestNestedC4Boundaries:
    """Nested group rendering in the C4 generators."""

    def test_mermaid_c4_nested_boundaries(self):
        diagram = _nested_c4_diagram()

        with pytest.warns(UserWarning, match='Re-pointing C4 Rel'):
            output = MermaidGenerator(diagram_type='c4').generate(diagram)

        outer_start = output.index('Boundary(group_sys, "Payment System") {')
        inner_start = output.index('Boundary(group_inner, "Data Layer") {')
        assert outer_start < inner_start
        assert inner_start < output.rindex('}')
        assert output.count('Container(api, "API Service")') == 1
        assert output.count('ContainerDb(db, "Postgres")') == 1

    @pytest.mark.filterwarnings('ignore:Re-pointing C4 Rel')
    def test_mermaid_c4_skips_empty_boundary(self):
        diagram = _nested_c4_diagram(include_empty_group=True)

        with pytest.warns(UserWarning, match='empty C4 boundary'):
            output = MermaidGenerator(diagram_type='c4').generate(diagram)

        assert 'group_empty' not in output

    def test_mermaid_c4_remaps_rel_from_suppressed_source_shape(self):
        diagram = _nested_c4_diagram()

        with pytest.warns(UserWarning, match='Re-pointing C4 Rel'):
            output = MermaidGenerator(diagram_type='c4').generate(diagram)

        assert 'Rel(user, api, "uses")' in output
        assert 'Rel(user, sys' not in output
        assert 'Rel(api, db, "reads")' in output

    def test_plantuml_c4_nested_boundaries_use_labels(self):
        diagram = _nested_c4_diagram()

        output = C4PlantUMLGenerator().generate(diagram)

        outer_start = output.index('System_Boundary(group_sys, "Payment System") {')
        inner_start = output.index('System_Boundary(group_inner, "Data Layer") {')
        assert outer_start < inner_start
        assert 'Container(api, "API Service")' in output
        assert 'Container(svc, "svc")' in output
        assert '"Container")' not in output
        assert '"Component")' not in output

    def test_plantuml_c4_declares_each_element_once(self):
        diagram = _nested_c4_diagram()

        output = C4PlantUMLGenerator().generate(diagram)

        assert output.count('Container(api,') == 1
        assert output.count('ComponentDb(db,') == 1
        assert output.count('Person(user,') == 1
        assert output.count('(sys,') == 0


def _style(fill, stroke_style='solid'):
    return Style(fill_color=fill, stroke_style=stroke_style)


@pytest.mark.parametrize(
    ('kwargs', 'expected', 'confidence'),
    [
        ({'shape_type': 'diamond'}, 'decision', 0.9),
        ({'shape_type': 'note'}, 'note', 0.9),
        ({'shape_type': 'sticky'}, 'note', 0.9),
        ({'shape_type': 'cylinder'}, 'database', 0.9),
        ({'shape_type': 'rectangle', 'label': 'PostgreSQL Database'}, 'database', 0.8),
        ({'shape_type': 'rectangle', 'label': 'REST API Service'}, 'service', 0.8),
        ({'shape_type': 'ellipse', 'label': 'Admin User'}, 'person', 0.85),
        ({'shape_type': 'rectangle', 'label': 'Kafka Queue'}, 'queue', 0.8),
        ({'shape_type': 'rectangle', 'label': '👤 Customer'}, 'person', 0.85),
        ({'shape_type': 'rectangle', 'label': '🗄️ Storage'}, 'database', 0.85),
        ({'shape_type': 'rectangle', 'label': '☁️ AWS'}, 'cloud', 0.85),
        ({'shape_type': 'rectangle', 'style': _style('#ffff00')}, 'note', 0.7),
        ({'shape_type': 'rectangle', 'style': _style('#808080', 'dashed')}, 'external', 0.65),
        ({'shape_type': 'rectangle', 'style': _style('#808080ff', 'dashed')}, 'external', 0.65),
        ({'shape_type': 'rectangle', 'style': _style('#808093', 'dashed')}, 'external', 0.65),
        (
            {'shape_type': 'rectangle', 'style': _style('#80948a', 'dashed'), 'size': Dimensions(100.0, 60.0)},
            'component',
            0.55,
        ),
        (
            {'shape_type': 'rectangle', 'style': _style('#8a8094', 'dashed'), 'size': Dimensions(100.0, 60.0)},
            'component',
            0.55,
        ),
        (
            {'shape_type': 'rectangle', 'style': _style('#808a94', 'dashed'), 'size': Dimensions(100.0, 60.0)},
            'component',
            0.55,
        ),
        ({'shape_type': 'rectangle', 'label': 'Box', 'metadata': {'semantic_type': 'database'}}, 'database', 1.0),
        ({'shape_type': 'rectangle', 'size': Dimensions(500.0, 300.0)}, 'system', 0.7),
        ({'shape_type': 'rectangle', 'size': Dimensions(500.0, 0.0)}, 'component', 0.4),
        ({'shape_type': 'ellipse', 'size': Dimensions(200.0, 50.0)}, 'database', 0.7),
        ({'shape_type': 'ellipse', 'label': 'Customer', 'size': Dimensions(60.0, 60.0)}, 'person', 0.925),
        ({'shape_type': 'rectangle', 'label': 'GameDropDown'}, 'component', 0.4),
        ({'shape_type': 'rectangle', 'label': 'Select the hit shape'}, 'component', 0.4),
        ({'shape_type': 'rectangle', 'label': 'Feedback'}, 'component', 0.4),
        ({'shape_type': 'rectangle', 'label': 'Orders DB'}, 'database', 0.8),
        ({'shape_type': 'rectangle', 'label': 'UserDatabase'}, 'database', 0.8),
        ({'shape_type': 'rectangle', 'label': 'mobile_user'}, 'person', 0.8),
    ],
)
def test_semantic_inference(kwargs, expected, confidence):
    from diacea.ir.semantic import infer_semantic_type

    semantic, inferred_confidence = infer_semantic_type(**kwargs)

    assert getattr(semantic, 'value', semantic) == expected
    assert inferred_confidence == pytest.approx(confidence)


@pytest.mark.parametrize(
    ('label', 'expected'),
    [
        ('Mobile user', 'person'),
        ('Customer', 'person'),
        ('Customer\nA person with an account', 'person'),
        ('Customer Database', 'database'),
        ('User Store DB', 'database'),
        ('Admin console', 'interface'),
        ('Message Queue', 'queue'),
        ('Check stock?', 'decision'),
        ('Replica Manager', 'container'),
        ('User Input', None),
        ('Filter results', None),
        ('HTTP client', None),
        ('ChangeResponder', None),
    ],
)
def test_label_head_noun_names_the_type(label, expected):
    """A label names what an element is with its last word; earlier words only qualify it."""
    from diacea.ir.semantic import _infer_from_text

    semantic, confidence = _infer_from_text(label)

    assert (getattr(semantic, 'value', None), confidence) == (expected, 0.8 if expected else 0.0)
