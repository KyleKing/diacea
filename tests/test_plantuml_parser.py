"""Tests for the PlantUML parser."""

import json
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

from diacea.generators import C4PlantUMLGenerator, PlantUMLGenerator
from diacea.ir import Connection, Diagram, Group, SemanticType, Shape
from diacea.parsers import ExcalidrawParser
from diacea.parsers.plantuml import PlantUMLParser, is_c4_plantuml, is_plantuml

DATA_DIR = Path(__file__).parent / 'data'
PLANTUML_DIR = DATA_DIR / 'plantuml'


def _parse(text: str) -> tuple[Diagram, PlantUMLParser]:
    parser = PlantUMLParser()
    return parser.parse(text), parser


def _wrap(body: str) -> str:
    return f'@startuml\n{textwrap.dedent(body).strip()}\n@enduml'


def _shape(diagram: Diagram, elem_id: str) -> Shape:
    element = diagram.get_element(elem_id)
    assert isinstance(element, Shape), f'{elem_id} is not a Shape: {element}'
    return element


def _only_connection(diagram: Diagram) -> Connection:
    connections = diagram.get_connections()
    assert len(connections) == 1
    return connections[0]


@pytest.fixture
def excalidraw_diagram() -> Diagram:
    data = json.loads((DATA_DIR / 'excalidraw.json').read_text())
    return ExcalidrawParser().parse(data)


class TestSniffing:
    def test_is_plantuml(self):
        assert is_plantuml('@startuml\nrectangle a\n@enduml')

    def test_is_not_plantuml(self):
        assert not is_plantuml('digraph G { a -> b }')

    def test_is_c4_by_include(self):
        content = '@startuml\n!include <C4/C4_Container>\n@enduml'
        assert is_c4_plantuml(content)

    def test_is_c4_by_include_url(self):
        content = (
            '@startuml\n!include https://raw.githubusercontent.com/'
            'plantuml-stdlib/C4-PlantUML/master/C4_Component.puml\n@enduml'
        )
        assert is_c4_plantuml(content)

    def test_is_c4_by_macros(self):
        content = '@startuml\nPerson(u, "User")\nRel(u, s, "uses")\n@enduml'
        assert is_c4_plantuml(content)

    def test_plain_plantuml_is_not_c4(self):
        content = _wrap('rectangle "Box" as b\nactor "User" as u\nu --> b')
        assert not is_c4_plantuml(content)


class TestEnvelope:
    def test_diagram_name(self):
        diagram, _ = _parse('@startuml my_diagram\nrectangle a\n@enduml')
        assert diagram.name == 'my_diagram'

    def test_no_name(self):
        diagram, _ = _parse('@startuml\nrectangle a\n@enduml')
        assert diagram.name is None

    def test_missing_startuml_raises(self):
        with pytest.raises(ValueError, match='@startuml'):
            PlantUMLParser().parse('rectangle a')

    def test_non_string_input_raises(self):
        with pytest.raises(ValueError, match='string'):
            PlantUMLParser().parse({'not': 'plantuml'})

    def test_content_outside_envelope_ignored(self):
        text = 'preamble text\n@startuml\nrectangle a\n@enduml\ntrailing text'
        diagram, parser = _parse(text)
        assert len(diagram.get_shapes()) == 1
        assert not parser.warnings


