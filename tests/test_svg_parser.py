"""Tests for SVG parser."""

from pathlib import Path

import pytest
from defusedxml import EntitiesForbidden

from diacea.formats import convert, parse_diagram
from diacea.ir import Connection, Dimensions, Group, Point, Shape, Text
from diacea.ir.semantic import SemanticType
from diacea.parsers import SVGParser


class TestSVGParser:
    """Test SVG parser."""

    def test_parse_rectangle(self):
        """Test parsing SVG rectangle."""
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg">
            <rect id="rect1" x="10" y="20" width="100" height="50"
                  fill="blue" stroke="black" data-label="Component"/>
        </svg>
        """

        parser = SVGParser()
        diagram = parser.parse(svg)

        shapes = [e for e in diagram.elements if isinstance(e, Shape)]
        assert len(shapes) == 1
        assert shapes[0].id == 'rect1'
        assert shapes[0].position.x == 10
        assert shapes[0].position.y == 20
        assert shapes[0].size.width == 100
        assert shapes[0].size.height == 50
        assert shapes[0].label == 'Component'

    def test_parse_circle(self):
        """Test parsing SVG circle."""
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg">
            <circle id="circle1" cx="100" cy="100" r="50" fill="red"/>
        </svg>
        """

        parser = SVGParser()
        diagram = parser.parse(svg)

        shapes = [e for e in diagram.elements if isinstance(e, Shape)]
        assert len(shapes) == 1
        assert shapes[0].shape_type == 'ellipse'
        assert shapes[0].size.width == 100  # diameter
        assert shapes[0].size.height == 100
        # Center at 100,100 with radius 50 → position at 50,50
        assert shapes[0].position.x == 50
        assert shapes[0].position.y == 50

    def test_parse_ellipse(self):
        """Test parsing SVG ellipse."""
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg">
            <ellipse id="ellipse1" cx="200" cy="150" rx="80" ry="40" fill="green"/>
        </svg>
        """

        parser = SVGParser()
        diagram = parser.parse(svg)

        shapes = [e for e in diagram.elements if isinstance(e, Shape)]
        assert len(shapes) == 1
        assert shapes[0].shape_type == 'ellipse'
        assert shapes[0].size.width == 160  # 2 * rx
        assert shapes[0].size.height == 80  # 2 * ry

    def test_parse_polygon_diamond(self):
        """Test parsing 4-point polygon as diamond."""
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg">
            <polygon id="diamond1" points="100,50 150,100 100,150 50,100" fill="yellow"/>
        </svg>
        """

        parser = SVGParser()
        diagram = parser.parse(svg)

        shapes = [e for e in diagram.elements if isinstance(e, Shape)]
        assert len(shapes) == 1
        assert shapes[0].shape_type == 'diamond'
        assert shapes[0].position.x == 50
        assert shapes[0].position.y == 50
        assert shapes[0].size.width == 100
        assert shapes[0].size.height == 100

    def test_semantic_hints(self):
        """Test semantic type hints."""
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg">
            <rect id="db" x="0" y="0" width="100" height="50" data-semantic="database"/>
            <circle id="user" cx="200" cy="25" r="25" data-semantic="person"/>
            <rect id="svc" x="300" y="0" width="120" height="60" data-semantic="service"/>
        </svg>
        """

        parser = SVGParser()
        diagram = parser.parse(svg)

        shapes = [e for e in diagram.elements if isinstance(e, Shape)]
        assert len(shapes) == 3

        # Find shapes by id
        db_shape = next(s for s in shapes if s.id == 'db')
        user_shape = next(s for s in shapes if s.id == 'user')
        svc_shape = next(s for s in shapes if s.id == 'svc')

        assert db_shape.semantic_type == SemanticType.DATABASE.value
        assert db_shape.semantic_confidence == 0.9
        assert user_shape.semantic_type == SemanticType.PERSON.value
        assert svc_shape.semantic_type == SemanticType.SERVICE.value

    def test_text_association(self):
        """Test text label association with shapes."""
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg">
            <rect id="r1" x="0" y="0" width="100" height="50"/>
            <text x="20" y="30">Label Text</text>
        </svg>
        """

        parser = SVGParser()
        diagram = parser.parse(svg)

        shapes = [e for e in diagram.elements if isinstance(e, Shape)]
        assert len(shapes) == 1
        assert shapes[0].label == 'Label Text'

    def test_text_element_parsing(self):
        """Test standalone text element."""
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg">
            <text id="txt1" x="50" y="50" font-size="16">Important Note</text>
        </svg>
        """

        parser = SVGParser()
        diagram = parser.parse(svg)

        texts = [e for e in diagram.elements if isinstance(e, Text)]
        assert len(texts) == 1
        assert texts[0].content == 'Important Note'
        assert texts[0].position.x == 50
        assert texts[0].position.y == 50

    def test_group_parsing(self):
        """Test SVG group parsing."""
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg">
            <g id="system1" data-label="System">
                <rect id="comp1" x="10" y="10" width="80" height="40"/>
                <rect id="comp2" x="100" y="10" width="80" height="40"/>
            </g>
        </svg>
        """

        parser = SVGParser()
        diagram = parser.parse(svg)

        groups = [e for e in diagram.elements if isinstance(e, Group)]
        assert len(groups) == 1
        assert groups[0].id == 'system1'
        assert groups[0].label == 'System'
        assert len(groups[0].children) == 2
        assert 'comp1' in groups[0].children
        assert 'comp2' in groups[0].children

    def test_style_parsing(self):
        """Test SVG style attributes."""
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg">
            <rect id="r1" x="0" y="0" width="100" height="50"
                  fill="#E3F2FD" stroke="#1976D2" stroke-width="2"/>
            <rect id="r2" x="120" y="0" width="100" height="50"
                  fill="none" stroke="#4CAF50" stroke-width="3" stroke-dasharray="5,5"/>
        </svg>
        """

        parser = SVGParser()
        diagram = parser.parse(svg)

        shapes = [e for e in diagram.elements if isinstance(e, Shape)]
        assert len(shapes) == 2

        r1 = next(s for s in shapes if s.id == 'r1')
        assert r1.style.fill_color == '#E3F2FD'
        assert r1.style.stroke_color == '#1976D2'
        assert r1.style.stroke_width == 2.0
        assert r1.style.stroke_style == 'solid'

        r2 = next(s for s in shapes if s.id == 'r2')
        assert r2.style.fill_color is None  # fill="none"
        assert r2.style.stroke_color == '#4CAF50'
        assert r2.style.stroke_width == 3.0
        assert r2.style.stroke_style == 'dashed'

    def test_empty_svg(self):
        """Test parsing empty SVG."""
        svg = '<svg xmlns="http://www.w3.org/2000/svg"></svg>'

        parser = SVGParser()
        diagram = parser.parse(svg)

        assert len(diagram.elements) == 0

    def test_nested_groups(self):
        """Test nested groups."""
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg">
            <g id="outer" data-label="Outer">
                <rect id="r1" x="10" y="10" width="50" height="30"/>
                <g id="inner" data-label="Inner">
                    <rect id="r2" x="20" y="50" width="40" height="25"/>
                </g>
            </g>
        </svg>
        """

        parser = SVGParser()
        diagram = parser.parse(svg)

        groups = [e for e in diagram.elements if isinstance(e, Group)]
        shapes = {e.id: e for e in diagram.elements if isinstance(e, Shape)}

        # A group wrapping a single shape is that shape; only the outer group is a container
        assert [group.id for group in groups] == ['outer']
        assert groups[0].label == 'Outer'
        assert groups[0].children == ['r1', 'inner']
        assert shapes['inner'].label == 'Inner'

    def test_labelled_node_groups_and_container_border(self):
        """A <g> per labelled box, inside a <g> with a border rect and a title."""
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg">
            <defs><marker id="arrowhead"><polygon points="0 0, 10 3, 0 6"/></marker></defs>
            <g id="services" data-semantic="system">
                <rect x="0" y="0" width="400" height="200" fill="none" stroke="#666"/>
                <text x="10" y="20" font-size="14">Services</text>
                <g id="auth" data-semantic="service">
                    <rect x="20" y="40" width="100" height="50"/>
                    <text x="70" y="70" font-size="11">Auth Service</text>
                </g>
                <g id="orders_db" data-semantic="database">
                    <ellipse cx="300" cy="65" rx="40" ry="20"/>
                    <text x="300" y="70" font-size="11">Orders DB</text>
                </g>
            </g>
            <line x1="120" y1="65" x2="260" y2="65"/>
        </svg>
        """

        diagram = SVGParser().parse(svg)
        shapes = {e.id: e for e in diagram.elements if isinstance(e, Shape)}
        group = next(e for e in diagram.elements if isinstance(e, Group))

        assert set(shapes) == {'auth', 'orders_db'}
        assert shapes['auth'].label == 'Auth Service'
        assert shapes['auth'].semantic_type == SemanticType.SERVICE
        assert shapes['orders_db'].semantic_type == SemanticType.DATABASE
        assert (group.id, group.label, group.children) == ('services', 'Services', ['auth', 'orders_db'])
        assert [(c.from_id, c.to_id) for c in diagram.elements if isinstance(c, Connection)] == [('auth', 'orders_db')]


class TestSVGTransforms:
    """Test SVG transform support."""

    def test_translate_transform(self):
        svg = """<svg xmlns="http://www.w3.org/2000/svg">
            <rect id="r1" x="0" y="0" width="100" height="50" transform="translate(50, 100)"/>
        </svg>"""
        parser = SVGParser()
        diagram = parser.parse(svg)

        shapes = diagram.get_shapes()
        assert len(shapes) == 1
        assert shapes[0].position.x == 50.0
        assert shapes[0].position.y == 100.0

    def test_scale_transform(self):
        svg = """<svg xmlns="http://www.w3.org/2000/svg">
            <rect id="r1" x="10" y="10" width="100" height="50" transform="scale(2)"/>
        </svg>"""
        parser = SVGParser()
        diagram = parser.parse(svg)

        shapes = diagram.get_shapes()
        assert len(shapes) == 1
        assert shapes[0].position.x == 20.0
        assert shapes[0].position.y == 20.0
        assert shapes[0].size.width == 200.0
        assert shapes[0].size.height == 100.0

    def test_combined_transform(self):
        svg = """<svg xmlns="http://www.w3.org/2000/svg">
            <rect id="r1" x="0" y="0" width="100" height="50" transform="translate(10, 20) scale(2)"/>
        </svg>"""
        parser = SVGParser()
        diagram = parser.parse(svg)

        shapes = diagram.get_shapes()
        assert len(shapes) == 1
        assert shapes[0].size.width == 200.0

    def test_group_transform_inheritance(self):
        svg = """<svg xmlns="http://www.w3.org/2000/svg">
            <g transform="translate(100, 100)">
                <rect id="r1" x="0" y="0" width="50" height="50"/>
            </g>
        </svg>"""
        parser = SVGParser()
        diagram = parser.parse(svg)

        shapes = diagram.get_shapes()
        assert len(shapes) == 1
        assert shapes[0].position.x == 100.0
        assert shapes[0].position.y == 100.0


class TestSVGPathSupport:
    """Test SVG path element support."""

    def test_simple_path_rectangle(self):
        svg = """<svg xmlns="http://www.w3.org/2000/svg">
            <path id="p1" d="M 0 0 L 100 0 L 100 50 L 0 50 Z"/>
        </svg>"""
        parser = SVGParser()
        diagram = parser.parse(svg)

        shapes = diagram.get_shapes()
        assert len(shapes) == 1
        assert shapes[0].shape_type == 'rectangle'
        assert shapes[0].size.width == 100.0
        assert shapes[0].size.height == 50.0

    def test_path_with_relative_commands(self):
        svg = """<svg xmlns="http://www.w3.org/2000/svg">
            <path id="p1" d="M 10 10 l 100 0 l 0 50 l -100 0 z"/>
        </svg>"""
        parser = SVGParser()
        diagram = parser.parse(svg)

        shapes = diagram.get_shapes()
        assert len(shapes) == 1
        assert shapes[0].size.width == 100.0

    def test_path_with_h_v_commands(self):
        svg = """<svg xmlns="http://www.w3.org/2000/svg">
            <path id="p1" d="M 0 0 H 100 V 50 H 0 Z"/>
        </svg>"""
        parser = SVGParser()
        diagram = parser.parse(svg)

        shapes = diagram.get_shapes()
        assert len(shapes) == 1
        assert shapes[0].size.width == 100.0
        assert shapes[0].size.height == 50.0


class TestSVGPathCurves:
    """Curve commands must not desync the tokenizer and must sample true curve extents."""

    def test_curve_then_line_no_desync(self):
        svg = """<svg xmlns="http://www.w3.org/2000/svg">
            <path id="p1" d="M 0 0 c 10 20 30 40 50 60 l 50 0 Z"/>
        </svg>"""
        parser = SVGParser()
        diagram = parser.parse(svg)

        shapes = diagram.get_shapes()
        assert len(shapes) == 1
        assert shapes[0].size.width == 100.0
        assert shapes[0].size.height == 60.0
        assert any('curve' in w for w in parser.warnings)

    def test_cubic_bbox_uses_curve_extremum_not_control_points(self):
        svg = """<svg xmlns="http://www.w3.org/2000/svg">
            <path id="p1" d="M 0 0 C 0 100 100 100 100 0 Z"/>
        </svg>"""
        parser = SVGParser()
        diagram = parser.parse(svg)

        shapes = diagram.get_shapes()
        assert len(shapes) == 1
        assert shapes[0].size.width == 100.0
        assert shapes[0].size.height == 75.0

    def test_implicit_curve_repetition(self):
        svg = """<svg xmlns="http://www.w3.org/2000/svg">
            <path id="p1" d="M 0 0 C 0 50 50 50 50 0 100 -50 150 -50 150 0"/>
        </svg>"""
        parser = SVGParser()
        diagram = parser.parse(svg)

        shapes = diagram.get_shapes()
        assert len(shapes) == 1
        assert shapes[0].position.y == -37.5
        assert shapes[0].size.width == 150.0
        assert shapes[0].size.height == 75.0

    def test_arc_bulge_included_in_bbox(self):
        svg = """<svg xmlns="http://www.w3.org/2000/svg">
            <path id="p1" d="M 0 0 A 50 50 0 0 1 100 0 L 100 40 L 0 40 Z"/>
        </svg>"""
        parser = SVGParser()
        diagram = parser.parse(svg)

        shapes = diagram.get_shapes()
        assert len(shapes) == 1
        assert shapes[0].position.y == -50.0
        assert shapes[0].size.width == 100.0
        assert shapes[0].size.height == 90.0

    def test_quadratic_and_smooth_commands(self):
        svg = """<svg xmlns="http://www.w3.org/2000/svg">
            <path id="p1" d="M 0 0 Q 50 80 100 0 T 200 0 Z"/>
        </svg>"""
        parser = SVGParser()
        diagram = parser.parse(svg)

        shapes = diagram.get_shapes()
        assert len(shapes) == 1
        assert shapes[0].position.y == -40.0
        assert shapes[0].size.width == 200.0
        assert shapes[0].size.height == 80.0

    def test_smooth_cubic_reflects_previous_control(self):
        svg = """<svg xmlns="http://www.w3.org/2000/svg">
            <path id="p1" d="M 0 0 C 0 40 50 40 50 0 S 100 -40 100 0 L 100 20 L 0 20 Z"/>
        </svg>"""
        parser = SVGParser()
        diagram = parser.parse(svg)

        shapes = diagram.get_shapes()
        assert len(shapes) == 1
        assert shapes[0].position.y == -30.0
        assert shapes[0].size.width == 100.0
        assert shapes[0].size.height == 60.0

    def test_full_circle_from_two_arcs(self):
        svg = """<svg xmlns="http://www.w3.org/2000/svg">
            <path id="p1" d="M 0 50 A 50 50 0 0 1 100 50 A 50 50 0 0 1 0 50 Z"/>
        </svg>"""
        parser = SVGParser()
        diagram = parser.parse(svg)

        shapes = diagram.get_shapes()
        assert len(shapes) == 1
        assert shapes[0].size.width == 100.0
        assert shapes[0].size.height == 100.0

    def test_real_llm_proxy_component_fixture(self):
        svg_path = Path(__file__).parent / 'data' / 'real' / 'llm_proxy_component.svg'

        parser = SVGParser()
        diagram = parser.parse(svg_path.read_text())

        assert len(diagram.elements) > 0
        assert any('curve' in w for w in parser.warnings)


class TestSVGLineElements:
    """Test SVG line and polyline elements."""

    def test_line_element(self):
        svg = """<svg xmlns="http://www.w3.org/2000/svg">
            <rect id="r1" x="0" y="0" width="50" height="50"/>
            <rect id="r2" x="100" y="0" width="50" height="50"/>
            <line id="l1" x1="50" y1="25" x2="100" y2="25"/>
        </svg>"""
        parser = SVGParser()
        diagram = parser.parse(svg)

        connections = diagram.get_connections()
        assert len(connections) == 1
        assert connections[0].from_id == 'r1'
        assert connections[0].to_id == 'r2'

    def test_polyline_element(self):
        svg = """<svg xmlns="http://www.w3.org/2000/svg">
            <rect id="r1" x="0" y="0" width="50" height="50"/>
            <rect id="r2" x="100" y="0" width="50" height="50"/>
            <rect id="r3" x="200" y="0" width="50" height="50"/>
            <polyline points="50,25 100,25 150,25 200,25"/>
        </svg>"""
        parser = SVGParser()
        diagram = parser.parse(svg)

        connections = diagram.get_connections()
        assert len(connections) >= 2


class TestSVGSecurity:
    """Test that untrusted SVG cannot trigger XML entity attacks."""

    def test_billion_laughs_is_rejected(self):
        svg = """<?xml version="1.0"?>
        <!DOCTYPE svg [
            <!ENTITY a "aaaaaaaaaa">
            <!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">
            <!ENTITY c "&b;&b;&b;&b;&b;&b;&b;&b;&b;&b;">
        ]>
        <svg xmlns="http://www.w3.org/2000/svg"><text id="t1">&c;</text></svg>"""

        parser = SVGParser()
        with pytest.raises(EntitiesForbidden):
            parser.parse(svg)


_HINTED_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg"><rect id="svc1" x="10" y="10" width="100" height="50" '
    'data-semantic="service" data-label="API"/><ellipse id="db1" cx="200" cy="35" rx="60" ry="30" '
    'data-semantic="database" data-label="PostgreSQL"/><rect id="comp1" x="0" y="100" width="100" height="50" '
    'data-label="Component A"/></svg>'
)


@pytest.mark.parametrize(
    ('output_format', 'expected'),
    [
        (
            'plantuml',
            (
                '@startuml\nrectangle "API" as svc1\ndatabase "PostgreSQL" as db1\n'
                'rectangle "Component A" as comp1\n@enduml'
            ),
        ),
        (
            'mermaid',
            (
                'C4Context\n    title SVG Diagram\n    System(svc1, "API")\n    SystemDb(db1, "PostgreSQL")\n'
                '    Component(comp1, "Component A")'
            ),
        ),
        ('d2', 'direction: right\n\nsvc1: API\ndb1: PostgreSQL {\n  shape: cylinder\n}\ncomp1: Component A'),
    ],
)
def test_svg_hints_and_labels_convert(output_format, expected):
    assert convert(_HINTED_SVG, output_format).output == expected


def _layout(body):
    diagram = parse_diagram(f'<svg xmlns="http://www.w3.org/2000/svg">{body}</svg>', 'svg').diagram
    return [
        (
            type(element).__name__,
            element.id,
            element.label if isinstance(element, (Shape, Group)) else getattr(element, 'content', None),
            (element.position.x, element.position.y, element.size.width, element.size.height),
            {key: value for key, value in element.metadata.items() if key != 'svg'},
        )
        for element in diagram.elements
        if not isinstance(element, Connection)
    ], [(conn.from_id, conn.to_id, conn.position, conn.size) for conn in diagram.get_connections()]


@pytest.mark.parametrize(
    ('body', 'elements', 'connections'),
    [
        pytest.param(
            '<g id="grp"><rect x="0" y="0" width="300" height="200"/><rect x="50" y="0" width="100" height="200"/>'
            '<rect x="200" y="50" width="50" height="50"/></g>',
            [
                ('Group', 'grp', '', (0.0, 0.0, 300.0, 200.0), {}),
                ('Shape', 'elem_2', '', (50.0, 0.0, 100.0, 200.0), {}),
                ('Shape', 'elem_3', '', (200.0, 50.0, 50.0, 50.0), {}),
            ],
            [],
            id='border-may-touch-a-member-top-and-bottom',
        ),
        pytest.param(
            '<ellipse cx="100" rx="40" ry="20"/><ellipse cx="300" cy="50" rx="40"/>',
            [('Shape', 'elem_1', '', (60.0, -20.0, 80.0, 40.0), {})],
            [],
            id='ellipse-without-cy-sits-on-zero-and-without-ry-is-dropped',
        ),
        pytest.param(
            '<rect x="0" y="0" width="200" height="100"/><text x="50" y="50">Solo</text>',
            [
                ('Shape', 'elem_1', 'Solo', (0.0, 0.0, 200.0, 100.0), {}),
                ('Text', 'elem_2', 'Solo', (50.0, 50.0, 33.6, 16.8), {'label_of': 'elem_1'}),
            ],
            [],
            id='single-text-is-the-label-with-no-description',
        ),
        pytest.param(
            '<rect x="0" y="0" width="200" height="100"/><text x="20" y="30" font-size="12px">small</text>'
            '<text x="20" y="70" font-size="30px">Big</text>',
            [
                ('Shape', 'elem_1', 'Big', (0.0, 0.0, 200.0, 100.0), {'description': 'small'}),
                ('Text', 'elem_2', 'small', (20.0, 30.0, 36.0, 14.399999999999999), {'label_of': 'elem_1'}),
                ('Text', 'elem_3', 'Big', (20.0, 70.0, 54.0, 36.0), {'label_of': 'elem_1'}),
            ],
            [],
            id='largest-font-with-units-is-the-label',
        ),
        pytest.param(
            '<rect id="a" x="-20" y="-20" width="40" height="40"/><rect id="b" x="180" y="-20" width="40" height="40"/>'
            '<rect id="c" x="180" y="180" width="40" height="40"/><line x2="200" y2="0"/>'
            '<polyline points="200,0 200,200"/><rect id="d" x="-20" y="180" width="40" height="40"/>'
            '<line x1="200" y1="200" y2="200"/>',
            [
                ('Shape', 'a', '', (-20.0, -20.0, 40.0, 40.0), {}),
                ('Shape', 'b', '', (180.0, -20.0, 40.0, 40.0), {}),
                ('Shape', 'c', '', (180.0, 180.0, 40.0, 40.0), {}),
                ('Shape', 'd', '', (-20.0, 180.0, 40.0, 40.0), {}),
            ],
            [
                ('a', 'b', Point(100.0, 0.0), Dimensions(200.0, 0.0)),
                ('b', 'c', Point(200.0, 100.0), Dimensions(0.0, 200.0)),
                ('c', 'd', Point(100.0, 200.0), Dimensions(200.0, 0.0)),
            ],
            id='line-coordinates-default-to-zero-and-a-two-point-polyline-connects',
        ),
        pytest.param(
            '<rect id="r" x="0" y="0" width="100" height="50" transform="rotate(90 50 25)"/>',
            [('Shape', 'r', '', (0.0, 0.0, 100.0, 50.0), {})],
            [],
            id='rotation-about-a-center-parses',
        ),
    ],
)
def test_svg_parses_to(body, elements, connections):
    assert _layout(body) == (elements, connections)
