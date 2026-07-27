"""Tests for workspace CLI commands."""

import argparse
import json
from pathlib import Path

import pytest

from diacea.ir.workspace import DiagramView, ElementDefinition, Workspace
from diacea.workspace_cli import (
    main_workspace,
    workspace_add_element,
    workspace_add_view,
    workspace_create,
    workspace_info,
    workspace_validate,
)
from diacea.workspace_format import load_workspace, save_workspace

from .configuration import TEST_DATA_DIR


class TestWorkspaceCreate:
    """Test workspace create command."""

    def test_create_yaml_workspace(self, tmp_path):
        output_file = tmp_path / 'workspace.yml'

        args = argparse.Namespace(
            name='Test Workspace',
            id='test-workspace',
            description='A test workspace',
            author='Test Author',
            add=[],
            from_diagrams=[],
            output=str(output_file),
        )

        result = workspace_create(args)
        assert result == 0
        assert output_file.exists()

        workspace = load_workspace(output_file)
        assert workspace.name == 'Test Workspace'
        assert workspace.id == 'test-workspace'
        assert workspace.description == 'A test workspace'
        assert workspace.author == 'Test Author'

    def test_create_json_workspace(self, tmp_path):
        output_file = tmp_path / 'workspace.json'

        args = argparse.Namespace(
            name='JSON Workspace',
            id='json-ws',
            description='',
            author='',
            add=[],
            from_diagrams=[],
            output=str(output_file),
        )

        result = workspace_create(args)
        assert result == 0
        assert output_file.exists()

        with Path(output_file).open() as f:
            data = json.load(f)
        assert data['workspace']['name'] == 'JSON Workspace'

    def test_create_with_diagram_files(self, tmp_path, capsys):
        output_file = tmp_path / 'workspace.yml'
        context_file = TEST_DATA_DIR / 'excalidraw.json'
        detail_file = TEST_DATA_DIR / 'tldraw_v2.tldr'

        args = argparse.Namespace(
            name='With Diagrams',
            id=None,
            description='',
            author='',
            add=[f'{context_file}:context-view:context', f'{detail_file}:detail-view'],
            from_diagrams=[],
            output=str(output_file),
        )

        result = workspace_create(args)
        assert result == 0

        workspace = load_workspace(output_file)
        assert workspace.id == 'with-diagrams'
        assert len(workspace.views) == 2
        assert workspace.views['context-view'].view_type == 'context'
        assert workspace.views['detail-view'].view_type == 'diagram'
        assert workspace.views['context-view'].element_refs == ['left-box', 'right-box', 'moat']
        assert workspace.views['detail-view'].element_refs == ['api-server', 'database']
        assert workspace.validate_references() == []

        captured = capsys.readouterr()
        assert 'Ingested 5 elements from 2 diagrams (0 deduplicated)' in captured.out

    def test_create_from_diagrams(self, tmp_path, capsys):
        output_file = tmp_path / 'workspace.yml'

        args = argparse.Namespace(
            name='Ingested',
            id=None,
            description='',
            author='',
            add=[],
            from_diagrams=[
                str(TEST_DATA_DIR / 'tldraw_v2.tldr'),
                str(TEST_DATA_DIR / 'obsidian_plain.excalidraw.md'),
            ],
            output=str(output_file),
        )

        result = workspace_create(args)
        assert result == 0

        workspace = load_workspace(output_file)
        assert set(workspace.views) == {'tldraw-v2', 'obsidian-plain'}
        assert set(workspace.elements) == {'api-server', 'database', 'client', 'server'}
        assert workspace.elements['database'].element_type == 'database'

        captured = capsys.readouterr()
        assert 'Ingested 4 elements from 2 diagrams (0 deduplicated)' in captured.out

    def test_create_missing_diagram_file(self, tmp_path, capsys):
        output_file = tmp_path / 'workspace.yml'

        args = argparse.Namespace(
            name='Missing',
            id=None,
            description='',
            author='',
            add=[],
            from_diagrams=[str(tmp_path / 'missing.excalidraw')],
            output=str(output_file),
        )

        result = workspace_create(args)
        assert result == 1
        assert not output_file.exists()

        captured = capsys.readouterr()
        assert 'missing.excalidraw' in captured.err

    def test_create_invalid_diagram_spec(self, tmp_path, capsys):
        output_file = tmp_path / 'workspace.yml'

        args = argparse.Namespace(
            name='Invalid',
            id=None,
            description='',
            author='',
            add=['invalid-spec-no-colon'],
            from_diagrams=[],
            output=str(output_file),
        )

        result = workspace_create(args)
        assert result == 1

        captured = capsys.readouterr()
        assert 'Invalid diagram spec' in captured.err