class TestElementDeclarations:
    @pytest.mark.parametrize(
        'keyword',
        [
            'actor',
            'agent',
            'card',
            'cloud',
            'component',
            'database',
            'ellipse',
            'folder',
            'frame',
            'hexagon',
            'node',
            'package',
            'person',
            'queue',
            'rectangle',
            'storage',
            'usecase',
        ],
    )
    def test_each_keyword(self, keyword):
        diagram, parser = _parse(_wrap(f'{keyword} "Widget" as w1'))
        shape = _shape(diagram, 'w1')
        assert shape.label == 'Widget'
        assert not parser.warnings

    @pytest.mark.parametrize(
        ('keyword', 'semantic'),
        [
            ('actor', SemanticType.PERSON),
            ('cloud', SemanticType.CLOUD),
            ('component', SemanticType.COMPONENT),
            ('database', SemanticType.DATABASE),
            ('node', SemanticType.SERVER),
            ('person', SemanticType.PERSON),
            ('queue', SemanticType.QUEUE),
            ('storage', SemanticType.STORAGE),
        ],
    )
    def test_explicit_keyword_semantics(self, keyword, semantic):
        diagram, _ = _parse(_wrap(f'{keyword} "Widget" as w1'))
        shape = _shape(diagram, 'w1')
        assert shape.semantic_type == semantic
        assert shape.semantic_confidence >= 0.9

    def test_generic_rectangle_label_inference(self):
        diagram, _ = _parse(_wrap('rectangle "Postgres Database" as db1'))
        shape = _shape(diagram, 'db1')
        assert shape.semantic_type == SemanticType.DATABASE

    def test_bare_id_form(self):
        diagram, _ = _parse(_wrap('rectangle box1'))
        shape = _shape(diagram, 'box1')
        assert shape.label == 'box1'

    def test_derived_id_form(self):
        diagram, _ = _parse(_wrap('rectangle "Some Label"'))
        shapes = diagram.get_shapes()
        assert len(shapes) == 1
        assert shapes[0].label == 'Some Label'
        assert shapes[0].id == 'Some_Label'

    def test_label_unescaping(self):
        diagram, _ = _parse(_wrap(r'rectangle "Line1\nLine2" as multi'))
        assert _shape(diagram, 'multi').label == 'Line1\nLine2'

    def test_stereotype_and_color_tolerated(self):
        diagram, parser = _parse(_wrap('rectangle "Box" as b <<external>> #lightblue'))
        assert _shape(diagram, 'b').label == 'Box'
        assert not parser.warnings


class TestBlocks:
    def test_block_creates_group(self):
        diagram, _ = _parse(
            _wrap("""
            rectangle "Platform" as plat {
              component "API" as api
              database "DB" as db
            }
        """)
        )
        groups = diagram.get_groups()
        assert len(groups) == 1
        group = groups[0]
        assert group.id == 'plat'
        assert group.label == 'Platform'
        assert group.children == ['api', 'db']

    def test_nested_blocks(self):
        diagram, _ = _parse(
            _wrap("""
            package "Outer" as outer {
              rectangle "Inner" as inner {
                component "Leaf" as leaf
              }
              component "Sibling" as sib
            }
        """)
        )
        outer = diagram.get_element('outer')
        inner = diagram.get_element('inner')
        assert isinstance(outer, Group)
        assert isinstance(inner, Group)
        assert outer.children == ['inner', 'sib']
        assert inner.children == ['leaf']

    def test_elements_after_block_not_children(self):
        diagram, _ = _parse(
            _wrap("""
            rectangle "Grp" as grp {
              component "In" as inside
            }
            component "Out" as outside
        """)
        )
        group = diagram.get_element('grp')
        assert isinstance(group, Group)
        assert group.children == ['inside']
        assert isinstance(diagram.get_element('outside'), Shape)


class TestRelationships:
    @pytest.mark.parametrize('arrow', ['->', '-->'])
    def test_directed(self, arrow):
        diagram, _ = _parse(_wrap(f'rectangle a\nrectangle b\na {arrow} b'))
        conn = _only_connection(diagram)
        assert (conn.from_id, conn.to_id) == ('a', 'b')
        assert conn.connection_type == 'directed'

    def test_dashed(self):
        diagram, _ = _parse(_wrap('rectangle a\nrectangle b\na ..> b'))
        conn = _only_connection(diagram)
        assert conn.style.stroke_style == 'dashed'
        assert conn.connection_type == 'directed'

    @pytest.mark.parametrize('arrow', ['-', '--'])
    def test_undirected(self, arrow):
        diagram, _ = _parse(_wrap(f'rectangle a\nrectangle b\na {arrow} b'))
        assert _only_connection(diagram).connection_type == 'undirected'

    def test_reversed(self):
        diagram, _ = _parse(_wrap('rectangle a\nrectangle b\na <-- b'))
        conn = _only_connection(diagram)
        assert (conn.from_id, conn.to_id) == ('b', 'a')
        assert conn.connection_type == 'directed'

    def test_bidirectional(self):
        diagram, _ = _parse(_wrap('rectangle a\nrectangle b\na <--> b'))
        assert _only_connection(diagram).connection_type == 'bidirectional'

    def test_bare_label(self):
        diagram, _ = _parse(_wrap('rectangle a\nrectangle b\na --> b : sends data'))
        assert _only_connection(diagram).label == 'sends data'

    def test_quoted_label(self):
        diagram, _ = _parse(_wrap('rectangle a\nrectangle b\na --> b : "reads/writes"'))
        assert _only_connection(diagram).label == 'reads/writes'

    @pytest.mark.parametrize(
        ('arrow', 'direction'),
        [
            ('-down->', 'down'),
            ('-d->', 'down'),
            ('-left->', 'left'),
            ('-l->', 'left'),
            ('-right->', 'right'),
            ('-up->', 'up'),
            ('.d.>', 'down'),
        ],
    )
    def test_direction_hints(self, arrow, direction):
        diagram, parser = _parse(_wrap(f'rectangle a\nrectangle b\na {arrow} b'))
        conn = _only_connection(diagram)
        assert conn.metadata['direction_hint'] == direction
        assert not parser.warnings

    def test_quoted_endpoints_resolve_to_declared_ids(self):
        diagram, _ = _parse(
            _wrap("""
            rectangle "Some Label" as s1
            rectangle "Other" as o1
            "Some Label" --> "Other"
        """)
        )
        conn = _only_connection(diagram)
        assert (conn.from_id, conn.to_id) == ('s1', 'o1')
        assert len(diagram.get_shapes()) == 2

    def test_undeclared_endpoints_auto_created(self):
        diagram, _ = _parse(_wrap('alpha --> beta'))
        assert isinstance(diagram.get_element('alpha'), Shape)
        assert isinstance(diagram.get_element('beta'), Shape)


