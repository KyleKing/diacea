"""Tests for SVG parser."""

from pathlib import Path

import pytest

from diacea.cli import detect_input_format
from diacea.ir import Group, Shape, Text
from diacea.ir.semantic import SemanticType
from diacea.parsers import SVGParser


class TestSVGParser:
    """Test SVG parser."""

    def test_parse_rectangle(self):
        """Test parsing SVG rectangle."""
        svg = '''
        <svg xmlns="http://www.w3.org/2000/svg">
            <rect id="rect1" x="10" y="20" width="100" height="50"
                  fill="blue" stroke="black" data-label="Component"/>
        </svg>
        '''

        parser = SVGParser()
        diagram = parser.parse(svg)

        shapes = [e for e in diagram.elements if isinstance(e, Shape)]
        assert len(shapes) == 1
        assert shapes[0].id == "rect1"
        assert shapes[0].position.x == 10
        assert shapes[0].position.y == 20
        assert shapes[0].size.width == 100
        assert shapes[0].size.height == 50
        assert shapes[0].label == "Component"

    def test_parse_circle(self):
        """Test parsing SVG circle."""
        svg = '''
        <svg xmlns="http://www.w3.org/2000/svg">
            <circle id="circle1" cx="100" cy="100" r="50" fill="red"/>
        </svg>
        '''

        parser = SVGParser()
        diagram = parser.parse(svg)

        shapes = [e for e in diagram.elements if isinstance(e, Shape)]
        assert len(shapes) == 1
        assert shapes[0].shape_type == "ellipse"
        assert shapes[0].size.width == 100  # diameter
        assert shapes[0].size.height == 100
        # Center at 100,100 with radius 50 → position at 50,50
        assert shapes[0].position.x == 50
        assert shapes[0].position.y == 50

    def test_parse_ellipse(self):
        """Test parsing SVG ellipse."""
        svg = '''
        <svg xmlns="http://www.w3.org/2000/svg">
            <ellipse id="ellipse1" cx="200" cy="150" rx="80" ry="40" fill="green"/>
        </svg>
        '''

        parser = SVGParser()
        diagram = parser.parse(svg)

        shapes = [e for e in diagram.elements if isinstance(e, Shape)]
        assert len(shapes) == 1
        assert shapes[0].shape_type == "ellipse"
        assert shapes[0].size.width == 160  # 2 * rx
        assert shapes[0].size.height == 80  # 2 * ry

    def test_parse_polygon_diamond(self):
        """Test parsing 4-point polygon as diamond."""
        svg = '''
        <svg xmlns="http://www.w3.org/2000/svg">
            <polygon id="diamond1" points="100,50 150,100 100,150 50,100" fill="yellow"/>
        </svg>
        '''

        parser = SVGParser()
        diagram = parser.parse(svg)

        shapes = [e for e in diagram.elements if isinstance(e, Shape)]
        assert len(shapes) == 1
        assert shapes[0].shape_type == "diamond"
        assert shapes[0].position.x == 50
        assert shapes[0].position.y == 50
        assert shapes[0].size.width == 100
        assert shapes[0].size.height == 100

    def test_semantic_hints(self):
        """Test semantic type hints."""
        svg = '''
        <svg xmlns="http://www.w3.org/2000/svg">
            <rect id="db" x="0" y="0" width="100" height="50" data-semantic="database"/>
            <circle id="user" cx="200" cy="25" r="25" data-semantic="person"/>
            <rect id="svc" x="300" y="0" width="120" height="60" data-semantic="service"/>
        </svg>
        '''

        parser = SVGParser()
        diagram = parser.parse(svg)

        shapes = [e for e in diagram.elements if isinstance(e, Shape)]
        assert len(shapes) == 3

        # Find shapes by id
        db_shape = next(s for s in shapes if s.id == "db")
        user_shape = next(s for s in shapes if s.id == "user")
        svc_shape = next(s for s in shapes if s.id == "svc")

        assert db_shape.semantic_type == SemanticType.DATABASE.value
        assert db_shape.semantic_confidence == 0.9
        assert user_shape.semantic_type == SemanticType.PERSON.value
        assert svc_shape.semantic_type == SemanticType.SERVICE.value

    def test_text_association(self):
        """Test text label association with shapes."""
        svg = '''
        <svg xmlns="http://www.w3.org/2000/svg">
            <rect id="r1" x="0" y="0" width="100" height="50"/>
            <text x="20" y="30">Label Text</text>
        </svg>
        '''

        parser = SVGParser()
        diagram = parser.parse(svg)

        shapes = [e for e in diagram.elements if isinstance(e, Shape)]
        assert len(shapes) == 1
        assert shapes[0].label == "Label Text"

    def test_text_element_parsing(self):
        """Test standalone text element."""
        svg = '''
        <svg xmlns="http://www.w3.org/2000/svg">
            <text id="txt1" x="50" y="50" font-size="16">Important Note</text>
        </svg>
        '''

        parser = SVGParser()
        diagram = parser.parse(svg)

        texts = [e for e in diagram.elements if isinstance(e, Text)]
        assert len(texts) == 1
        assert texts[0].content == "Important Note"
        assert texts[0].position.x == 50
        assert texts[0].position.y == 50

    def test_group_parsing(self):
        """Test SVG group parsing."""
        svg = '''
        <svg xmlns="http://www.w3.org/2000/svg">
            <g id="system1" data-label="System">
                <rect id="comp1" x="10" y="10" width="80" height="40"/>
                <rect id="comp2" x="100" y="10" width="80" height="40"/>
            </g>
        </svg>
        '''

        parser = SVGParser()
        diagram = parser.parse(svg)

        groups = [e for e in diagram.elements if isinstance(e, Group)]
        assert len(groups) == 1
        assert groups[0].id == "system1"
        assert groups[0].label == "System"
        assert len(groups[0].children) == 2
        assert "comp1" in groups[0].children
        assert "comp2" in groups[0].children

    def test_style_parsing(self):
        """Test SVG style attributes."""
        svg = '''
        <svg xmlns="http://www.w3.org/2000/svg">
            <rect id="r1" x="0" y="0" width="100" height="50"
                  fill="#E3F2FD" stroke="#1976D2" stroke-width="2"/>
            <rect id="r2" x="120" y="0" width="100" height="50"
                  fill="none" stroke="#4CAF50" stroke-width="3" stroke-dasharray="5,5"/>
        </svg>
        '''

        parser = SVGParser()
        diagram = parser.parse(svg)

        shapes = [e for e in diagram.elements if isinstance(e, Shape)]
        assert len(shapes) == 2

        r1 = next(s for s in shapes if s.id == "r1")
        assert r1.style.fill_color == "#E3F2FD"
        assert r1.style.stroke_color == "#1976D2"
        assert r1.style.stroke_width == 2.0
        assert r1.style.stroke_style == "solid"

        r2 = next(s for s in shapes if s.id == "r2")
        assert r2.style.fill_color is None  # fill="none"
        assert r2.style.stroke_color == "#4CAF50"
        assert r2.style.stroke_width == 3.0
        assert r2.style.stroke_style == "dashed"

    def test_empty_svg(self):
        """Test parsing empty SVG."""
        svg = '<svg xmlns="http://www.w3.org/2000/svg"></svg>'

        parser = SVGParser()
        diagram = parser.parse(svg)

        assert len(diagram.elements) == 0

    def test_nested_groups(self):
        """Test nested groups."""
        svg = '''
        <svg xmlns="http://www.w3.org/2000/svg">
            <g id="outer" data-label="Outer">
                <rect id="r1" x="10" y="10" width="50" height="30"/>
                <g id="inner" data-label="Inner">
                    <rect id="r2" x="20" y="50" width="40" height="25"/>
                </g>
            </g>
        </svg>
        '''

        parser = SVGParser()
        diagram = parser.parse(svg)

        groups = [e for e in diagram.elements if isinstance(e, Group)]
        # Both outer and inner groups should be parsed
        assert len(groups) == 2

        outer = next((g for g in groups if g.id == "outer"), None)
        inner = next((g for g in groups if g.id == "inner"), None)

        assert outer is not None
        assert inner is not None