class TestWorkspaceValidate:
    """Test workspace validate command."""

    def test_validate_valid_workspace(self, tmp_path, capsys):
        workspace_file = tmp_path / 'workspace.yml'

        workspace = Workspace(id='test', name='Test')
        element = ElementDefinition(
            id='elem1',
            label='Element 1',
            element_type='component',
        )
        workspace.add_element(element)
        view = DiagramView(
            id='view1',
            name='View 1',
            view_type='diagram',
            element_refs=['elem1'],
        )
        workspace.add_view(view)
        save_workspace(workspace, workspace_file)

        args = argparse.Namespace(workspace=str(workspace_file))

        result = workspace_validate(args)
        assert result == 0

        captured = capsys.readouterr()
        assert 'valid' in captured.out.lower()

    def test_validate_invalid_reference(self, tmp_path, capsys):
        workspace_file = tmp_path / 'workspace.yml'

        workspace = Workspace(id='test', name='Test')
        view = DiagramView(
            id='view1',
            name='View 1',
            view_type='diagram',
            element_refs=['nonexistent-element'],
        )
        workspace.add_view(view)
        save_workspace(workspace, workspace_file)

        args = argparse.Namespace(workspace=str(workspace_file))

        result = workspace_validate(args)
        assert result == 1

        captured = capsys.readouterr()
        assert 'error' in captured.out.lower()

    def test_validate_nonexistent_file(self, tmp_path, capsys):
        args = argparse.Namespace(workspace=str(tmp_path / 'nonexistent.yml'))

        result = workspace_validate(args)
        assert result == 1

        captured = capsys.readouterr()
        assert 'Error' in captured.err


class TestWorkspaceInfo:
    """Test workspace info command."""

    def test_info_displays_workspace_details(self, tmp_path, capsys):
        workspace_file = tmp_path / 'workspace.yml'

        workspace = Workspace(
            id='my-project',
            name='My Project',
            description='Project description',
            author='Test Author',
            version='2.0.0',
        )
        element = ElementDefinition(
            id='api',
            label='API Service',
            element_type='container',
        )
        workspace.add_element(element)
        view = DiagramView(
            id='context',
            name='System Context',
            view_type='context',
            file='context.excalidraw',
            element_refs=['api'],
        )
        workspace.add_view(view)
        save_workspace(workspace, workspace_file)

        args = argparse.Namespace(workspace=str(workspace_file))

        result = workspace_info(args)
        assert result == 0

        captured = capsys.readouterr()
        assert 'My Project' in captured.out
        assert 'my-project' in captured.out
        assert 'Project description' in captured.out
        assert 'Test Author' in captured.out
        assert '2.0.0' in captured.out
        assert 'api' in captured.out
        assert 'API Service' in captured.out
        assert 'context' in captured.out
        assert 'System Context' in captured.out

    def test_info_nonexistent_file(self, tmp_path, capsys):
        args = argparse.Namespace(workspace=str(tmp_path / 'nonexistent.yml'))

        result = workspace_info(args)
        assert result == 1

        captured = capsys.readouterr()
        assert 'Error' in captured.err


class TestWorkspaceAddElement:
    """Test workspace add-element command."""

    def test_add_element_basic(self, tmp_path):
        workspace_file = tmp_path / 'workspace.yml'

        workspace = Workspace(id='test', name='Test')
        save_workspace(workspace, workspace_file)

        args = argparse.Namespace(
            workspace=str(workspace_file),
            id='new-element',
            label='New Element',
            description='Element description',
            type='system',
            technology='Python',
            tags=['backend', 'core'],
        )

        result = workspace_add_element(args)
        assert result == 0

        updated = load_workspace(workspace_file)
        assert 'new-element' in updated.elements
        elem = updated.elements['new-element']
        assert elem.label == 'New Element'
        assert elem.description == 'Element description'
        assert elem.element_type == 'system'
        assert elem.technology == 'Python'
        assert elem.tags == ['backend', 'core']

    def test_add_element_auto_label(self, tmp_path):
        workspace_file = tmp_path / 'workspace.yml'

        workspace = Workspace(id='test', name='Test')
        save_workspace(workspace, workspace_file)

        args = argparse.Namespace(
            workspace=str(workspace_file),
            id='api-gateway',
            label=None,
            description='',
            type='component',
            technology='',
            tags=None,
        )

        result = workspace_add_element(args)
        assert result == 0

        updated = load_workspace(workspace_file)
        assert updated.elements['api-gateway'].label == 'Api Gateway'