class TestSkippedDirectives:
    def test_skinparam_single_line(self):
        diagram, parser = _parse(_wrap('skinparam shadowing false\nrectangle a'))
        assert len(diagram.get_shapes()) == 1
        assert any('skinparam' in w for w in parser.warnings)

    def test_skinparam_block(self):
        diagram, parser = _parse(
            _wrap("""
            skinparam rectangle {
              BackgroundColor white
              BorderColor black
            }
            rectangle a
        """)
        )
        assert len(diagram.get_shapes()) == 1
        assert any('skinparam' in w for w in parser.warnings)

    @pytest.mark.parametrize(
        'directive',
        [
            'title My Title',
            'caption A caption',
            'header Page header',
            'footer Page footer',
            'hide stereotype',
            'show members',
            '!include other.puml',
            '!define MACRO value',
        ],
    )
    def test_directives_warn(self, directive):
        diagram, parser = _parse(_wrap(f'{directive}\nrectangle a'))
        assert len(diagram.get_shapes()) == 1
        assert len(parser.warnings) == 1
        assert parser.warnings[0].startswith('Line 2:')

    def test_direction_recorded_without_warning(self):
        diagram, parser = _parse(_wrap('left to right direction\nrectangle a'))
        assert diagram.metadata['direction'] == 'left_to_right'
        assert not parser.warnings

    def test_unknown_line_warns_with_line_number(self):
        diagram, parser = _parse('@startuml\nrectangle a\ntotally ! bogus line\n@enduml')
        assert len(diagram.get_shapes()) == 1
        assert any(w.startswith('Line 3:') for w in parser.warnings)

    def test_comments_ignored_silently(self):
        diagram, parser = _parse(
            _wrap("""
            ' single line comment
            /' block
            comment '/
            rectangle a
        """)
        )
        assert len(diagram.get_shapes()) == 1
        assert not parser.warnings


class TestSequenceRejection:
    @pytest.mark.parametrize(
        'line',
        [
            'participant Alice',
            'activate Alice',
            'alt success case',
        ],
    )
    def test_sequence_syntax_raises(self, line):
        with pytest.raises(ValueError, match='sequence diagram'):
            PlantUMLParser().parse(_wrap(line))


class TestActivityRejection:
    @pytest.mark.parametrize(
        'line',
        [
            '(*) --> "Step 0: Select release manager"',
            ':Do the thing;',
            'if (72 hours or 3 yes votes?) then',
            'start',
            'stop',
            'while (more items?)',
        ],
    )
    def test_activity_syntax_raises(self, line):
        with pytest.raises(ValueError, match='activity diagrams are not supported'):
            PlantUMLParser().parse(_wrap(line))

    def test_fineract_fixture_raises(self):
        content = (DATA_DIR / 'real' / 'fineract_release_process.puml').read_text()
        with pytest.raises(ValueError, match='activity diagrams are not supported'):
            PlantUMLParser().parse(content)


