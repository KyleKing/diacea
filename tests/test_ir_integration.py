"""Generator behavior through the public pipeline: whole outputs, compared exactly."""

import json
import os
import re

import pytest

from diacea.formats import convert, parse_diagram, parse_file, render_diagram, verify_conversion
from diacea.ir import Connection, Diagram, Dimensions, Group, Point, SemanticType, Shape

from .configuration import TEST_DATA_DIR

_ORIGIN = Point(x=0.0, y=0.0)
_SIZE = Dimensions(width=100.0, height=60.0)
_GOLDENS_DIR = TEST_DATA_DIR / 'goldens'


def _make_shape(shape_id, label, shape_type='rectangle', semantic_type=None):
    return Shape(
        id=shape_id,
        label=label,
        shape_type=shape_type,
        position=_ORIGIN,
        size=_SIZE,
        semantic_type=semantic_type,
    )


def _make_connection(from_id, to_id, label=''):
    return Connection(
        id=f'{from_id}-{to_id}',
        from_id=from_id,
        to_id=to_id,
        label=label,
        position=_ORIGIN,
        size=_SIZE,
    )


def _excalidraw(*elements):
    return json.dumps({'type': 'excalidraw', 'elements': list(elements)})


def _rect(element_id, x, y, width=100, height=60):
    return {'id': element_id, 'type': 'rectangle', 'x': x, 'y': y, 'width': width, 'height': height}


@pytest.mark.parametrize(
    ('output_format', 'options', 'suffix'),
    [
        ('d2', {'d2_direction': 'down'}, '.down.d2'),
        ('mermaid', {'mermaid_type': 'flowchart'}, '.flowchart.mmd'),
        ('graphviz', {'graphviz_direction': 'TB'}, '.tb.dot'),
    ],
)
def test_generator_options_change_the_output_as_pinned(output_format, options, suffix):
    golden = _GOLDENS_DIR / f'excalidraw.json{suffix}'
    output = render_diagram(parse_file(TEST_DATA_DIR / 'excalidraw.json').diagram, output_format, **options).output

    if os.environ.get('DIACEA_REGEN_GOLDENS') == '1':
        golden.parent.mkdir(parents=True, exist_ok=True)
        golden.write_text(output + '\n', encoding='utf-8')
    assert output + '\n' == golden.read_text(encoding='utf-8')


def test_c4_declares_all_rel_aliases():
    """Every alias referenced by a Rel() must have a declaration."""
    diagram = Diagram(id='c4-test')
    diagram.elements = [
        _make_shape('customer', 'Customer', semantic_type=SemanticType.PERSON),
        _make_shape('api', 'API', semantic_type=SemanticType.CONTAINER),
        _make_shape('db', 'Database', semantic_type=SemanticType.DATABASE),
        _make_shape('bus', 'Event Bus', semantic_type=SemanticType.QUEUE),
        _make_shape('warehouse', 'Warehouse', semantic_type=SemanticType.DATABASE),
        Group(id='platform', label='Platform', children=['api', 'db', 'bus'], position=_ORIGIN, size=_SIZE),
        _make_connection('customer', 'api', 'Uses'),
        _make_connection('api', 'db', 'Reads'),
        _make_connection('api', 'bus', 'Publishes'),
        _make_connection('bus', 'warehouse', 'Streams'),
    ]

    output = render_diagram(diagram, 'mermaid', mermaid_type='c4').output

    declared = re.findall(
        r'^\s*(?:Person|System|SystemDb|SystemQueue|Container|ContainerDb|ContainerQueue|Component)\((\w+),',
        output,
        flags=re.MULTILINE,
    )
    rel_aliases = {alias for match in re.findall(r'Rel\((\w+), (\w+),', output) for alias in match}
    assert sorted(declared) == sorted(set(declared))
    assert rel_aliases <= set(declared)
    assert '        ContainerDb(db, "Database")' in output
    assert '        ContainerQueue(bus, "Event Bus")' in output
    assert '    SystemDb(warehouse, "Warehouse")' in output


