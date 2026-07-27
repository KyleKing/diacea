"""Tests for workspace functionality."""

import json
import tempfile
from pathlib import Path

import pytest

from diacea.ingestion import DiagramIngestionError, ingest_diagrams, view_id_from_path
from diacea.ir.workspace import DiagramView, ElementDefinition, Workspace
from diacea.workspace_format import (
    create_workspace_from_diagrams,
    from_dict,
    load_workspace,
    save_workspace,
    to_dict,
)

from .configuration import TEST_DATA_DIR


class TestElementDefinition:
    """Test ElementDefinition class."""

    def test_create_element(self):
        """Test creating an element definition."""
        elem = ElementDefinition(
            id='api-gateway',
            label='API Gateway',
            description='Routes requests',
            element_type='container',
            technology='Node.js',
            style={'color': '#90EE90'},
            tags=['web-tier', 'critical'],
        )

        assert elem.id == 'api-gateway'
        assert elem.label == 'API Gateway'
        assert elem.element_type == 'container'
        assert elem.technology == 'Node.js'
        assert 'critical' in elem.tags


class TestDiagramView:
    """Test DiagramView class."""

    def test_create_view(self):
        """Test creating a diagram view."""
        view = DiagramView(
            id='context',
            name='System Context',
            view_type='c4-context',
            description='High-level view',
            file='diagrams/context.json',
            zoom_level=1,
            element_refs=['api-gateway', 'database'],
        )

        assert view.id == 'context'
        assert view.view_type == 'c4-context'
        assert view.zoom_level == 1
        assert len(view.element_refs) == 2

    def test_create_child_view(self):
        """Test creating a child view with parent."""
        view = DiagramView(
            id='api-containers',
            name='API Containers',
            view_type='c4-container',
            zoom_level=2,
            parent_view='context',
            focused_element='api-gateway',
            element_refs=['router', 'auth'],
        )

        assert view.parent_view == 'context'
        assert view.focused_element == 'api-gateway'