class TestC4:
    @pytest.mark.parametrize(
        ('macro', 'semantic'),
        [
            ('Person(x, "Label")', SemanticType.PERSON),
            ('System(x, "Label")', SemanticType.SYSTEM),
            ('Container(x, "Label")', SemanticType.CONTAINER),
            ('ContainerDb(x, "Label")', SemanticType.DATABASE),
            ('Component(x, "Label")', SemanticType.COMPONENT),
            ('ComponentDb(x, "Label")', SemanticType.DATABASE),
        ],
    )
    def test_element_macros(self, macro, semantic):
        diagram, parser = _parse(_wrap(macro))
        shape = _shape(diagram, 'x')
        assert shape.label == 'Label'
        assert shape.semantic_type == semantic
        assert shape.semantic_confidence == 1.0
        assert not parser.warnings

    def test_container_technology_metadata(self):
        diagram, _ = _parse(_wrap('Container(api, "API", "FastAPI")'))
        assert _shape(diagram, 'api').metadata['technology'] == 'FastAPI'

    def test_external_variant(self):
        diagram, _ = _parse(_wrap('System_Ext(pay, "Payments")'))
        shape = _shape(diagram, 'pay')
        assert shape.semantic_type == SemanticType.SYSTEM
        assert shape.metadata['external'] is True

    def test_system_boundary_group(self):
        diagram, _ = _parse(
            _wrap("""
            System_Boundary(shop, "Web Shop") {
              Container(web, "Web App")
              ContainerDb(db, "Orders DB")
            }
        """)
        )
        groups = diagram.get_groups()
        assert len(groups) == 1
        assert groups[0].id == 'shop'
        assert groups[0].label == 'Web Shop'
        assert groups[0].children == ['web', 'db']

    def test_rel(self):
        diagram, _ = _parse(
            _wrap("""
            Person(u, "User")
            System(s, "System")
            Rel(u, s, "Uses")
        """)
        )
        conn = _only_connection(diagram)
        assert (conn.from_id, conn.to_id) == ('u', 's')
        assert conn.label == 'Uses'
        assert conn.connection_type == 'directed'

    @pytest.mark.parametrize(
        ('macro', 'direction'),
        [
            ('Rel_D', 'down'),
            ('Rel_U', 'up'),
            ('Rel_L', 'left'),
            ('Rel_R', 'right'),
            ('Rel_Down', 'down'),
        ],
    )
    def test_rel_direction_variants(self, macro, direction):
        diagram, _ = _parse(_wrap(f'System(a, "A")\nSystem(b, "B")\n{macro}(a, b, "x")'))
        assert _only_connection(diagram).metadata['direction_hint'] == direction

    def test_layout_macros_skipped_silently(self):
        diagram, parser = _parse(_wrap('LAYOUT_WITH_LEGEND()\nSystem(s, "S")'))
        assert not parser.warnings

    def test_unknown_macro_warns(self):
        _, parser = _parse(_wrap('SHOW_FLOATING_LEGEND()'))
        assert any('SHOW_FLOATING_LEGEND' in w for w in parser.warnings)

    def test_c4_include_not_warned_and_flagged(self):
        diagram, parser = _parse(_wrap('!include <C4/C4_Container>\nSystem(s, "S")'))
        assert diagram.metadata['c4_plantuml'] is True
        assert not parser.warnings

    def test_c4_fixture(self):
        diagram, parser = _parse((PLANTUML_DIR / 'c4_container.puml').read_text())
        assert not parser.warnings
        shapes = {s.id: s for s in diagram.get_shapes()}
        assert set(shapes) == {'customer', 'payments', 'web', 'api', 'db', 'bus'}
        assert shapes['db'].semantic_type == SemanticType.DATABASE
        assert shapes['bus'].semantic_type == SemanticType.QUEUE
        group = diagram.get_groups()[0]
        assert group.children == ['web', 'api', 'db', 'bus']
        assert len(diagram.get_connections()) == 5


