"""CLI commands for workspace management."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from .ingestion import DiagramIngestionError, view_id_from_path
from .ir.workspace import DiagramView, ElementDefinition, Workspace
from .workspace_format import create_workspace_from_diagrams, load_workspace, save_workspace

if TYPE_CHECKING:
    _SubParsersAction = argparse._SubParsersAction[argparse.ArgumentParser]
else:
    _SubParsersAction = argparse._SubParsersAction


def workspace_create(args: argparse.Namespace) -> int:
    """Create a new workspace by ingesting diagram files.

    Args:
        args: Command-line arguments

    Returns:
        Exit code
    """
    # Parse diagram file specifications
    diagram_files: dict[str, tuple[str, str]] = {}

    for spec in args.add:
        # Format: file_path:view_id:view_type or file_path:view_id
        parts = spec.split(':')
        if len(parts) < 2:
            print(f"Error: Invalid diagram spec '{spec}' (use file:view_id or file:view_id:type)", file=sys.stderr)
            return 1

        file_path = parts[0]
        view_id = parts[1]
        view_type = parts[2] if len(parts) > 2 else 'diagram'

        diagram_files[view_id] = (file_path, view_type)

    for file_path in args.from_diagrams or []:
        view_id = view_id_from_path(file_path)
        if view_id in diagram_files:
            print(f"Error: Duplicate view ID '{view_id}' derived from '{file_path}'", file=sys.stderr)
            return 1
        diagram_files[view_id] = (file_path, 'diagram')

    # Create workspace (parses each diagram file and extracts elements)
    try:
        workspace, summary = create_workspace_from_diagrams(
            workspace_id=args.id or args.name.lower().replace(' ', '-'),
            workspace_name=args.name,
            diagram_files=diagram_files,
        )
    except DiagramIngestionError as err:
        print(f'Error: {err}', file=sys.stderr)
        return 1

    workspace.description = args.description or ''
    workspace.author = args.author or ''

    # Save workspace
    format_type = 'yaml' if args.output.endswith(('.yml', '.yaml')) else 'json'
    save_workspace(workspace, args.output, format=format_type)

    print(f"Created workspace '{workspace.name}' with {len(workspace.views)} views")
    if summary.diagrams_parsed:
        print(
            f'Ingested {summary.elements_added} elements from {summary.diagrams_parsed} diagrams '
            f'({summary.deduplicated} deduplicated)'
        )
    for warning in summary.warnings:
        print(f'Warning: {warning}', file=sys.stderr)
    print(f'Saved to: {args.output}')

    return 0


def workspace_validate(args: argparse.Namespace) -> int:
    """Validate workspace consistency.

    Args:
        args: Command-line arguments

    Returns:
        Exit code (0 if valid, 1 if errors found)
    """
    try:
        workspace = load_workspace(args.workspace)
    except Exception as e:
        print(f'Error loading workspace: {e}', file=sys.stderr)
        return 1

    print(f"Validating workspace '{workspace.name}'...")

    # Run validation
    errors = workspace.validate_references()

    if not errors:
        print('✓ Workspace is valid')
        print(f'  - {len(workspace.elements)} elements defined')
        print(f'  - {len(workspace.views)} views defined')
        return 0
    else:
        print('✗ Validation errors found:')
        for error in errors:
            print(f'  - {error}')
        return 1


def workspace_info(args: argparse.Namespace) -> int:
    """Show workspace information.

    Args:
        args: Command-line arguments

    Returns:
        Exit code
    """
    try:
        workspace = load_workspace(args.workspace)
    except Exception as e:
        print(f'Error loading workspace: {e}', file=sys.stderr)
        return 1

    # Print workspace info
    print(f'Workspace: {workspace.name}')
    print(f'ID: {workspace.id}')
    if workspace.description:
        print(f'Description: {workspace.description}')
    if workspace.author:
        print(f'Author: {workspace.author}')
    print(f'Version: {workspace.version}')
    print()

    # Elements
    print(f'Elements ({len(workspace.elements)}):')
    for elem_id, elem in workspace.elements.items():
        usage = workspace.get_element_usage(elem_id)
        print(f'  - {elem_id}: {elem.label} ({elem.element_type})')
        if usage:
            print(f'    Used in: {", ".join(usage)}')

    print()

    # Views
    print(f'Views ({len(workspace.views)}):')
    hierarchy = workspace.get_view_hierarchy()

    def print_view(view_id: str, indent: int = 0):
        view = workspace.views[view_id]
        prefix = '  ' * indent
        print(f'{prefix}- {view_id}: {view.name} ({view.view_type})')
        print(f'{prefix}  Elements: {len(view.element_refs)}')
        if view.file:
            print(f'{prefix}  File: {view.file}')

        # Print children
        if view_id in hierarchy:
            for child_id in hierarchy[view_id]:
                print_view(child_id, indent + 1)

    # Print root views first
    for root_id in hierarchy.get('_root', []):
        print_view(root_id)

    return 0


def workspace_add_element(args: argparse.Namespace) -> int:
    """Add element to workspace.

    Args:
        args: Command-line arguments

    Returns:
        Exit code
    """
    try:
        workspace = load_workspace(args.workspace)
    except Exception as e:
        print(f'Error loading workspace: {e}', file=sys.stderr)
        return 1

    # Create element
    element = ElementDefinition(
        id=args.id,
        label=args.label or args.id.replace('-', ' ').replace('_', ' ').title(),
        description=args.description or '',
        element_type=args.type,
        technology=args.technology or '',
        tags=args.tags or [],
    )

    # Add to workspace
    workspace.add_element(element)

    # Save
    save_workspace(workspace, args.workspace)

    print(f"Added element '{element.id}' to workspace")

    return 0


def workspace_add_view(args: argparse.Namespace) -> int:
    """Add view to workspace.

    Args:
        args: Command-line arguments

    Returns:
        Exit code
    """
    try:
        workspace = load_workspace(args.workspace)
    except Exception as e:
        print(f'Error loading workspace: {e}', file=sys.stderr)
        return 1

    # Create view
    view = DiagramView(
        id=args.id,
        name=args.name or args.id.replace('-', ' ').replace('_', ' ').title(),
        view_type=args.type,
        description=args.description or '',
        file=args.file or '',
        zoom_level=args.level,
        parent_view=args.parent,
        element_refs=args.elements or [],
    )

    # Add to workspace
    workspace.add_view(view)

    # Save
    save_workspace(workspace, args.workspace)

    print(f"Added view '{view.id}' to workspace")

    return 0


def add_workspace_subcommands(subparsers: _SubParsersAction) -> None:
    """Add workspace subcommands to CLI parser.

    Args:
        subparsers: Subparser action object
    """
    # workspace create
    create_parser = subparsers.add_parser(
        'create',
        help='Create new workspace',
        description='Create a new workspace from diagram files',
    )
    create_parser.add_argument('--name', required=True, help='Workspace name')
    create_parser.add_argument('--id', help='Workspace ID (default: derived from name)')
    create_parser.add_argument('--description', default='', help='Workspace description')
    create_parser.add_argument('--author', default='', help='Workspace author')
    create_parser.add_argument(
        '--add',
        action='append',
        default=[],
        metavar='FILE:VIEW_ID[:TYPE]',
        help='Add diagram file (format: file.json:view_id or file.json:view_id:context)',
    )
    create_parser.add_argument(
        '--from-diagrams',
        nargs='+',
        default=[],
        metavar='FILE',
        help='Diagram files to ingest (view IDs derived from file names)',
    )
    create_parser.add_argument('-o', '--output', required=True, help='Output workspace file (.yml or .json)')
    create_parser.set_defaults(func=workspace_create)

    # workspace validate
    validate_parser = subparsers.add_parser(
        'validate',
        help='Validate workspace',
        description='Validate workspace for consistency and reference errors',
    )
    validate_parser.add_argument('workspace', help='Workspace file to validate')
    validate_parser.set_defaults(func=workspace_validate)

    # workspace info
    info_parser = subparsers.add_parser(
        'info',
        help='Show workspace information',
        description='Display workspace details, elements, and views',
    )
    info_parser.add_argument('workspace', help='Workspace file')
    info_parser.set_defaults(func=workspace_info)

    # workspace element add
    elem_add_parser = subparsers.add_parser(
        'add-element',
        help='Add element to workspace',
        description='Add a new element definition to the workspace library',
    )
    elem_add_parser.add_argument('workspace', help='Workspace file')
    elem_add_parser.add_argument('--id', required=True, help='Element ID')
    elem_add_parser.add_argument('--label', help='Element label')
    elem_add_parser.add_argument('--description', default='', help='Element description')
    elem_add_parser.add_argument(
        '--type', default='component', help='Element type (system, container, component, etc.)'
    )
    elem_add_parser.add_argument('--technology', default='', help='Technology stack')
    elem_add_parser.add_argument('--tags', nargs='*', help='Tags')
    elem_add_parser.set_defaults(func=workspace_add_element)

    # workspace view add
    view_add_parser = subparsers.add_parser(
        'add-view',
        help='Add view to workspace',
        description='Add a new diagram view to the workspace',
    )
    view_add_parser.add_argument('workspace', help='Workspace file')
    view_add_parser.add_argument('--id', required=True, help='View ID')
    view_add_parser.add_argument('--name', help='View name')
    view_add_parser.add_argument('--type', default='diagram', help='View type (context, container, component, etc.)')
    view_add_parser.add_argument('--description', default='', help='View description')
    view_add_parser.add_argument('--file', default='', help='Diagram file path')
    view_add_parser.add_argument('--level', type=int, default=0, help='Zoom level (C4: 1=Context, 2=Container, etc.)')
    view_add_parser.add_argument('--parent', help='Parent view ID')
    view_add_parser.add_argument('--elements', nargs='*', help='Element IDs used in this view')
    view_add_parser.set_defaults(func=workspace_add_view)


def main_workspace(argv: Optional[list[str]] = None) -> int:
    """Main entry point for workspace CLI.

    Args:
        argv: Command-line arguments

    Returns:
        Exit code
    """
    parser = argparse.ArgumentParser(
        prog='diacea workspace',
        description='Workspace management for multi-diagram projects',
    )

    subparsers = parser.add_subparsers(
        title='commands',
        description='Available workspace commands',
        dest='command',
        required=True,
    )

    add_workspace_subcommands(subparsers)

    args = parser.parse_args(argv)

    # Execute command
    return args.func(args)