class TestWorkspace:
    """Test Workspace class."""

    def test_create_workspace(self):
        """Test creating a workspace."""
        workspace = Workspace(
            id='ecommerce',
            name='E-Commerce Platform',
            description='Architecture views',
            version='1.0.0',
        )

        assert workspace.id == 'ecommerce'
        assert workspace.name == 'E-Commerce Platform'
        assert len(workspace.elements) == 0
        assert len(workspace.views) == 0

    def test_add_element(self):
        """Test adding elements to workspace."""
        workspace = Workspace(id='test', name='Test')

        elem1 = ElementDefinition(id='elem1', label='Element 1')
        elem2 = ElementDefinition(id='elem2', label='Element 2')

        workspace.add_element(elem1)
        workspace.add_element(elem2)

        assert len(workspace.elements) == 2
        assert workspace.get_element('elem1') == elem1
        assert workspace.get_element('elem2') == elem2

    def test_add_view(self):
        """Test adding views to workspace."""
        workspace = Workspace(id='test', name='Test')

        view1 = DiagramView(id='view1', name='View 1', view_type='context')
        view2 = DiagramView(id='view2', name='View 2', view_type='container')

        workspace.add_view(view1)
        workspace.add_view(view2)

        assert len(workspace.views) == 2
        assert workspace.get_view('view1') == view1
        assert workspace.get_view('view2') == view2

    def test_get_related_views(self):
        """Test getting related views."""
        workspace = Workspace(id='test', name='Test')

        parent = DiagramView(id='parent', name='Parent', view_type='context')
        child1 = DiagramView(id='child1', name='Child 1', view_type='container', parent_view='parent')
        child2 = DiagramView(id='child2', name='Child 2', view_type='container', parent_view='parent')

        workspace.add_view(parent)
        workspace.add_view(child1)
        workspace.add_view(child2)

        # Get related views from parent (should get children)
        related = workspace.get_related_views('parent')
        assert len(related) == 2

        # Get related views from child (should get parent)
        related = workspace.get_related_views('child1')
        assert len(related) == 1
        assert related[0].id == 'parent'

    def test_get_child_views(self):
        """Test getting child views."""
        workspace = Workspace(id='test', name='Test')

        parent = DiagramView(id='parent', name='Parent', view_type='context')
        child1 = DiagramView(id='child1', name='Child 1', view_type='container', parent_view='parent')
        child2 = DiagramView(id='child2', name='Child 2', view_type='container', parent_view='parent')

        workspace.add_view(parent)
        workspace.add_view(child1)
        workspace.add_view(child2)

        children = workspace.get_child_views('parent')
        assert len(children) == 2
        assert all(c.parent_view == 'parent' for c in children)

    def test_get_parent_view(self):
        """Test getting parent view."""
        workspace = Workspace(id='test', name='Test')

        parent = DiagramView(id='parent', name='Parent', view_type='context')
        child = DiagramView(id='child', name='Child', view_type='container', parent_view='parent')

        workspace.add_view(parent)
        workspace.add_view(child)

        parent_view = workspace.get_parent_view('child')
        assert parent_view is not None
        assert parent_view.id == 'parent'

    def test_validate_references_valid(self):
        """Test validation with valid references."""
        workspace = Workspace(id='test', name='Test')

        elem = ElementDefinition(id='elem1', label='Element 1')
        workspace.add_element(elem)

        view = DiagramView(id='view1', name='View 1', view_type='context', element_refs=['elem1'])
        workspace.add_view(view)

        errors = workspace.validate_references()
        assert len(errors) == 0

    def test_validate_references_missing_element(self):
        """Test validation with missing element reference."""
        workspace = Workspace(id='test', name='Test')

        view = DiagramView(id='view1', name='View 1', view_type='context', element_refs=['missing'])
        workspace.add_view(view)

        errors = workspace.validate_references()
        assert len(errors) > 0
        assert 'missing' in errors[0]

    def test_validate_references_missing_parent(self):
        """Test validation with missing parent view."""
        workspace = Workspace(id='test', name='Test')

        view = DiagramView(id='view1', name='View 1', view_type='container', parent_view='missing')
        workspace.add_view(view)

        errors = workspace.validate_references()
        assert len(errors) > 0
        assert 'missing' in errors[0]

    def test_get_element_usage(self):
        """Test getting element usage across views."""
        workspace = Workspace(id='test', name='Test')

        elem = ElementDefinition(id='elem1', label='Element 1')
        workspace.add_element(elem)

        view1 = DiagramView(id='view1', name='View 1', view_type='context', element_refs=['elem1'])
        view2 = DiagramView(id='view2', name='View 2', view_type='container', element_refs=['elem1'])
        view3 = DiagramView(id='view3', name='View 3', view_type='component', element_refs=[])

        workspace.add_view(view1)
        workspace.add_view(view2)
        workspace.add_view(view3)

        usage = workspace.get_element_usage('elem1')
        assert len(usage) == 2
        assert 'view1' in usage
        assert 'view2' in usage
        assert 'view3' not in usage

    def test_remove_element(self):
        """Test removing element."""
        workspace = Workspace(id='test', name='Test')

        elem = ElementDefinition(id='elem1', label='Element 1')
        workspace.add_element(elem)

        assert len(workspace.elements) == 1

        removed = workspace.remove_element('elem1')
        assert removed is True
        assert len(workspace.elements) == 0

        # Try removing non-existent
        removed = workspace.remove_element('nonexistent')
        assert removed is False

    def test_remove_view(self):
        """Test removing view."""
        workspace = Workspace(id='test', name='Test')

        view = DiagramView(id='view1', name='View 1', view_type='context')
        workspace.add_view(view)

        assert len(workspace.views) == 1

        removed = workspace.remove_view('view1')
        assert removed is True
        assert len(workspace.views) == 0

        # Try removing non-existent
        removed = workspace.remove_view('nonexistent')
        assert removed is False

    def test_get_view_hierarchy(self):
        """Test getting view hierarchy."""
        workspace = Workspace(id='test', name='Test')

        root1 = DiagramView(id='root1', name='Root 1', view_type='context')
        root2 = DiagramView(id='root2', name='Root 2', view_type='context')
        child1 = DiagramView(id='child1', name='Child 1', view_type='container', parent_view='root1')
        grandchild = DiagramView(id='grandchild', name='Grandchild', view_type='component', parent_view='child1')

        workspace.add_view(root1)
        workspace.add_view(root2)
        workspace.add_view(child1)
        workspace.add_view(grandchild)

        hierarchy = workspace.get_view_hierarchy()

        # Check root views
        assert len(hierarchy['_root']) == 2
        assert 'root1' in hierarchy['_root']
        assert 'root2' in hierarchy['_root']

        # Check parent → children mapping
        assert len(hierarchy['root1']) == 1
        assert 'child1' in hierarchy['root1']

        assert len(hierarchy['child1']) == 1
        assert 'grandchild' in hierarchy['child1']