def test_flowchart_quotes_labels_with_special_chars():
    diagram = Diagram(id='quote-test')
    diagram.elements = [
        _make_shape('check', 'Valid (yes/no)?', shape_type='diamond'),
        _make_shape('note', 'Say "hi" [now]'),
        _make_shape('pipe', 'a|b{c}', shape_type='circle'),
        _make_shape('plain', 'Plain label'),
    ]

    output = render_diagram(diagram, 'mermaid', mermaid_type='flowchart').output

    assert output == (
        'flowchart LR\n'
        '    check{"Valid (yes/no)?"}\n'
        '    note["Say #quot;hi#quot; [now]"]\n'
        '    pipe(("a|b{c}"))\n'
        '    plain[Plain label]'
    )


@pytest.mark.parametrize(
    ('elements', 'rankdir'),
    [
        pytest.param([_rect('a', 500, 0), _rect('b', 500, 300)], 'TB', id='tall-away-from-origin'),
        pytest.param([_rect('a', 0, 500), _rect('b', 400, 500)], 'LR', id='wide-away-from-origin'),
        pytest.param([_rect('a', 500, 500, 100, 100)], 'LR', id='square'),
        pytest.param([], 'LR', id='empty'),
    ],
)
def test_graphviz_direction_follows_the_drawing_aspect_ratio(elements, rankdir):
    output = convert(_excalidraw(*elements), 'graphviz').output

    assert [line.strip() for line in output.splitlines() if 'rankdir' in line] == [f'rankdir="{rankdir}";']


@pytest.mark.parametrize(
    ('source', 'input_format', 'output_format', 'expected', 'diagram_type'),
    [
        pytest.param(
            'sequenceDiagram\n  participant A\n  participant B as Bob\n  A->>B: hi\n',
            'mermaid',
            'mermaid',
            'sequenceDiagram\n    participant A as A\n    participant B as Bob\n    A->>B: hi',
            'sequence',
            id='mermaid-sequence-participants',
        ),
        pytest.param(
            'flowchart LR\n  a -->|"x -- y"| b\n  a -->|say "hi"| c\n  a -->|plain| d\n',
            'mermaid',
            'mermaid',
            'flowchart LR\n    a[a]\n    b[b]\n    c[c]\n    d[d]\n'
            '    a -->|"x -- y"| b\n    a -->|"say #quot;hi#quot;"| c\n    a -->|plain| d',
            'flowchart',
            id='mermaid-edge-labels-quoted-only-when-needed',
        ),
        pytest.param(
            'a: A {style.fill: "#f00"}\nb: B {style.stroke: "#0f0"}\nc: C\n'
            'g: G {\n  style.fill: "#00f"\n  style.stroke: "#0f0"\n  d: D\n}\n',
            'd2',
            'mermaid',
            'flowchart LR\n    a[A]\n    b[B]\n    c[C]\n    subgraph g[G]\n        d[D]\n    end\n\n'
            '    style a fill:#f00\n    style b stroke:#0f0\n    style g fill:#00f,stroke:#0f0',
            'flowchart',
            id='mermaid-styles-for-fill-or-stroke-and-groups',
        ),
        pytest.param(
            '@startuml\nrectangle "Users DB" as db\ndatabase "Orders" as o\n@enduml\n',
            'plantuml',
            'mermaid',
            'flowchart TD\n    db[Users DB]\n    o[(Orders)]',
            'flowchart',
            id='guessed-type-never-overrides-an-explicit-plantuml-shape',
        ),
        pytest.param(
            'g: G {\n  x: X\n}\ng -> g\n',
            'd2',
            'd2',
            'g: G {\n  x: X\n}\n',
            None,
            id='d2-drops-self-loop-on-container',
        ),
        pytest.param(
            '<svg xmlns="http://www.w3.org/2000/svg"><rect x="0" y="0" width="100" height="50" '
            'fill="rgb(255,0,0)" stroke="none"/><polygon id="gate" points="200,0 250,25 200,50 150,25" '
            'style="fill:#ff0000"/></svg>',
            'svg',
            'd2',
            'direction: right\n\nelem_1: elem_1\n'
            'gate: gate {\n  shape: diamond\n  style: {\n    fill: "#ff0000"\n  }\n}',
            None,
            id='d2-keeps-hex-colors-only-and-svg-ids',
        ),
        pytest.param(
            'a: {\n b: {\n  c: {\n   d: {\n    e: E\n   }\n  }\n }\n}\n',
            'd2',
            'mermaid',
            'flowchart LR\n    subgraph a[a]\n        subgraph b[b]\n            subgraph c[c]\n'
            '            end\n        end\n    end',
            'flowchart',
            id='mermaid-subgraphs-stop-at-depth-three',
        ),
    ],
)
def test_conversion_output(source, input_format, output_format, expected, diagram_type):
    result = convert(source, output_format, input_format=input_format)

    assert result.output == expected
    assert result.diagram_type == diagram_type


