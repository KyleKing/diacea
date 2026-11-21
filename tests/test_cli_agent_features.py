"""Tests for agent-oriented CLI features: --json envelope, inspect, formats, exit codes."""

import json

import pytest

from diacea.cli import EXIT_EMPTY_DIAGRAM, EXIT_ERROR, EXIT_OK, main


@pytest.fixture
def excalidraw_file(tmp_path):
    data = {
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
    f = tmp_path / 'test.json'
    f.write_text(json.dumps(data))
    return f


@pytest.fixture
def empty_excalidraw_file(tmp_path):
    f = tmp_path / 'empty.json'
    f.write_text(json.dumps({'elements': []}))
    return f


@pytest.fixture
def curved_svg_file(tmp_path):
    svg_content = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" width="300" height="200">
    <rect id="a" x="10" y="10" width="80" height="40" fill="blue"/>
    <rect id="b" x="150" y="10" width="80" height="40" fill="red"/>
    <path d="M 10 100 C 40 80, 80 80, 110 100 L 150 150 Z" fill="green"/>
</svg>"""
    f = tmp_path / 'curved.svg'
    f.write_text(svg_content)
    return f


@pytest.fixture
def multipage_tldraw_file(tmp_path):
    data = {
        'document': {
            'pages': {
                'page1': {
                    'id': 'page1',
                    'shapes': {
                        'shape1': {'id': 'shape1', 'type': 'rectangle', 'point': [0.0, 0.0], 'size': [100.0, 50.0]}
                    },
                    'bindings': {},
                },
                'page2': {
                    'id': 'page2',
                    'shapes': {
                        'shape2': {'id': 'shape2', 'type': 'ellipse', 'point': [0.0, 0.0], 'size': [100.0, 50.0]}
                    },
                    'bindings': {},
                },
            }
        }
    }
    f = tmp_path / 'multipage.json'
    f.write_text(json.dumps(data))
    return f


class TestJsonEnvelope:
    def test_envelope_fields(self, excalidraw_file, capsys):
        result = main(['-i', str(excalidraw_file), '-f', 'mermaid', '--json'])
        assert result == EXIT_OK
        envelope = json.loads(capsys.readouterr().out)
        assert set(envelope) == {
            'output',
            'input_format',
            'output_format',
            'diagram_type',
            'elements',
            'warnings',
        }
        assert envelope['input_format'] == 'excalidraw'
        assert envelope['output_format'] == 'mermaid'
        assert envelope['diagram_type'] in {'flowchart', 'c4', 'sequence'}
        assert envelope['diagram_type'] in envelope['output'].lower() or envelope['diagram_type'] == 'c4'
        assert isinstance(envelope['warnings'], list)

    def test_envelope_elements_have_semantic_fields(self, excalidraw_file, capsys):
        result = main(['-i', str(excalidraw_file), '-f', 'mermaid', '--json'])
        assert result == EXIT_OK
        envelope = json.loads(capsys.readouterr().out)
        element_ids = {e['id'] for e in envelope['elements']}
        assert {'a', 'b', 'arr'} <= element_ids
        for element in envelope['elements']:
            assert {'id', 'type', 'label', 'semantic_type', 'confidence'} <= set(element)
            assert ('shape' in element) == (element['type'] == 'shape')
            assert 0.0 <= element['confidence'] <= 1.0

    def test_envelope_reports_forced_mermaid_type(self, excalidraw_file, capsys):
        result = main(['-i', str(excalidraw_file), '-f', 'mermaid', '--mermaid-type', 'c4', '--json'])
        assert result == EXIT_OK
        envelope = json.loads(capsys.readouterr().out)
        assert envelope['diagram_type'] == 'c4'

    def test_envelope_diagram_type_null_for_non_mermaid(self, excalidraw_file, capsys):
        result = main(['-i', str(excalidraw_file), '-f', 'plantuml', '--json'])
        assert result == EXIT_OK
        envelope = json.loads(capsys.readouterr().out)
        assert envelope['diagram_type'] is None
        assert '@startuml' in envelope['output']

    def test_envelope_with_output_file(self, excalidraw_file, tmp_path, capsys):
        output_file = tmp_path / 'out.mmd'
        result = main(['-i', str(excalidraw_file), '-f', 'mermaid', '-o', str(output_file), '--json'])
        assert result == EXIT_OK
        envelope = json.loads(capsys.readouterr().out)
        assert output_file.read_text() == envelope['output']

    def test_convert_subcommand_alias(self, excalidraw_file, capsys):
        result = main(['convert', '-i', str(excalidraw_file), '-f', 'mermaid', '--json'])
        assert result == EXIT_OK
        envelope = json.loads(capsys.readouterr().out)
        assert envelope['input_format'] == 'excalidraw'


class TestStructuredFailures:
    def test_file_not_found(self, capsys):
        result = main(['-i', 'nonexistent.json', '-f', 'mermaid'])
        assert result == EXIT_ERROR
        assert 'not found' in capsys.readouterr().err

    def test_file_not_found_json(self, capsys):
        result = main(['-i', 'nonexistent.json', '-f', 'mermaid', '--json'])
        assert result == EXIT_ERROR
        captured = capsys.readouterr()
        assert not captured.out
        error = json.loads(captured.err)
        assert 'not found' in error['error']
        assert error['exit_code'] == EXIT_ERROR

    def test_unrecognized_format(self, tmp_path, capsys):
        f = tmp_path / 'unknown.json'
        f.write_text('{"not": "a diagram"}')
        result = main(['-i', str(f), '-f', 'mermaid'])
        assert result == EXIT_ERROR
        assert 'Unrecognized input format' in capsys.readouterr().err

    def test_unrecognized_format_json(self, tmp_path, capsys):
        f = tmp_path / 'unknown.json'
        f.write_text('{"not": "a diagram"}')
        result = main(['-i', str(f), '-f', 'mermaid', '--json'])
        assert result == EXIT_ERROR
        error = json.loads(capsys.readouterr().err)
        assert 'Unrecognized input format' in error['error']

    def test_empty_diagram_exit_code(self, empty_excalidraw_file, capsys):
        result = main(['-i', str(empty_excalidraw_file), '-f', 'mermaid'])
        assert result == EXIT_EMPTY_DIAGRAM
        assert 'parsed 0 elements' in capsys.readouterr().err

    def test_empty_diagram_json(self, empty_excalidraw_file, capsys):
        result = main(['-i', str(empty_excalidraw_file), '-f', 'mermaid', '--json'])
        assert result == EXIT_EMPTY_DIAGRAM
        error = json.loads(capsys.readouterr().err)
        assert 'parsed 0 elements' in error['error']
        assert error['exit_code'] == EXIT_EMPTY_DIAGRAM


class TestConversionLossWarnings:
    def test_svg_curve_warning_in_envelope(self, curved_svg_file, capsys):
        result = main(['-i', str(curved_svg_file), '-f', 'mermaid', '--json'])
        assert result == EXIT_OK
        envelope = json.loads(capsys.readouterr().out)
        assert any('curve' in w for w in envelope['warnings'])

    def test_svg_curve_warning_on_stderr_in_text_mode(self, curved_svg_file, capsys):
        result = main(['-i', str(curved_svg_file), '-f', 'mermaid'])
        assert result == EXIT_OK
        captured = capsys.readouterr()
        assert 'Warning:' in captured.err
        assert 'curve' in captured.err
        assert 'Warning' not in captured.out

    def test_tldraw_multipage_warning(self, multipage_tldraw_file, capsys):
        result = main(['-i', str(multipage_tldraw_file), '-f', 'd2', '--json'])
        assert result == EXIT_OK
        envelope = json.loads(capsys.readouterr().out)
        assert any('2 pages' in w for w in envelope['warnings'])

    def test_no_warnings_for_clean_input(self, excalidraw_file, capsys):
        result = main(['-i', str(excalidraw_file), '-f', 'mermaid', '--json'])
        assert result == EXIT_OK
        envelope = json.loads(capsys.readouterr().out)
        assert envelope['warnings'] == []


class TestFormatsSubcommand:
    def test_formats_text(self, capsys):
        result = main(['formats'])
        assert result == EXIT_OK
        captured = capsys.readouterr().out
        assert 'Input formats:' in captured
        assert 'Output formats:' in captured
        for name in ('excalidraw', 'obsidian', 'svg', 'tldraw', 'mermaid', 'plantuml', 'graphviz', 'd2', 'c4'):
            assert name in captured

    def test_formats_json(self, capsys):
        result = main(['formats', '--json'])
        assert result == EXIT_OK
        listing = json.loads(capsys.readouterr().out)
        assert set(listing) == {'input_formats', 'output_formats', 'semantic_types'}
        assert 'database' in listing['semantic_types']
        input_names = {f['name'] for f in listing['input_formats']}
        assert input_names == {'d2', 'excalidraw', 'graphviz', 'mermaid', 'obsidian', 'plantuml', 'svg', 'tldraw'}
        for input_format in listing['input_formats']:
            assert input_format['detection']
        output_names = {f['name'] for f in listing['output_formats']}
        assert output_names == {'c4', 'd2', 'excalidraw', 'graphviz', 'mermaid', 'plantuml', 'svg'}
        for output_format in listing['output_formats']:
            assert isinstance(output_format['options'], list)


class TestInspectSubcommand:
    def test_inspect_text(self, excalidraw_file, capsys):
        result = main(['inspect', str(excalidraw_file)])
        assert result == EXIT_OK
        captured = capsys.readouterr().out
        assert 'Format: excalidraw' in captured
        assert 'Elements:' in captured
        assert 'confidence=' in captured

    def test_inspect_json(self, excalidraw_file, capsys):
        result = main(['inspect', str(excalidraw_file), '--json'])
        assert result == EXIT_OK
        report = json.loads(capsys.readouterr().out)
        assert set(report) == {'input_format', 'element_count', 'elements', 'warnings'}
        assert report['input_format'] == 'excalidraw'
        assert report['element_count'] == len(report['elements']) >= 3
        for element in report['elements']:
            assert {'id', 'type', 'label', 'semantic_type', 'confidence'} <= set(element)

    def test_inspect_svg_detects_format_and_warnings(self, curved_svg_file, capsys):
        result = main(['inspect', str(curved_svg_file), '--json'])
        assert result == EXIT_OK
        report = json.loads(capsys.readouterr().out)
        assert report['input_format'] == 'svg'
        assert any('curve' in w for w in report['warnings'])

    def test_inspect_empty_diagram_reports_warning(self, empty_excalidraw_file, capsys):
        result = main(['inspect', str(empty_excalidraw_file), '--json'])
        assert result == EXIT_OK
        report = json.loads(capsys.readouterr().out)
        assert report['element_count'] == 0
        assert any('parsed 0 elements' in w for w in report['warnings'])

    def test_inspect_missing_file(self, capsys):
        result = main(['inspect', 'nonexistent.json'])
        assert result == EXIT_ERROR
        assert 'not found' in capsys.readouterr().err

    def test_inspect_missing_file_json(self, capsys):
        result = main(['inspect', 'nonexistent.json', '--json'])
        assert result == EXIT_ERROR
        error = json.loads(capsys.readouterr().err)
        assert 'not found' in error['error']


class TestBackwardCompatibility:
    def test_bare_invocation_still_converts(self, excalidraw_file, capsys):
        result = main(['-i', str(excalidraw_file), '-f', 'mermaid'])
        assert result == EXIT_OK
        output = capsys.readouterr().out
        assert output.startswith(('flowchart', 'C4Context', 'sequenceDiagram'))

    def test_text_mode_stdout_unchanged(self, excalidraw_file, capsys):
        result = main(['-i', str(excalidraw_file), '-f', 'plantuml'])
        assert result == EXIT_OK
        assert '@startuml' in capsys.readouterr().out


class TestTextFormatInputs:
    def test_mermaid_autodetect_to_d2(self, tmp_path, capsys):
        f = tmp_path / 'flow.mmd'
        f.write_text('flowchart LR\n    a[(Orders DB)]\n    b[API]\n    b -->|reads| a\n')
        result = main(['-i', str(f), '-f', 'd2', '--json'])
        assert result == EXIT_OK
        envelope = json.loads(capsys.readouterr().out)
        assert envelope['input_format'] == 'mermaid'
        assert '->' in envelope['output']
        semantic_types = {e['semantic_type'] for e in envelope['elements']}
        assert 'database' in semantic_types

    def test_plantuml_autodetect_to_mermaid(self, tmp_path, capsys):
        f = tmp_path / 'arch.puml'
        f.write_text('@startuml\ndatabase "Orders" as db\nrectangle "API" as api\napi --> db : reads\n@enduml\n')
        result = main(['-i', str(f), '-f', 'mermaid', '--json'])
        assert result == EXIT_OK
        envelope = json.loads(capsys.readouterr().out)
        assert envelope['input_format'] == 'plantuml'
        assert 'reads' in envelope['output']

    def test_c4_plantuml_roundtrip_via_cli(self, tmp_path, capsys):
        f = tmp_path / 'c4.puml'
        f.write_text(
            '@startuml\n!include https://raw.githubusercontent.com/plantuml-stdlib/'
            'C4-PlantUML/master/C4_Container.puml\n'
            'Person(user, "User")\nContainerDb(db, "Orders")\nRel(user, db, "queries")\n@enduml\n'
        )
        result = main(['-i', str(f), '-f', 'c4'])
        assert result == EXIT_OK
        output = capsys.readouterr().out
        assert 'Person(user, "User")' in output
        assert 'Rel(user, db' in output

    def test_mermaid_sequence_converts(self, tmp_path, capsys):
        f = tmp_path / 'seq.mmd'
        f.write_text('sequenceDiagram\n    A->>B: hi\n')
        result = main(['-i', str(f), '-f', 'd2', '--json'])
        assert result == EXIT_OK
        envelope = json.loads(capsys.readouterr().out)
        assert envelope['input_format'] == 'mermaid'
        assert 'A -> B: hi' in envelope['output']

    def test_explicit_input_format_flag(self, tmp_path, capsys):
        f = tmp_path / 'flow.txt'
        f.write_text('flowchart TD\n    a --> b\n')
        result = main(['-i', str(f), '--input-format', 'mermaid', '-f', 'graphviz'])
        assert result == EXIT_OK
        assert 'digraph' in capsys.readouterr().out


class TestConvenientInvocation:
    def test_positional_input(self, excalidraw_file, capsys):
        assert main([str(excalidraw_file), '-f', 'mermaid']) == EXIT_OK
        assert capsys.readouterr().out.startswith(('flowchart', 'C4Context'))

    def test_output_format_inferred_from_extension(self, excalidraw_file, tmp_path, capsys):
        target = tmp_path / 'out.d2'

        assert main([str(excalidraw_file), '-o', str(target)]) == EXIT_OK
        assert 'Generated d2 diagram' in capsys.readouterr().err
        assert target.read_text().strip()

    def test_text_to_excalidraw_and_back(self, tmp_path, capsys):
        source = tmp_path / 'flow.mmd'
        source.write_text('flowchart LR\n    a[Web]\n    b[(DB)]\n    a -->|calls| b\n')
        drawing = tmp_path / 'flow.excalidraw'

        assert main([str(source), '-o', str(drawing)]) == EXIT_OK
        assert json.loads(drawing.read_text())['type'] == 'excalidraw'
        capsys.readouterr()
        assert main([str(drawing), '-f', 'mermaid', '--mermaid-type', 'flowchart']) == EXIT_OK
        assert capsys.readouterr().out.strip() == source.read_text().strip()

    @pytest.mark.parametrize(('suffix', 'content'), [('.dot', 'digraph { a -> b }'), ('.d2', 'a -> b\n')])
    def test_new_text_inputs_convert(self, tmp_path, capsys, suffix, content):
        source = tmp_path / f'graph{suffix}'
        source.write_text(content)

        assert main([str(source), '-f', 'mermaid']) == EXIT_OK
        assert 'a --> b' in capsys.readouterr().out

    def test_missing_input_is_explained(self, capsys):
        assert main(['-f', 'mermaid']) == EXIT_ERROR
        assert 'No input given' in capsys.readouterr().err

    def test_missing_format_is_explained(self, excalidraw_file, capsys):
        assert main([str(excalidraw_file)]) == EXIT_ERROR
        assert 'No output format given' in capsys.readouterr().err

    def test_conflicting_inputs_are_rejected(self, excalidraw_file, capsys):
        assert main(['other.json', '-i', str(excalidraw_file), '-f', 'mermaid']) == EXIT_ERROR
        assert 'Two inputs given' in capsys.readouterr().err

    def test_generator_warnings_are_plain_warning_lines(self, tmp_path, capsys):
        source = tmp_path / 'loop.mmd'
        source.write_text('flowchart LR\n    subgraph box\n        inner\n    end\n    box --> inner\n')

        assert main([str(source), '-f', 'd2']) == EXIT_OK
        err = capsys.readouterr().err
        assert 'Warning: Dropping connection' in err
        assert 'UserWarning' not in err


class TestHintFlag:
    def test_hint_overrides_inferred_type(self, excalidraw_file, capsys):
        assert main([str(excalidraw_file), '-f', 'c4', '--hint', 'a=database', '--json']) == EXIT_OK
        envelope = json.loads(capsys.readouterr().out)
        element = next(e for e in envelope['elements'] if e['id'] == 'a')

        assert element['semantic_type'] == 'database'
        assert element['confidence'] == 1.0

    def test_hint_that_matches_nothing_warns(self, excalidraw_file, capsys):
        assert main([str(excalidraw_file), '-f', 'mermaid', '--hint', 'nope=database']) == EXIT_OK
        assert 'no element has that id or label' in capsys.readouterr().err

    def test_malformed_hint_is_an_error(self, excalidraw_file, capsys):
        assert main([str(excalidraw_file), '-f', 'mermaid', '--hint', 'database']) == EXIT_ERROR
        assert 'ID_OR_LABEL=TYPE' in capsys.readouterr().err

    def test_inspect_explains_how_to_correct_a_guess(self, excalidraw_file, capsys):
        assert main(['inspect', str(excalidraw_file)]) == EXIT_OK
        assert '<<database>>' in capsys.readouterr().err

    def test_formats_lists_semantic_types(self, capsys):
        assert main(['formats']) == EXIT_OK
        assert 'Semantic types' in capsys.readouterr().out


class TestVerifyFlag:
    def test_verified_conversion_reports_counts(self, excalidraw_file, capsys):
        assert main([str(excalidraw_file), '-f', 'd2', '--verify']) == EXIT_OK
        assert 'Verified: the d2 output reads back with the same' in capsys.readouterr().err

    def test_verification_in_json_envelope(self, excalidraw_file, capsys):
        assert main([str(excalidraw_file), '-f', 'graphviz', '--verify', '--json']) == EXIT_OK
        envelope = json.loads(capsys.readouterr().out)

        assert envelope['verification'] == {'checked': True, 'problems': []}

    def test_format_that_cannot_be_read_back_is_not_verified(self, excalidraw_file, capsys):
        assert main([str(excalidraw_file), '-f', 'svg', '--verify', '-o', '-']) == EXIT_OK
        assert 'Not verified' in capsys.readouterr().err


_CLI_FILES = {
    'arch.d2': 'web: Web App\n',
    'declared.puml': '@startuml\ndatabase "Orders" as o\nqueue "Jobs" as j\no --> j\n@enduml\n',
    'flow.mmd': 'flowchart LR\n  a[A] --> b[B]\n',
}


@pytest.mark.parametrize(
    ('argv', 'code', 'out', 'err'),
    [
        pytest.param(['--version'], 0, 'diacea 0.0.1\n', '', id='version'),
        pytest.param(['arch.d2', '-f', 'mermaid'], 0, 'flowchart LR\n    web[Web App]\n', '', id='extension-decides'),
        pytest.param(
            ['inspect', 'declared.puml'],
            0,
            "Format: plantuml\nElements: 3\n  o: label='Orders' semantic=database confidence=0.90\n"
            "  j: label='Jobs' semantic=queue confidence=0.90\n  conn-0: label='' semantic=- confidence=0.00\n",
            '',
            id='inspect-declared-types-need-no-tip',
        ),
        pytest.param(
            ['flow.mmd', '-f', 'd2', '--verify'],
            0,
            'direction: right\n\na: A\nb: B\n\na -> b\n',
            'Verified: the d2 output reads back with the same 2 node(s), 0 group(s), and connections\n',
            id='verify-counts',
        ),
    ],
)
def test_cli_output(argv, code, out, err, tmp_path, monkeypatch, capsys):
    for name, content in _CLI_FILES.items():
        (tmp_path / name).write_text(content)
    monkeypatch.chdir(tmp_path)

    result: int | str | None
    try:
        result = main(argv)
    except SystemExit as exit_:
        result = exit_.code

    assert (result, *capsys.readouterr()) == (code, out, err)


def test_unverifiable_json_envelope_says_unchecked(tmp_path, capsys):
    source = tmp_path / 'flow.mmd'
    source.write_text(_CLI_FILES['flow.mmd'])

    assert main([str(source), '-f', 'svg', '--verify', '--json']) == EXIT_OK
    assert json.loads(capsys.readouterr().out)['verification'] == {'checked': False, 'problems': []}


def test_formats_json_is_indented_by_two(capsys):
    assert main(['formats', '--json']) == EXIT_OK
    assert capsys.readouterr().out.startswith('{\n  "input_formats": [\n    {\n      "name": "d2",\n')


def test_version_without_package_metadata_is_unknown(monkeypatch, capsys):
    import diacea

    monkeypatch.delattr(diacea, '__version__')

    with pytest.raises(SystemExit):
        main(['--version'])
    assert capsys.readouterr().out == 'diacea unknown\n'
