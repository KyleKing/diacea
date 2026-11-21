"""What one-way conversion keeps and what it drops.

Parsers keep geometry, labels, fill, and connections; text generators keep
structure, labels, styles, and semantics but leave positions to the target
format's layout engine.
"""

import pytest

from diacea.formats import render_diagram
from diacea.ir import Connection, Diagram, Dimensions, Point, Shape
from diacea.ir.elements import Style
from diacea.parsers import ExcalidrawParser, SVGParser, TLDrawParser


def _styled_diagram():
    def shape(shape_id, label, x, semantic=None, style=None):
        result = Shape(
            id=shape_id,
            label=label,
            shape_type='rectangle',
            position=Point(x, 200.0),
            size=Dimensions(150.0, 80.0),
            style=style or Style(),
        )
        result.semantic_type = semantic
        return result

    styled = Style(fill_color='#ff0000', stroke_color='#0000ff', stroke_width=3.0, stroke_style='dashed')
    return Diagram(
        id='t',
        elements=[
            shape('styled', 'Styled Shape', 100.0, style=styled),
            shape('db', 'Database', 400.0, semantic='database'),
            Connection(
                id='c1', from_id='styled', to_id='db', label='HTTP', position=Point(0.0, 0.0), size=Dimensions(0.0, 0.0)
            ),
            Connection(
                id='c2',
                from_id='db',
                to_id='styled',
                label='sync',
                connection_type='bidirectional',
                position=Point(0.0, 0.0),
                size=Dimensions(0.0, 0.0),
            ),
        ],
    )


@pytest.mark.parametrize(
    ('output_format', 'options', 'expected'),
    [
        (
            'plantuml',
            {},
            (
                '@startuml\nrectangle "Styled Shape" as styled\ndatabase "Database" as db\n'
                'styled --> db : "HTTP"\ndb <--> styled : "sync"\n@enduml'
            ),
        ),
        (
            'mermaid',
            {'mermaid_type': 'flowchart'},
            (
                'flowchart LR\n    styled[Styled Shape]\n    db[(Database)]\n    styled -->|HTTP| db\n'
                '    db <-->|sync| styled\n\n    style styled fill:#ff0000,stroke:#0000ff,stroke-dasharray:5 5'
            ),
        ),
        (
            'graphviz',
            {},
            (
                'digraph "diagram" {\n    rankdir="LR";\n    node [shape="box", fontname="Helvetica"];\n'
                '    edge [fontname="Helvetica"];\n\n'
                '    styled [label="Styled Shape", fillcolor="#ff0000", style="filled", '
                'color="#0000ff", penwidth="3.0"];\n'
                '    db [label="Database", shape="cylinder"];\n\n'
                '    styled -> db [label="HTTP"];\n    db -> styled [label="sync", dir="both"];\n}'
            ),
        ),
        (
            'd2',
            {},
            (
                'direction: right\n\nstyled: Styled Shape {\n  style: {\n    fill: "#ff0000"\n    stroke: "#0000ff"\n'
                '    stroke-width: 3\n    stroke-dash: 3\n  }\n}\ndb: Database {\n  shape: cylinder\n}\n\n'
                'styled -> db: HTTP\ndb <-> styled: sync'
            ),
        ),
    ],
)
def test_text_output_keeps_structure_style_and_semantics_but_not_positions(output_format, options, expected):
    assert render_diagram(_styled_diagram(), output_format, **options).output == expected


def test_excalidraw_keeps_geometry_and_keeps_sketch_settings_only_as_metadata():
    element = {'id': 'a', 'type': 'rectangle', 'x': 100.0, 'y': 200.0, 'width': 150.0, 'height': 80.0}
    shape = ExcalidrawParser().parse({'elements': [{**element, 'roughness': 2, 'seed': 12345}]}).get_shapes()[0]

    assert (shape.position, shape.size, shape.style) == (
        Point(100.0, 200.0),
        Dimensions(150.0, 80.0),
        Style(stroke_style='solid', opacity=1.0),
    )
    assert shape.metadata['excalidraw']['seed'] == 12345


def test_svg_keeps_rect_geometry_and_fill_and_reduces_paths_to_bounding_boxes():
    diagram = SVGParser().parse(
        '<svg xmlns="http://www.w3.org/2000/svg"><rect x="10" y="20" width="100" height="50" fill="#ff0000"/>'
        '<path d="M 210 10 L 300 10 L 300 50 L 210 50 Z" fill="green"/></svg>'
    )

    assert [(s.shape_type, s.position, s.size, s.style.fill_color) for s in diagram.get_shapes()] == [
        ('rectangle', Point(10.0, 20.0), Dimensions(100.0, 50.0), '#ff0000'),
        ('rectangle', Point(210.0, 10.0), Dimensions(90.0, 40.0), 'green'),
    ]


@pytest.mark.parametrize(('options', 'expected_ids'), [({}, ['shape1']), ({'page_index': None}, ['shape1', 'shape2'])])
def test_legacy_tldraw_reads_the_first_page_unless_asked_for_all(options, expected_ids):
    def page(page_id, shape_id, shape_type, point):
        shape = {'type': shape_type, 'point': point, 'size': [120.0, 60.0]}
        return {'id': page_id, 'shapes': {shape_id: shape}, 'bindings': {}}

    data = {
        'document': {
            'pages': {
                'page1': page('page1', 'shape1', 'rectangle', [50.0, 100.0]),
                'page2': page('page2', 'shape2', 'ellipse', [0.0, 0.0]),
            }
        }
    }

    shapes = TLDrawParser(**options).parse(data).get_shapes()

    assert [s.id for s in shapes] == expected_ids
    assert (shapes[0].position, shapes[0].size) == (Point(50.0, 100.0), Dimensions(120.0, 60.0))
