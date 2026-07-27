"""Tests for `diacea sync`, ```diacea markdown fences, and the MkDocs plugin."""

from types import SimpleNamespace

import pytest

from diacea.cli import EXIT_ERROR, EXIT_OK, main
from diacea.markdown_fences import DiaceaFenceError, replace_diacea_fences
from diacea.mkdocs_plugin import DiaceaPlugin

from .configuration import TEST_DATA_DIR


@pytest.fixture
def excalidraw_source(tmp_path):
    source = tmp_path / 'arch.excalidraw'
    source.write_text((TEST_DATA_DIR / 'excalidraw.json').read_text())
    return source


class TestSyncCLI:
    def test_writes_mermaid_next_to_source(self, excalidraw_source, capsys):
        result = main(['sync', str(excalidraw_source)])

        assert result == EXIT_OK
        target = excalidraw_source.with_name('arch.mmd')
        assert target.read_text().startswith('C4Context')
        assert target.read_text().endswith('\n')
        assert f'wrote {target}' in capsys.readouterr().err

    def test_second_run_is_noop(self, excalidraw_source, capsys):
        assert main(['sync', str(excalidraw_source)]) == EXIT_OK
        capsys.readouterr()

        assert main(['sync', str(excalidraw_source)]) == EXIT_OK
        assert not capsys.readouterr().err

    def test_check_reports_stale_without_writing(self, excalidraw_source, capsys):
        result = main(['sync', '--check', str(excalidraw_source)])

        assert result == EXIT_ERROR
        assert 'stale' in capsys.readouterr().err
        assert not excalidraw_source.with_name('arch.mmd').exists()

    def test_check_passes_when_in_sync(self, excalidraw_source):
        assert main(['sync', str(excalidraw_source)]) == EXIT_OK
        assert main(['sync', '--check', str(excalidraw_source)]) == EXIT_OK

    def test_output_dir_and_format(self, excalidraw_source, tmp_path):
        out_dir = tmp_path / 'generated'
        result = main(['sync', str(excalidraw_source), '-f', 'd2', '--output-dir', str(out_dir)])

        assert result == EXIT_OK
        assert (out_dir / 'arch.d2').exists()

    def test_obsidian_double_suffix_stripped(self, tmp_path):
        source = tmp_path / 'note.excalidraw.md'
        source.write_text(
            '---\nexcalidraw-plugin: parsed\n---\n# Drawing\n```json\n'
            + (TEST_DATA_DIR / 'excalidraw.json').read_text()
            + '\n```\n'
        )

        assert main(['sync', str(source)]) == EXIT_OK
        assert (tmp_path / 'note.mmd').exists()

    def test_refuses_target_equal_to_source(self, tmp_path, capsys):
        source = tmp_path / 'flow.mmd'
        source.write_text('flowchart LR\n    a --> b\n')

        result = main(['sync', str(source)])

        assert result == EXIT_ERROR
        assert 'output path equals the source' in capsys.readouterr().err
        assert source.read_text() == 'flowchart LR\n    a --> b\n'

    def test_missing_source_errors_but_continues(self, excalidraw_source, capsys):
        result = main(['sync', str(excalidraw_source.parent / 'nope.excalidraw'), str(excalidraw_source)])

        assert result == EXIT_ERROR
        assert 'not found' in capsys.readouterr().err
        assert excalidraw_source.with_name('arch.mmd').exists()


class TestMarkdownFences:
    def test_replaces_fence_with_mermaid_block(self, excalidraw_source):
        markdown = 'before\n\n```diacea\nsource: arch.excalidraw\n```\n\nafter\n'

        result = replace_diacea_fences(markdown, [excalidraw_source.parent])

        assert '```mermaid' in result
        assert 'C4Context' in result
        assert 'diacea' not in result
        assert result.startswith('before')
        assert result.rstrip().endswith('after')

    def test_format_option_controls_fence_language(self, excalidraw_source):
        markdown = '```diacea\nsource: arch.excalidraw\nformat: d2\n```'

        result = replace_diacea_fences(markdown, [excalidraw_source.parent])

        assert result.startswith('```d2')

    def test_indented_fence_stays_indented(self, excalidraw_source):
        markdown = '1. step\n\n    ```diacea\n    source: arch.excalidraw\n    ```\n'

        result = replace_diacea_fences(markdown, [excalidraw_source.parent])

        assert '\n    ```mermaid\n' in result
        assert '\n    C4Context' in result

    def test_second_base_dir_is_fallback(self, excalidraw_source, tmp_path):
        empty = tmp_path / 'pages'
        empty.mkdir()
        markdown = '```diacea\nsource: arch.excalidraw\n```'

        result = replace_diacea_fences(markdown, [empty, excalidraw_source.parent])

        assert '```mermaid' in result

    def test_unrelated_fences_untouched(self):
        markdown = '```python\nprint("hi")\n```\n'
        assert replace_diacea_fences(markdown, ['.']) == markdown

    def test_missing_source_raises(self, tmp_path):
        with pytest.raises(DiaceaFenceError, match='not found'):
            replace_diacea_fences('```diacea\nsource: nope.svg\n```', [tmp_path])

    def test_missing_source_option_raises(self):
        with pytest.raises(DiaceaFenceError, match="missing the required 'source'"):
            replace_diacea_fences('```diacea\nformat: d2\n```', ['.'])

    def test_unknown_option_raises(self):
        with pytest.raises(DiaceaFenceError, match='unknown diacea fence option'):
            replace_diacea_fences('```diacea\nsource: a.svg\ndirection: LR\n```', ['.'])

    def test_unknown_format_raises(self):
        with pytest.raises(DiaceaFenceError, match='unknown diacea fence format'):
            replace_diacea_fences('```diacea\nsource: a.svg\nformat: ascii\n```', ['.'])


class TestMkDocsPlugin:
    def test_on_page_markdown_replaces_fences(self, excalidraw_source):
        page = SimpleNamespace(file=SimpleNamespace(abs_src_path=str(excalidraw_source.parent / 'index.md')))
        config = {'docs_dir': str(excalidraw_source.parent)}

        result = DiaceaPlugin().on_page_markdown(
            '```diacea\nsource: arch.excalidraw\n```',
            page=page,
            config=config,
            files=None,
        )

        assert '```mermaid' in result

    def test_plugin_is_registered_as_entry_point(self):
        from importlib.metadata import entry_points

        plugins = entry_points(group='mkdocs.plugins')
        assert any(ep.name == 'diacea' for ep in plugins)