def test_svg_draws_multiline_edge_labels_one_line_per_row():
    output = convert('a: A\nb: B\na -> b: "line1\\nline2"\n', 'svg', input_format='d2').output

    assert (
        '<polyline points="60.0,61.0 60.0,151.0" fill="none" stroke="#1e1e1e" stroke-width="1.5" '
        'marker-end="url(#arrow)"/><text class="edge-label" x="60.0" y="106.0" text-anchor="middle">line1</text>'
        '<text class="edge-label" x="60.0" y="120.0" text-anchor="middle">line2</text>\n'
    ) in output


def test_drawings_skip_connections_to_missing_nodes():
    half_routed = Connection(
        id='c2', from_id='a', to_id='ghost2', position=_ORIGIN, size=_SIZE, start_point=Point(50.0, 60.0)
    )
    diagram = Diagram(id='dangling', elements=[_make_shape('a', 'A'), _make_connection('a', 'ghost'), half_routed])

    svg = render_diagram(diagram, 'svg').output
    scene = json.loads(render_diagram(diagram, 'excalidraw').output)

    assert svg.splitlines()[-2:] == [
        (
            '<g id="a" data-semantic=""><rect x="0.0" y="0.0" width="100.0" height="60.0" rx="2.0" fill="#ffffff" '
            'stroke="#1e1e1e" stroke-width="1.5"/><text x="50.0" y="34.7" text-anchor="middle">A</text></g>'
        ),
        '</svg>',
    ]
    assert [element['type'] for element in scene['elements']] == ['rectangle', 'text']


def test_excalidraw_group_label_sits_inside_its_border_at_two_decimals():
    scene = _excalidraw(
        _rect('g', 10.12345, 20.98765, 400, 300),
        {'id': 'gt', 'type': 'text', 'x': 15, 'y': 25, 'width': 50, 'height': 20, 'text': 'Group', 'fontSize': 20},
        {**_rect('a', 100, 100), 'boundElements': [{'id': 'at', 'type': 'text'}]},
        {'id': 'at', 'type': 'text', 'x': 110, 'y': 120, 'width': 50, 'height': 20, 'text': 'A', 'containerId': 'a'},
    )

    elements = json.loads(convert(scene, 'excalidraw').output)['elements']

    assert [(e['id'], e['x'], e['y']) for e in elements if e['type'] == 'text'] == [
        ('group-g-label', 20.12, 30.99),
        ('a-label', 144.5, 117.5),
    ]


def test_verification_counts_only_connections_lost_beyond_the_reported_ones():
    source = 'flowchart LR\n  subgraph g[Group]\n    a[A]\n  end\n  g --> a\n  a --> b[B]\n  b --> c[C]\n'
    result = render_diagram(parse_diagram(source).diagram, 'graphviz')
    assert result.warnings == ['Dropping connection between container and its own content: group-g -> a']
    result.output = result.output.replace('    b -> c;\n', '')

    assert verify_conversion(result) == [
        "1 connection(s) lost without a warning, among: 'B' -> 'C', 'Group' -> 'A'",
    ]
