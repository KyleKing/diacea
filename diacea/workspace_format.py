"""Workspace file format serialization/deserialization.

Supports YAML and JSON formats for workspace files.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from .ingestion import IngestionSummary, ingest_diagrams
from .ir.workspace import DiagramView, ElementDefinition, Workspace


def load_workspace(file_path: str | Path) -> Workspace:
    """Load workspace from YAML or JSON file.

    Args:
        file_path: Path to workspace file (.yml, .yaml, or .json)

    Returns:
        Workspace object

    Raises:
        ValueError: If file format is not supported
        FileNotFoundError: If file doesn't exist
    """
    path = Path(file_path)
    if not path.exists():
        msg = f'Workspace file not found: {file_path}'
        raise FileNotFoundError(msg)

    content = Path(path).read_text(encoding='utf-8')

    # Detect format from extension
    suffix = path.suffix.lower()
    if suffix in {'.yml', '.yaml'}:
        data = yaml.safe_load(content)
    elif suffix == '.json':
        data = json.loads(content)
    else:
        msg = f'Unsupported workspace format: {suffix} (use .yml, .yaml, or .json)'
        raise ValueError(msg)

    return from_dict(data)


def save_workspace(workspace: Workspace, file_path: str | Path, format: str = 'yaml') -> None:  # noqa: A002
    """Save workspace to YAML or JSON file.

    Args:
        workspace: Workspace object to save
        file_path: Output file path
        format: Output format ("yaml" or "json")

    Raises:
        ValueError: If format is not supported
    """
    data = to_dict(workspace)

    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with Path(path).open('w', encoding='utf-8') as f:
        if format == 'yaml':
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        elif format == 'json':
            json.dump(data, f, indent=2)
        else:
            msg = f"Unsupported format: {format} (use 'yaml' or 'json')"
            raise ValueError(msg)


def to_dict(workspace: Workspace) -> dict[str, Any]:
    """Convert workspace to dictionary.

    Args:
        workspace: Workspace object

    Returns:
        Dictionary representation
    """
    return {
        'workspace': {
            'id': workspace.id,
            'name': workspace.name,
            'description': workspace.description,
            'version': workspace.version,
            'author': workspace.author,
            'created': workspace.created,
            'modified': workspace.modified,
            'elements': {
                elem_id: {
                    'id': elem.id,
                    'label': elem.label,
                    'description': elem.description,
                    'type': elem.element_type,
                    'technology': elem.technology,
                    'style': elem.style,
                    'tags': elem.tags,
                    'metadata': elem.metadata,
                }
                for elem_id, elem in workspace.elements.items()
            },
            'views': {
                view_id: {
                    'id': view.id,
                    'name': view.name,
                    'type': view.view_type,
                    'description': view.description,
                    'file': view.file,
                    'level': view.zoom_level,
                    'parent': view.parent_view,
                    'focus': view.focused_element,
                    'elements': view.element_refs,
                }
                for view_id, view in workspace.views.items()
            },
        }
    }


def from_dict(data: dict[str, Any]) -> Workspace:
    """Convert dictionary to workspace.

    Args:
        data: Dictionary with workspace data

    Returns:
        Workspace object

    Raises:
        KeyError: If required fields are missing
    """
    ws_data = data.get('workspace', {})

    workspace = Workspace(
        id=ws_data.get('id', ''),
        name=ws_data.get('name', ''),
        description=ws_data.get('description', ''),
        version=ws_data.get('version', '1.0.0'),
        author=ws_data.get('author', ''),
        created=ws_data.get('created', ''),
        modified=ws_data.get('modified', ''),
    )

    # Load elements
    elements_data = ws_data.get('elements', {})
    for elem_id, elem_dict in elements_data.items():
        element = ElementDefinition(
            id=elem_dict.get('id', elem_id),
            label=elem_dict.get('label', ''),
            description=elem_dict.get('description', ''),
            element_type=elem_dict.get('type', 'component'),
            technology=elem_dict.get('technology', ''),
            style=elem_dict.get('style', {}),
            tags=elem_dict.get('tags', []),
            metadata=elem_dict.get('metadata', {}),
        )
        workspace.add_element(element)

    # Load views
    views_data = ws_data.get('views', {})
    for view_id, view_dict in views_data.items():
        view = DiagramView(
            id=view_dict.get('id', view_id),
            name=view_dict.get('name', ''),
            view_type=view_dict.get('type', 'diagram'),
            description=view_dict.get('description', ''),
            file=view_dict.get('file', ''),
            zoom_level=view_dict.get('level', 0),
            parent_view=view_dict.get('parent'),
            focused_element=view_dict.get('focus'),
            element_refs=view_dict.get('elements', []),
        )
        workspace.add_view(view)

    return workspace


def create_workspace_from_diagrams(
    workspace_id: str,
    workspace_name: str,
    diagram_files: dict[str, tuple[str, str]],  # view_id: (file_path, view_type)
) -> tuple[Workspace, IngestionSummary]:
    """Create workspace by parsing existing diagram files.

    Each diagram file is parsed with format auto-detection, labeled shapes are
    extracted into the shared element library (de-duplicated by normalized
    label), and each registered view references the element IDs it uses.

    Args:
        workspace_id: Workspace identifier
        workspace_name: Workspace name
        diagram_files: Dictionary mapping view IDs to (file_path, view_type) tuples

    Returns:
        Tuple of (Workspace, IngestionSummary with counts and conflict warnings)

    Raises:
        DiagramIngestionError: If a diagram file is missing or unparseable
    """
    workspace = Workspace(
        id=workspace_id,
        name=workspace_name,
    )
    summary = ingest_diagrams(workspace, diagram_files)
    return workspace, summary