class TestWorkspaceAddView:
    """Test workspace add-view command."""

    def test_add_view_basic(self, tmp_path):
        workspace_file = tmp_path / 'workspace.yml'

        workspace = Workspace(id='test', name='Test')
        save_workspace(workspace, workspace_file)

        args = argparse.Namespace(
            workspace=str(workspace_file),
            id='new-view',
            name='New View',
            type='container',
            description='View description',
            file='diagram.excalidraw',
            level=2,
            parent=None,
            elements=['elem1', 'elem2'],
        )

        result = workspace_add_view(args)
        assert result == 0

        updated = load_workspace(workspace_file)
        assert 'new-view' in updated.views
        view = updated.views['new-view']
        assert view.name == 'New View'
        assert view.view_type == 'container'
        assert view.description == 'View description'
        assert view.file == 'diagram.excalidraw'
        assert view.zoom_level == 2
        assert view.element_refs == ['elem1', 'elem2']

    def test_add_view_with_parent(self, tmp_path):
        workspace_file = tmp_path / 'workspace.yml'

        workspace = Workspace(id='test', name='Test')
        parent_view = DiagramView(id='parent', name='Parent', view_type='context')
        workspace.add_view(parent_view)
        save_workspace(workspace, workspace_file)

        args = argparse.Namespace(
            workspace=str(workspace_file),
            id='child-view',
            name='Child View',
            type='container',
            description='',
            file='',
            level=0,
            parent='parent',
            elements=None,
        )

        result = workspace_add_view(args)
        assert result == 0

        updated = load_workspace(workspace_file)
        assert updated.views['child-view'].parent_view == 'parent'


class TestMainWorkspace:
    """Test main_workspace entry point."""

    def test_help_command(self, capsys):
        with pytest.raises(SystemExit) as exc:
            main_workspace(['--help'])
        assert exc.value.code == 0

        captured = capsys.readouterr()
        assert 'workspace' in captured.out.lower()

    def test_create_subcommand(self, tmp_path, capsys):
        output_file = tmp_path / 'workspace.yml'

        result = main_workspace(
            [
                'create',
                '--name',
                'CLI Test',
                '-o',
                str(output_file),
            ]
        )
        assert result == 0
        assert output_file.exists()

    def test_create_from_diagrams_subcommand(self, tmp_path, capsys):
        output_file = tmp_path / 'workspace.yml'

        result = main_workspace(
            [
                'create',
                '--name',
                'CLI Ingest',
                '--from-diagrams',
                str(TEST_DATA_DIR / 'excalidraw.json'),
                str(TEST_DATA_DIR / 'obsidian_plain.excalidraw.md'),
                '-o',
                str(output_file),
            ]
        )
        assert result == 0

        workspace = load_workspace(output_file)
        assert set(workspace.views) == {'excalidraw', 'obsidian-plain'}
        assert len(workspace.elements) == 5

        captured = capsys.readouterr()
        assert 'Ingested 5 elements from 2 diagrams' in captured.out

    def test_validate_subcommand(self, tmp_path, capsys):
        workspace_file = tmp_path / 'workspace.yml'
        workspace = Workspace(id='test', name='Test')
        save_workspace(workspace, workspace_file)

        result = main_workspace(['validate', str(workspace_file)])
        assert result == 0

    def test_info_subcommand(self, tmp_path, capsys):
        workspace_file = tmp_path / 'workspace.yml'
        workspace = Workspace(id='test', name='Test Workspace')
        save_workspace(workspace, workspace_file)

        result = main_workspace(['info', str(workspace_file)])
        assert result == 0

        captured = capsys.readouterr()
        assert 'Test Workspace' in captured.out

    def test_add_element_subcommand(self, tmp_path):
        workspace_file = tmp_path / 'workspace.yml'
        workspace = Workspace(id='test', name='Test')
        save_workspace(workspace, workspace_file)

        result = main_workspace(
            [
                'add-element',
                str(workspace_file),
                '--id',
                'new-elem',
                '--label',
                'New Element',
            ]
        )
        assert result == 0

        updated = load_workspace(workspace_file)
        assert 'new-elem' in updated.elements

    def test_add_view_subcommand(self, tmp_path):
        workspace_file = tmp_path / 'workspace.yml'
        workspace = Workspace(id='test', name='Test')
        save_workspace(workspace, workspace_file)

        result = main_workspace(
            [
                'add-view',
                str(workspace_file),
                '--id',
                'new-view',
                '--name',
                'New View',
            ]
        )
        assert result == 0

        updated = load_workspace(workspace_file)
        assert 'new-view' in updated.views

    def test_missing_required_command(self, capsys):
        with pytest.raises(SystemExit) as exc:
            main_workspace([])

        assert exc.value.code != 0
