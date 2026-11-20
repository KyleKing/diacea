"""Tests for the format registry, the public conversion API, and semantic hints."""

import json
import warnings

import pytest

import diacea
from diacea.formats import (
    INPUT_FORMATS,
    OUTPUT_FORMATS,
    FormatError,
    apply_hints,
    convert,
    detect_input_format,
    input_format_for_path,
    output_format_for_path,
    parse_diagram,
    parse_file,
    render_diagram,
)
from diacea.ir import SemanticType

from .configuration import TEST_DATA_DIR

MERMAID = 'flowchart LR\n    web[Web App] --> db[(Orders DB)]\n'


class TestDetection:
    @pytest.mark.parametrize(
        ('content', 'expected'),
        [
            ('<svg xmlns="http://www.w3.org/2000/svg"></svg>', 'svg'),
            ('@startuml\nrectangle a\n@enduml', 'plantuml'),
            ('digraph { a -> b }', 'graphviz'),
            ('graph TD\n    A --> B', 'mermaid'),
            ('graph G {\n    a -- b\n}', 'graphviz'),
            ('sequenceDiagram\n    A->>B: hi', 'mermaid'),
            ('C4Context\n    Person(a, "A")', 'mermaid'),
            ('{"elements": []}', 'excalidraw'),
            ('{"tldrawFileFormatVersion": 1, "records": []}', 'tldraw'),
            ('a -> b: uses\n', 'd2'),
        ],
    )
    def test_detects_from_content(self, content, expected):
        assert detect_input_format(content) == expected

    def test_extension_decides_when_content_has_no_signature(self):
        assert detect_input_format('web: Web App\n', filename='arch.d2') == 'd2'

    def test_content_signature_beats_extension(self):
        assert detect_input_format('digraph { a -> b }', filename='misnamed.mmd') == 'graphviz'

    def test_unknown_content_lists_supported_formats(self):
        with pytest.raises(ValueError, match='supported: d2, excalidraw, graphviz'):
            detect_input_format('just some prose')

    @pytest.mark.parametrize(
        ('name', 'expected'),
        [('a.excalidraw', 'excalidraw'), ('note.excalidraw.md', 'obsidian'), ('a.gv', 'graphviz'), ('a.txt', None)],
    )
    def test_input_format_for_path(self, name, expected):
        assert input_format_for_path(name) == expected

    @pytest.mark.parametrize(
        ('name', 'expected'),
        [
            ('a.mmd', 'mermaid'),
            ('a.puml', 'plantuml'),
            ('a.excalidraw', 'excalidraw'),
            ('a.svg', 'svg'),
            ('a.bin', None),
        ],
    )
    def test_output_format_for_path(self, name, expected):
        assert output_format_for_path(name) == expected

    def test_every_output_format_except_svg_drawings_is_an_input_format(self):
        readable = set(INPUT_FORMATS) | {'c4'}

        assert set(OUTPUT_FORMATS) <= readable


class TestConvert:
    def test_convert_is_exported_at_package_level(self):
        result = diacea.convert(MERMAID, to='d2')

        assert result.input_format == 'mermaid'
        assert result.output_format == 'd2'
        assert 'web -> db' in result.output
        assert 'shape: cylinder' in result.output

    @pytest.mark.parametrize('output_format', sorted(OUTPUT_FORMATS))
    def test_every_output_format_generates(self, output_format):
        assert convert(MERMAID, to=output_format).output.strip()

    def test_options_are_named_after_their_flags(self):
        result = convert(MERMAID, to='mermaid', mermaid_type='sequence')

        assert result.diagram_type == 'sequence'
        assert result.output.startswith('sequenceDiagram')

    def test_unknown_output_format_raises(self):
        with pytest.raises(FormatError, match='Unknown format: visio'):
            convert(MERMAID, to='visio')

    def test_unknown_input_format_raises(self):
        with pytest.raises(FormatError, match='Unsupported input format: visio'):
            parse_diagram(MERMAID, 'visio')

    def test_parse_error_names_the_format(self):
        with pytest.raises(FormatError, match='Failed to parse graphviz input'):
            parse_diagram('digraph { a -> ', 'graphviz')

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FormatError, match='Input file not found'):
            parse_file(tmp_path / 'missing.mmd')

    def test_generator_warnings_are_returned_not_emitted(self):
        source = 'flowchart LR\n    subgraph box\n        inner\n    end\n    box --> inner\n'
        with warnings.catch_warnings():
            warnings.simplefilter('error')
            result = convert(source, to='d2')

        assert any('Dropping connection' in warning for warning in result.warnings)


