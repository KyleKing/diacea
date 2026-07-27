"""Ingest diagram files into a workspace's shared element library."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .cli import detect_input_format
from .ir.elements import Diagram
from .ir.workspace import DiagramView, ElementDefinition, Workspace
from .parsers import (
    ExcalidrawParser,
    MermaidParser,
    PlantUMLParser,
    SVGParser,
    TLDrawParser,
    extract_excalidraw_json,
)


class DiagramIngestionError(Exception):
    """Raised when a diagram file cannot be read or parsed."""


@dataclass
class IngestionSummary:
    """Result of ingesting diagram files into a workspace."""

    diagrams_parsed: int = 0
    elements_added: int = 0
    deduplicated: int = 0
    warnings: list[str] = field(default_factory=list)


def parse_diagram_file(file_path: str | Path) -> Diagram:
    """Parse a diagram file to IR using format auto-detection.

    Raises:
        DiagramIngestionError: If the file is missing, its format cannot be
            detected, or parsing fails.
    """
    path = Path(file_path)
    if not path.exists():
        msg = f'Diagram file not found: {path}'
        raise DiagramIngestionError(msg)

    content = path.read_text(encoding='utf-8')
    stripped = content.strip()

    if stripped.startswith(('<?xml', '<svg')):
        input_format = 'svg'
        input_data: dict[str, Any] | str = content
    else:
        try:
            input_format = detect_input_format(content)
            input_data = content
        except ValueError:
            try:
                input_data = json.loads(content)
            except json.JSONDecodeError as err:
                msg = (
                    f"Could not detect diagram format of '{path}': not SVG, "
                    f'Obsidian Excalidraw markdown, PlantUML, Mermaid, or valid JSON'
                )
                raise DiagramIngestionError(msg) from err
            try:
                input_format = detect_input_format(input_data)
            except ValueError as err:
                msg = f"Could not detect diagram format of '{path}': {err}"
                raise DiagramIngestionError(msg) from err

    try:
        if input_format == 'svg':
            return SVGParser().parse(input_data)
        if input_format == 'obsidian':
            if not isinstance(input_data, str):
                msg = f"Obsidian Excalidraw requires text content: '{path}'"
                raise DiagramIngestionError(msg)
            return ExcalidrawParser().parse(extract_excalidraw_json(input_data))
        if input_format == 'mermaid':
            return MermaidParser().parse(input_data)
        if input_format == 'plantuml':
            return PlantUMLParser().parse(input_data)
        if input_format == 'tldraw':
            return TLDrawParser().parse(input_data)
        return ExcalidrawParser().parse(input_data)
    except ValueError as err:
        msg = f"Failed to parse diagram '{path}': {err}"
        raise DiagramIngestionError(msg) from err


def ingest_diagrams(
    workspace: Workspace,
    diagram_files: dict[str, tuple[str, str]],
) -> IngestionSummary:
    """Parse diagram files and populate the workspace element library.

    Registers a DiagramView per entry (creating it if absent), extracts labeled
    shapes with their inferred semantic types into shared ElementDefinition
    entries, and records the element IDs each view uses.

    Elements are de-duplicated by normalized label (case-insensitive,
    whitespace-collapsed). When the same label appears with conflicting
    semantic types, the higher-confidence inference wins (first-wins on ties)
    and the conflict is recorded in the summary warnings.

    Args:
        workspace: Workspace to populate in place
        diagram_files: Mapping of view ID to (file_path, view_type)

    Returns:
        IngestionSummary with counts and conflict warnings

    Raises:
        DiagramIngestionError: If a diagram file is missing or unparseable
    """
    summary = IngestionSummary()
    elements_by_name: dict[str, ElementDefinition] = {
        _normalize_name(elem.label): elem for elem in workspace.elements.values()
    }

    for view_id, (file_path, view_type) in diagram_files.items():
        diagram = parse_diagram_file(file_path)
        summary.diagrams_parsed += 1

        element_refs: list[str] = []
        for shape in diagram.get_shapes():
            normalized = _normalize_name(shape.label)
            if not normalized:
                continue

            semantic_type = _semantic_type_name(shape.semantic_type)
            confidence = shape.semantic_confidence

            existing = elements_by_name.get(normalized)
            if existing is None:
                element = ElementDefinition(
                    id=_slugify(normalized),
                    label=_collapse_whitespace(shape.label),
                    element_type=semantic_type,
                    metadata={
                        'semantic_confidence': confidence,
                        'source_file': str(file_path),
                    },
                )
                workspace.add_element(element)
                elements_by_name[normalized] = element
                summary.elements_added += 1
                element_id = element.id
            else:
                summary.deduplicated += 1
                element_id = existing.id
                if existing.element_type != semantic_type:
                    _resolve_type_conflict(existing, semantic_type, confidence, file_path, summary)

            if element_id not in element_refs:
                element_refs.append(element_id)

        view = workspace.views.get(view_id)
        if view is None:
            view = DiagramView(
                id=view_id,
                name=view_id.replace('-', ' ').replace('_', ' ').title(),
                view_type=view_type,
                file=str(file_path),
            )
            workspace.add_view(view)
        view.element_refs = element_refs

    return summary


def view_id_from_path(file_path: str | Path) -> str:
    """Derive a view ID from a diagram file name (e.g. 'a.excalidraw.md' -> 'a')."""
    name = Path(file_path).name
    known_suffixes = ('.md', '.mmd', '.excalidraw', '.puml', '.tldr', '.json', '.svg')
    while name.lower().endswith(known_suffixes):
        name = name[: name.rfind('.')]
    return _slugify(name.lower())


def _resolve_type_conflict(
    existing: ElementDefinition,
    semantic_type: str,
    confidence: float,
    file_path: str,
    summary: IngestionSummary,
) -> None:
    existing_confidence = existing.metadata.get('semantic_confidence', 0.0)
    if confidence > existing_confidence:
        kept, kept_confidence = semantic_type, confidence
        dropped = existing.element_type
        existing.element_type = semantic_type
        existing.metadata['semantic_confidence'] = confidence
        existing.metadata['source_file'] = str(file_path)
    else:
        kept, kept_confidence = existing.element_type, existing_confidence
        dropped = semantic_type
    summary.warnings.append(
        f"Element '{existing.label}' has conflicting semantic types: "
        f"kept '{kept}' (confidence {kept_confidence:.2f}), "
        f"dropped '{dropped}' from '{file_path}'"
    )


def _semantic_type_name(semantic_type: object) -> str:
    if not semantic_type:
        return 'generic'
    return str(getattr(semantic_type, 'value', semantic_type))


def _collapse_whitespace(label: str) -> str:
    return ' '.join(label.split())


def _normalize_name(label: str) -> str:
    return _collapse_whitespace(label).lower()


def _slugify(name: str) -> str:
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower())
    return slug.strip('-') or 'element'