class TestLayoutSynthesis:
    def test_metadata_flag(self):
        diagram, _ = _parse(_wrap('rectangle a'))
        assert diagram.metadata['synthesized_layout'] is True

    def test_topological_layers_top_to_bottom(self):
        diagram, _ = _parse(_wrap('rectangle a\nrectangle b\nrectangle c\na --> b\nb --> c'))
        pos = {s.id: s.position for s in diagram.get_shapes()}
        assert pos['a'].y < pos['b'].y < pos['c'].y

    def test_left_to_right_direction(self):
        diagram, _ = _parse(
            _wrap("""
            left to right direction
            rectangle a
            rectangle b
            a --> b
        """)
        )
        pos = {s.id: s.position for s in diagram.get_shapes()}
        assert pos['a'].x < pos['b'].x

    def test_siblings_do_not_overlap(self):
        diagram, _ = _parse(_wrap('rectangle a\nrectangle b\nrectangle c\na --> b\na --> c'))
        pos = {s.id: (s.position.x, s.position.y) for s in diagram.get_shapes()}
        assert len(set(pos.values())) == 3

    def test_cycle_does_not_crash(self):
        diagram, _ = _parse(_wrap('rectangle a\nrectangle b\na --> b\nb --> a'))
        assert len(diagram.get_shapes()) == 2

    def test_group_bounds_contain_children(self):
        diagram, _ = _parse(
            _wrap("""
            rectangle "Grp" as grp {
              rectangle a
              rectangle b
            }
        """)
        )
        group = diagram.get_element('grp')
        assert isinstance(group, Group)
        for shape in diagram.get_shapes():
            assert group.position.x <= shape.position.x
            assert group.position.y <= shape.position.y
            assert shape.position.x + shape.size.width <= group.position.x + group.size.width
            assert shape.position.y + shape.size.height <= group.position.y + group.size.height


class TestRoundTrip:
    def test_basic_plantuml_round_trip(self, excalidraw_diagram):
        generator = PlantUMLGenerator()
        first = generator.generate(excalidraw_diagram)
        parser = PlantUMLParser()
        reparsed = parser.parse(first)
        second = generator.generate(reparsed)
        assert second == first
        assert not parser.warnings

    def test_c4_plantuml_round_trip(self, excalidraw_diagram):
        generator = C4PlantUMLGenerator()
        first = generator.generate(excalidraw_diagram)
        parser = PlantUMLParser()
        reparsed = parser.parse(first)
        second = generator.generate(reparsed)
        assert second == first
        assert not parser.warnings

    def test_c4_round_trip_preserves_structure(self, excalidraw_diagram):
        first = C4PlantUMLGenerator().generate(excalidraw_diagram)
        reparsed = PlantUMLParser().parse(first)
        assert is_c4_plantuml(first)
        assert reparsed.metadata['c4_plantuml'] is True
        original_groups = excalidraw_diagram.get_groups()
        assert len(reparsed.get_groups()) == len(original_groups)
        assert len(reparsed.get_connections()) == len(excalidraw_diagram.get_connections())


class TestArchitectureFixture:
    @pytest.fixture
    def fixture_result(self):
        parser = PlantUMLParser()
        diagram = parser.parse((PLANTUML_DIR / 'architecture.puml').read_text())
        return diagram, parser

    def test_parses_all_elements(self, fixture_result):
        diagram, _ = fixture_result
        assert len(diagram.get_shapes()) == 11
        assert len(diagram.get_groups()) == 1
        assert len(diagram.get_connections()) == 12

    def test_group_membership(self, fixture_result):
        diagram, _ = fixture_result
        group = diagram.get_element('platform')
        assert isinstance(group, Group)
        assert group.children == [
            'frontend',
            'gateway',
            'orders',
            'billing',
            'events',
            'orders_db',
        ]

    def test_semantics(self, fixture_result):
        diagram, _ = fixture_result
        assert _shape(diagram, 'customer').semantic_type == SemanticType.PERSON
        assert _shape(diagram, 'orders_db').semantic_type == SemanticType.DATABASE
        assert _shape(diagram, 'events').semantic_type == SemanticType.QUEUE
        assert _shape(diagram, 'blobs').semantic_type == SemanticType.STORAGE
        assert _shape(diagram, 'cdn').semantic_type == SemanticType.CLOUD

    def test_direction_and_name(self, fixture_result):
        diagram, _ = fixture_result
        assert diagram.name == 'web_architecture'
        assert diagram.metadata['direction'] == 'left_to_right'

    def test_only_expected_warnings(self, fixture_result):
        _, parser = fixture_result
        assert len(parser.warnings) == 2
        assert 'skinparam' in parser.warnings[0]
        assert 'title' in parser.warnings[1]

    def test_dashed_relationships(self, fixture_result):
        diagram, _ = fixture_result
        dashed = [c for c in diagram.get_connections() if c.style.stroke_style == 'dashed']
        assert len(dashed) == 2
        assert {c.label for c in dashed} == {'publishes'}


@pytest.mark.skipif(shutil.which('plantuml') is None, reason='plantuml binary not installed')
class TestPlantUMLBinary:
    @pytest.mark.parametrize('fixture', ['architecture.puml', 'c4_container.puml'])
    def test_fixtures_are_valid_plantuml(self, fixture):
        result = subprocess.run(
            ['plantuml', '-checkonly', str(PLANTUML_DIR / fixture)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