class TestAuthoredShapesSurviveTextConversion:
    """Label keywords must not override a shape the author chose explicitly."""

    SOURCE = 'flowchart TD\n    A[User Input]\n    B[Report Database]\n    C{Filter?}\n    A --> B\n    B --> C'

    def test_mermaid_round_trip_is_identical(self):
        assert convert(self.SOURCE, to='mermaid').output == self.SOURCE

    def test_plain_boxes_stay_boxes_in_d2(self):
        output = convert(self.SOURCE, to='d2').output

        assert 'shape: person' not in output
        assert 'shape: cylinder' not in output
        assert 'shape: diamond' in output

    def test_direction_is_carried_to_other_formats(self):
        assert 'direction: down' in convert(self.SOURCE, to='d2').output
        assert 'rankdir="TB"' in convert(self.SOURCE, to='graphviz').output

    def test_drawings_still_get_shapes_from_labels(self):
        drawing = {
            'elements': [
                {'id': 'box', 'type': 'rectangle', 'x': 0, 'y': 0, 'width': 160, 'height': 80},
                {'id': 'text', 'type': 'text', 'x': 10, 'y': 30, 'width': 90, 'height': 20, 'text': 'Orders database'},
            ]
        }

        assert 'shape: cylinder' in convert(json.dumps(drawing), to='d2').output


class TestHints:
    def test_stereotype_in_label_sets_type_and_is_removed(self):
        parsed = parse_diagram('flowchart LR\n    A["Ledger <<database>>"] --> B[Report]\n')
        ledger = parsed.diagram.get_shapes()[0]

        assert ledger.label == 'Ledger'
        assert ledger.semantic_type == SemanticType.DATABASE
        assert ledger.semantic_confidence == 1.0

    def test_unknown_stereotype_is_left_in_the_label(self):
        parsed = parse_diagram('flowchart LR\n    A["Vec <<T>>"]\n')

        assert parsed.diagram.get_shapes()[0].label == 'Vec <<T>>'

    def test_hint_by_label_or_id(self):
        parsed = parse_diagram(MERMAID, hints={'web app': 'person', 'db': 'queue'})
        types = {shape.id: shape.semantic_type for shape in parsed.diagram.get_shapes()}

        assert parsed.warnings == []
        assert types == {'web': SemanticType.PERSON, 'db': SemanticType.QUEUE}

    def test_hint_changes_generated_output(self):
        assert 'Person(web' in convert(MERMAID, to='c4', hints={'web': 'person'}).output

    def test_bad_hints_are_reported(self):
        problems = apply_hints(parse_diagram(MERMAID).diagram, {'nope': 'database', 'web': 'blob'})

        assert any('no element has that id or label' in problem for problem in problems)
        assert any('unknown semantic type' in problem for problem in problems)


class TestReadableIds:
    def test_generated_ids_are_replaced_by_label_slugs(self):
        parsed = parse_file(TEST_DATA_DIR / 'curated' / 'aws_hatchet_sketch.excalidraw')
        ids = {shape.id for shape in parsed.diagram.get_shapes()}

        assert {'client', 'api_gw', 'hatchet_engine', 'postgres'} <= ids
        assert all(shape.metadata['source_id'] for shape in parsed.diagram.get_shapes() if shape.id == 'client')

    def test_connections_and_groups_follow_renamed_ids(self):
        diagram = parse_file(TEST_DATA_DIR / 'curated' / 'aws_hatchet_sketch.excalidraw').diagram
        known = {shape.id for shape in diagram.get_shapes()} | {group.id for group in diagram.get_groups()}

        for group in diagram.get_groups():
            assert set(group.children) <= known
        assert ('client', 'api_gw') in {(c.from_id, c.to_id) for c in diagram.get_connections()}

    def test_duplicate_labels_get_distinct_ids(self):
        elements = [
            {'id': f'A1b2C3d4E5f6G7h8I9j{n}', 'type': 'rectangle', 'x': n * 300, 'y': 0, 'width': 100, 'height': 60}
            for n in range(2)
        ]
        elements += [
            {'id': f't{n}', 'type': 'text', 'x': n * 300 + 10, 'y': 20, 'width': 60, 'height': 20, 'text': 'Worker'}
            for n in range(2)
        ]

        diagram = parse_diagram(json.dumps({'elements': elements})).diagram

        assert [shape.id for shape in diagram.get_shapes()] == ['worker', 'worker_2']

    def test_hand_written_ids_are_kept(self):
        diagram = parse_diagram(MERMAID).diagram

        assert [shape.id for shape in diagram.get_shapes()] == ['web', 'db']


def test_render_diagram_reports_detected_mermaid_type():
    diagram = parse_diagram('sequenceDiagram\n    A->>B: hi\n').diagram

    assert render_diagram(diagram, 'mermaid').diagram_type == 'sequence'