class TestSVGTransforms:
    """Test SVG transform support."""

    def test_translate_transform(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg">
            <rect id="r1" x="0" y="0" width="100" height="50" transform="translate(50, 100)"/>
        </svg>'''
        parser = SVGParser()
        diagram = parser.parse(svg)

        shapes = diagram.get_shapes()
        assert len(shapes) == 1
        assert shapes[0].position.x == 50.0
        assert shapes[0].position.y == 100.0

    def test_scale_transform(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg">
            <rect id="r1" x="10" y="10" width="100" height="50" transform="scale(2)"/>
        </svg>'''
        parser = SVGParser()
        diagram = parser.parse(svg)

        shapes = diagram.get_shapes()
        assert len(shapes) == 1
        assert shapes[0].position.x == 20.0
        assert shapes[0].position.y == 20.0
        assert shapes[0].size.width == 200.0
        assert shapes[0].size.height == 100.0

    def test_combined_transform(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg">
            <rect id="r1" x="0" y="0" width="100" height="50" transform="translate(10, 20) scale(2)"/>
        </svg>'''
        parser = SVGParser()
        diagram = parser.parse(svg)

        shapes = diagram.get_shapes()
        assert len(shapes) == 1
        assert shapes[0].size.width == 200.0

    def test_group_transform_inheritance(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg">
            <g transform="translate(100, 100)">
                <rect id="r1" x="0" y="0" width="50" height="50"/>
            </g>
        </svg>'''
        parser = SVGParser()
        diagram = parser.parse(svg)

        shapes = diagram.get_shapes()
        assert len(shapes) == 1
        assert shapes[0].position.x == 100.0
        assert shapes[0].position.y == 100.0


class TestSVGPathSupport:
    """Test SVG path element support."""

    def test_simple_path_rectangle(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg">
            <path id="p1" d="M 0 0 L 100 0 L 100 50 L 0 50 Z"/>
        </svg>'''
        parser = SVGParser()
        diagram = parser.parse(svg)

        shapes = diagram.get_shapes()
        assert len(shapes) == 1
        assert shapes[0].shape_type == 'rectangle'
        assert shapes[0].size.width == 100.0
        assert shapes[0].size.height == 50.0

    def test_path_with_relative_commands(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg">
            <path id="p1" d="M 10 10 l 100 0 l 0 50 l -100 0 z"/>
        </svg>'''
        parser = SVGParser()
        diagram = parser.parse(svg)

        shapes = diagram.get_shapes()
        assert len(shapes) == 1
        assert shapes[0].size.width == 100.0

    def test_path_with_h_v_commands(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg">
            <path id="p1" d="M 0 0 H 100 V 50 H 0 Z"/>
        </svg>'''
        parser = SVGParser()
        diagram = parser.parse(svg)

        shapes = diagram.get_shapes()
        assert len(shapes) == 1
        assert shapes[0].size.width == 100.0
        assert shapes[0].size.height == 50.0


class TestSVGPathCurves:
    """Regression tests: curve commands must not desync the path tokenizer."""

    def test_curve_then_line_no_desync(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg">
            <path id="p1" d="M 0 0 c 10 20 30 40 50 60 l 50 0 Z"/>
        </svg>'''
        parser = SVGParser()
        diagram = parser.parse(svg)

        shapes = diagram.get_shapes()
        assert len(shapes) == 1
        assert shapes[0].size.width == 100.0
        assert shapes[0].size.height == 60.0
        assert any('curve' in w for w in parser.warnings)

    def test_curve_control_points_in_bbox(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg">
            <path id="p1" d="M 0 0 C 0 100 100 100 100 0 Z"/>
        </svg>'''
        parser = SVGParser()
        diagram = parser.parse(svg)

        shapes = diagram.get_shapes()
        assert len(shapes) == 1
        assert shapes[0].size.width == 100.0
        assert shapes[0].size.height == 100.0

    def test_implicit_curve_repetition(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg">
            <path id="p1" d="M 0 0 C 0 50 50 50 50 0 100 -50 150 -50 150 0"/>
        </svg>'''
        parser = SVGParser()
        diagram = parser.parse(svg)

        shapes = diagram.get_shapes()
        assert len(shapes) == 1
        assert shapes[0].position.y == -50.0
        assert shapes[0].size.width == 150.0
        assert shapes[0].size.height == 100.0

    def test_arc_command_consumes_seven_operands(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg">
            <path id="p1" d="M 0 0 A 50 50 0 0 1 100 0 L 100 40 L 0 40 Z"/>
        </svg>'''
        parser = SVGParser()
        diagram = parser.parse(svg)

        shapes = diagram.get_shapes()
        assert len(shapes) == 1
        assert shapes[0].size.width == 100.0
        assert shapes[0].size.height == 40.0

    def test_quadratic_and_smooth_commands(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg">
            <path id="p1" d="M 0 0 Q 50 80 100 0 T 200 0 Z"/>
        </svg>'''
        parser = SVGParser()
        diagram = parser.parse(svg)

        shapes = diagram.get_shapes()
        assert len(shapes) == 1
        assert shapes[0].size.width == 200.0
        assert shapes[0].size.height == 80.0

    def test_real_llm_proxy_component_fixture(self):
        svg_path = Path(__file__).parent / "data" / "real" / "llm_proxy_component.svg"

        parser = SVGParser()
        diagram = parser.parse(svg_path.read_text())

        assert len(diagram.elements) > 0
        assert any('curve' in w for w in parser.warnings)


class TestSVGLineElements:
    """Test SVG line and polyline elements."""

    def test_line_element(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg">
            <rect id="r1" x="0" y="0" width="50" height="50"/>
            <rect id="r2" x="100" y="0" width="50" height="50"/>
            <line id="l1" x1="50" y1="25" x2="100" y2="25"/>
        </svg>'''
        parser = SVGParser()
        diagram = parser.parse(svg)

        connections = diagram.get_connections()
        assert len(connections) == 1
        assert connections[0].from_id == 'r1'
        assert connections[0].to_id == 'r2'

    def test_polyline_element(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg">
            <rect id="r1" x="0" y="0" width="50" height="50"/>
            <rect id="r2" x="100" y="0" width="50" height="50"/>
            <rect id="r3" x="200" y="0" width="50" height="50"/>
            <polyline points="50,25 100,25 150,25 200,25"/>
        </svg>'''
        parser = SVGParser()
        diagram = parser.parse(svg)

        connections = diagram.get_connections()
        assert len(connections) >= 2


class TestSVGCLI:
    """Test SVG CLI integration."""

    def test_auto_detect_svg_xml(self):
        """Test auto-detection of SVG with XML header."""
        svg_content = '<?xml version="1.0"?><svg></svg>'
        format_type = detect_input_format(svg_content)
        assert format_type == "svg"

    def test_auto_detect_svg_no_header(self):
        """Test auto-detection of SVG without XML header."""
        svg_content = '<svg xmlns="http://www.w3.org/2000/svg"></svg>'
        format_type = detect_input_format(svg_content)
        assert format_type == "svg"

    def test_auto_detect_svg_with_whitespace(self):
        """Test auto-detection with leading whitespace."""
        svg_content = '  \n  <?xml version="1.0"?><svg></svg>'
        format_type = detect_input_format(svg_content)
        assert format_type == "svg"


class TestSVGTestData:
    """Test with actual SVG test data files."""

    def test_simple_shapes_svg(self):
        """Test parsing simple shapes SVG file."""
        svg_path = Path(__file__).parent / "data" / "svg" / "simple_shapes.svg"
        if not svg_path.exists():
            pytest.skip("Test data file not found")

        with open(svg_path) as f:
            svg_content = f.read()

        parser = SVGParser()
        diagram = parser.parse(svg_content)

        shapes = [e for e in diagram.elements if isinstance(e, Shape)]
        # Should have rect, circle, ellipse, polygon, rect (5 shapes)
        assert len(shapes) >= 4

        # Check some shapes have labels
        labeled = [s for s in shapes if s.label]
        assert len(labeled) >= 3

    def test_architecture_diagram_svg(self):
        """Test parsing architecture diagram with semantic hints."""
        svg_path = Path(__file__).parent / "data" / "svg" / "architecture_diagram.svg"
        if not svg_path.exists():
            pytest.skip("Test data file not found")

        with open(svg_path) as f:
            svg_content = f.read()

        parser = SVGParser()
        diagram = parser.parse(svg_content)

        shapes = [e for e in diagram.elements if isinstance(e, Shape)]
        # Should have several shapes with semantic types
        assert len(shapes) >= 6

        # Check semantic types are parsed
        databases = [s for s in shapes if s.semantic_type == SemanticType.DATABASE.value]
        persons = [s for s in shapes if s.semantic_type == SemanticType.PERSON.value]
        services = [s for s in shapes if s.semantic_type == SemanticType.SERVICE.value]

        assert len(databases) >= 1
        assert len(persons) >= 1
        assert len(services) >= 1

    def test_grouped_diagram_svg(self):
        """Test parsing grouped diagram."""
        svg_path = Path(__file__).parent / "data" / "svg" / "grouped_diagram.svg"
        if not svg_path.exists():
            pytest.skip("Test data file not found")

        with open(svg_path) as f:
            svg_content = f.read()

        parser = SVGParser()
        diagram = parser.parse(svg_content)

        groups = [e for e in diagram.elements if isinstance(e, Group)]
        # Should have at least 2 groups (system_boundary and data_layer)
        assert len(groups) >= 2

        # Check groups have children
        for group in groups:
            assert len(group.children) > 0


class TestSVGEndToEnd:
    """Test end-to-end SVG to output format conversion."""

    def test_svg_to_plantuml(self):
        """Test SVG → IR → PlantUML."""
        svg = '''
        <svg xmlns="http://www.w3.org/2000/svg">
            <rect id="svc1" x="10" y="10" width="100" height="50"
                  data-semantic="service" data-label="API"/>
            <ellipse id="db1" cx="200" cy="35" rx="60" ry="30"
                     data-semantic="database" data-label="PostgreSQL"/>
        </svg>
        '''

        from diacea.generators import PlantUMLGenerator

        parser = SVGParser()
        diagram = parser.parse(svg)

        generator = PlantUMLGenerator()
        output = generator.generate(diagram)

        assert output.startswith("@startuml")
        assert output.endswith("@enduml")
        assert "API" in output or "svc1" in output
        assert "PostgreSQL" in output or "db1" in output

    def test_svg_to_mermaid(self):
        """Test SVG → IR → Mermaid."""
        svg = '''
        <svg xmlns="http://www.w3.org/2000/svg">
            <rect id="comp1" x="0" y="0" width="100" height="50"
                  data-label="Component A"/>
            <rect id="comp2" x="150" y="0" width="100" height="50"
                  data-label="Component B"/>
        </svg>
        '''

        from diacea.generators import MermaidGenerator

        parser = SVGParser()
        diagram = parser.parse(svg)

        generator = MermaidGenerator()
        output = generator.generate(diagram)

        # Can be flowchart, graph, or C4Context
        assert "flowchart" in output or "graph" in output or "C4Context" in output
        assert len(output.split("\n")) > 2

    def test_svg_to_d2(self):
        """Test SVG → IR → D2."""
        svg = '''
        <svg xmlns="http://www.w3.org/2000/svg">
            <rect id="svc" x="10" y="10" width="120" height="60"
                  data-semantic="service" data-label="Web Service"/>
        </svg>
        '''

        from diacea.generators import D2Generator

        parser = SVGParser()
        diagram = parser.parse(svg)

        generator = D2Generator()
        output = generator.generate(diagram)

        assert len(output) > 0
        assert ":" in output  # D2 syntax