class TestWorkspaceFormat:
    """Test workspace file format serialization."""

    def test_to_dict(self):
        """Test converting workspace to dictionary."""
        workspace = Workspace(id='test', name='Test Workspace')

        elem = ElementDefinition(
            id='elem1',
            label='Element 1',
            element_type='container',
            technology='Node.js',
        )
        workspace.add_element(elem)

        view = DiagramView(
            id='view1',
            name='View 1',
            view_type='context',
            element_refs=['elem1'],
        )
        workspace.add_view(view)

        data = to_dict(workspace)

        assert 'workspace' in data
        assert data['workspace']['id'] == 'test'
        assert data['workspace']['name'] == 'Test Workspace'
        assert 'elem1' in data['workspace']['elements']
        assert 'view1' in data['workspace']['views']

    def test_from_dict(self):
        """Test converting dictionary to workspace."""
        data = {
            'workspace': {
                'id': 'test',
                'name': 'Test Workspace',
                'version': '1.0.0',
                'elements': {
                    'elem1': {
                        'id': 'elem1',
                        'label': 'Element 1',
                        'type': 'container',
                        'technology': 'Node.js',
                    }
                },
                'views': {
                    'view1': {
                        'id': 'view1',
                        'name': 'View 1',
                        'type': 'context',
                        'elements': ['elem1'],
                        'level': 1,
                    }
                },
            }
        }

        workspace = from_dict(data)

        assert workspace.id == 'test'
        assert workspace.name == 'Test Workspace'
        assert len(workspace.elements) == 1
        assert len(workspace.views) == 1

        elem = workspace.get_element('elem1')
        assert elem is not None
        assert elem.label == 'Element 1'

        view = workspace.get_view('view1')
        assert view is not None
        assert view.name == 'View 1'

    def test_save_and_load_yaml(self):
        """Test saving and loading workspace as YAML."""
        workspace = Workspace(id='test', name='Test Workspace')

        elem = ElementDefinition(id='elem1', label='Element 1')
        workspace.add_element(elem)

        view = DiagramView(id='view1', name='View 1', view_type='context', element_refs=['elem1'])
        workspace.add_view(view)

        with tempfile.NamedTemporaryFile(encoding='utf-8', mode='w', suffix='.yml', delete=False) as f:
            temp_path = f.name

        try:
            save_workspace(workspace, temp_path, format='yaml')

            loaded = load_workspace(temp_path)

            assert loaded.id == workspace.id
            assert loaded.name == workspace.name
            assert len(loaded.elements) == 1
            assert len(loaded.views) == 1
        finally:
            Path(temp_path).unlink()

    def test_save_and_load_json(self):
        """Test saving and loading workspace as JSON."""
        workspace = Workspace(id='test', name='Test Workspace')

        elem = ElementDefinition(id='elem1', label='Element 1')
        workspace.add_element(elem)

        view = DiagramView(id='view1', name='View 1', view_type='context', element_refs=['elem1'])
        workspace.add_view(view)

        with tempfile.NamedTemporaryFile(encoding='utf-8', mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name

        try:
            save_workspace(workspace, temp_path, format='json')

            loaded = load_workspace(temp_path)

            assert loaded.id == workspace.id
            assert loaded.name == workspace.name
            assert len(loaded.elements) == 1
            assert len(loaded.views) == 1
        finally:
            Path(temp_path).unlink()


class TestWorkspaceIntegration:
    """Test workspace integration scenarios."""

    def test_c4_hierarchy(self):
        """Test C4 model hierarchy."""
        workspace = Workspace(id='ecommerce', name='E-Commerce Platform')

        # Add elements
        system = ElementDefinition(id='ecommerce-system', label='E-Commerce System', element_type='system')
        api = ElementDefinition(id='api', label='API', element_type='container', technology='Node.js')
        webapp = ElementDefinition(id='webapp', label='Web App', element_type='container', technology='React')
        db = ElementDefinition(id='db', label='Database', element_type='database', technology='PostgreSQL')

        workspace.add_element(system)
        workspace.add_element(api)
        workspace.add_element(webapp)
        workspace.add_element(db)

        # Add views
        context = DiagramView(
            id='context',
            name='System Context',
            view_type='c4-context',
            zoom_level=1,
            element_refs=['ecommerce-system'],
        )

        container = DiagramView(
            id='container',
            name='Container View',
            view_type='c4-container',
            zoom_level=2,
            parent_view='context',
            focused_element='ecommerce-system',
            element_refs=['api', 'webapp', 'db'],
        )

        workspace.add_view(context)
        workspace.add_view(container)

        # Validate
        errors = workspace.validate_references()
        assert len(errors) == 0

        # Check hierarchy
        children = workspace.get_child_views('context')
        assert len(children) == 1
        assert children[0].id == 'container'

        # Check element usage
        usage = workspace.get_element_usage('api')
        assert 'container' in usage


def _write_excalidraw(path, shapes):
    elements: list[dict[str, object]] = []
    for idx, (label, width, height) in enumerate(shapes):
        x = idx * 1000.0
        elements.extend(
            (
                {
                    'id': f'shape{idx}',
                    'type': 'rectangle',
                    'x': x,
                    'y': 0.0,
                    'width': float(width),
                    'height': float(height),
                },
                {
                    'id': f'text{idx}',
                    'type': 'text',
                    'x': x + 10.0,
                    'y': 10.0,
                    'width': 50.0,
                    'height': 20.0,
                    'text': label,
                    'containerId': f'shape{idx}',
                },
            )
        )
    path.write_text(json.dumps({'elements': elements}))


class TestWorkspaceIngestion:
    """Test diagram ingestion into the workspace element library."""

    def test_extracts_elements_from_excalidraw(self):
        workspace, summary = create_workspace_from_diagrams(
            workspace_id='test',
            workspace_name='Test',
            diagram_files={'ctx': (str(TEST_DATA_DIR / 'excalidraw.json'), 'context')},
        )

        assert summary.diagrams_parsed == 1
        assert summary.elements_added == 3
        assert summary.deduplicated == 0
        assert summary.warnings == []

        assert set(workspace.elements) == {'left-box', 'right-box', 'moat'}
        right_box = workspace.elements['right-box']
        assert right_box.label == 'Right Box'
        assert right_box.element_type == 'system'
        assert right_box.metadata['semantic_confidence'] == pytest.approx(0.7)
        assert right_box.metadata['source_file'].endswith('excalidraw.json')

        view = workspace.views['ctx']
        assert view.view_type == 'context'
        assert view.element_refs == ['left-box', 'right-box', 'moat']
        assert workspace.validate_references() == []

    def test_extracts_semantic_types_across_formats(self):
        workspace, summary = create_workspace_from_diagrams(
            workspace_id='test',
            workspace_name='Test',
            diagram_files={
                'containers': (str(TEST_DATA_DIR / 'tldraw_v2.tldr'), 'container'),
                'flow': (str(TEST_DATA_DIR / 'obsidian_plain.excalidraw.md'), 'diagram'),
            },
        )

        assert summary.diagrams_parsed == 2
        assert summary.elements_added == 4
        assert workspace.elements['api-server'].element_type == 'service'
        assert workspace.elements['database'].element_type == 'database'
        assert workspace.elements['client'].element_type == 'person'
        assert workspace.views['containers'].element_refs == ['api-server', 'database']
        assert workspace.views['flow'].element_refs == ['client', 'server']
        assert workspace.get_element_usage('database') == ['containers']

    def test_ingests_mermaid_text(self):
        workspace, summary = create_workspace_from_diagrams(
            workspace_id='test',
            workspace_name='Test',
            diagram_files={'pipeline': (str(TEST_DATA_DIR / 'mermaid' / 'ci_pipeline.mmd'), 'diagram')},
        )

        assert summary.diagrams_parsed == 1
        assert summary.warnings == []
        assert {'developer', 'github', 'ci-checks', 'production'} <= set(workspace.elements)
        assert workspace.elements['developer'].element_type == 'person'
        assert workspace.views['pipeline'].element_refs
        assert workspace.validate_references() == []

    def test_ingests_plantuml_text(self):
        workspace, summary = create_workspace_from_diagrams(
            workspace_id='test',
            workspace_name='Test',
            diagram_files={'arch': (str(TEST_DATA_DIR / 'plantuml' / 'architecture.puml'), 'container')},
        )

        assert summary.diagrams_parsed == 1
        assert summary.warnings == []
        assert {'customer', 'event-bus', 'orders-db'} <= set(workspace.elements)
        assert workspace.elements['customer'].element_type == 'person'
        assert workspace.elements['orders-db'].element_type == 'database'
        assert workspace.views['arch'].element_refs
        assert workspace.validate_references() == []

    def test_dedup_across_two_files(self, tmp_path):
        file_a = tmp_path / 'a.excalidraw'
        file_b = tmp_path / 'b.excalidraw'
        _write_excalidraw(file_a, [('Moat', 600, 500), ('Alpha', 600, 500)])
        _write_excalidraw(file_b, [('Moat', 600, 500), ('Beta', 600, 500)])

        workspace, summary = create_workspace_from_diagrams(
            workspace_id='test',
            workspace_name='Test',
            diagram_files={
                'view-a': (str(file_a), 'diagram'),
                'view-b': (str(file_b), 'diagram'),
            },
        )

        assert summary.elements_added == 3
        assert summary.deduplicated == 1
        assert summary.warnings == []
        assert set(workspace.elements) == {'moat', 'alpha', 'beta'}
        assert workspace.views['view-a'].element_refs == ['moat', 'alpha']
        assert workspace.views['view-b'].element_refs == ['moat', 'beta']
        assert sorted(workspace.get_element_usage('moat')) == ['view-a', 'view-b']

    def test_dedup_normalizes_case_and_whitespace(self, tmp_path):
        file_a = tmp_path / 'a.excalidraw'
        file_b = tmp_path / 'b.excalidraw'
        _write_excalidraw(file_a, [('Left Box', 600, 500)])
        _write_excalidraw(file_b, [('left\nbox', 600, 500)])

        workspace, summary = create_workspace_from_diagrams(
            workspace_id='test',
            workspace_name='Test',
            diagram_files={
                'view-a': (str(file_a), 'diagram'),
                'view-b': (str(file_b), 'diagram'),
            },
        )

        assert summary.deduplicated == 1
        assert set(workspace.elements) == {'left-box'}
        assert workspace.elements['left-box'].label == 'Left Box'

    def test_conflict_keeps_higher_confidence(self, tmp_path):
        low_conf = tmp_path / 'low.excalidraw'
        high_conf = tmp_path / 'high.excalidraw'
        _write_excalidraw(low_conf, [('Moat', 200, 100)])
        _write_excalidraw(high_conf, [('Moat', 600, 500)])

        for order in (['low', 'high'], ['high', 'low']):
            diagram_files = {name: (str(tmp_path / f'{name}.excalidraw'), 'diagram') for name in order}
            workspace, summary = create_workspace_from_diagrams(
                workspace_id='test',
                workspace_name='Test',
                diagram_files=diagram_files,
            )

            assert len(summary.warnings) == 1
            assert 'Moat' in summary.warnings[0]
            assert 'conflicting semantic types' in summary.warnings[0]
            element = workspace.elements['moat']
            assert element.element_type == 'system'
            assert element.metadata['semantic_confidence'] == pytest.approx(0.7)

    def test_ingest_into_existing_workspace_dedups(self, tmp_path):
        diagram = tmp_path / 'd.excalidraw'
        _write_excalidraw(diagram, [('Moat', 600, 500)])

        workspace = Workspace(id='test', name='Test')
        workspace.add_element(
            ElementDefinition(
                id='moat',
                label='Moat',
                element_type='system',
                metadata={'semantic_confidence': 0.9},
            )
        )

        summary = ingest_diagrams(workspace, {'view': (str(diagram), 'diagram')})

        assert summary.elements_added == 0
        assert summary.deduplicated == 1
        assert workspace.views['view'].element_refs == ['moat']

    def test_missing_file_errors_with_file_name(self, tmp_path):
        missing = tmp_path / 'missing.excalidraw'

        with pytest.raises(DiagramIngestionError, match='missing.excalidraw'):
            create_workspace_from_diagrams(
                workspace_id='test',
                workspace_name='Test',
                diagram_files={'view': (str(missing), 'diagram')},
            )

    def test_unparseable_file_errors_with_file_name(self, tmp_path):
        garbage = tmp_path / 'garbage.excalidraw'
        garbage.write_text('this is not a diagram')

        with pytest.raises(DiagramIngestionError, match='garbage.excalidraw'):
            create_workspace_from_diagrams(
                workspace_id='test',
                workspace_name='Test',
                diagram_files={'view': (str(garbage), 'diagram')},
            )

    def test_view_id_from_path(self):
        assert view_id_from_path('a.excalidraw') == 'a'
        assert view_id_from_path('obsidian_plain.excalidraw.md') == 'obsidian-plain'
        assert view_id_from_path('/tmp/System Context.tldr') == 'system-context'
        assert view_id_from_path('ci_pipeline.mmd') == 'ci-pipeline'
        assert view_id_from_path('architecture.puml') == 'architecture'
