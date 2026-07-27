"""Workspace support for multi-diagram management.

Enables management of related diagrams with shared element libraries,
particularly useful for C4 model hierarchies and other multi-view scenarios.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ElementDefinition:
    """Shared element definition that can be referenced across diagrams.

    Provides a single source of truth for element properties,
    ensuring consistency across multiple views.
    """

    id: str
    label: str
    description: str = ''
    element_type: str = 'component'  # system, container, component, etc.
    technology: str = ''
    style: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DiagramView:
    """A view/diagram within a workspace, referencing shared elements.

    Represents a specific perspective or zoom level of the architecture.
    """

    id: str
    name: str
    view_type: str  # "context", "container", "component", "sequence", etc.
    description: str = ''
    file: str = ''  # Path to diagram file
    zoom_level: int = 0  # C4: 1=Context, 2=Container, 3=Component, 4=Code
    parent_view: str | None = None  # For drill-down relationships
    focused_element: str | None = None  # Which element this zooms into
    element_refs: list[str] = field(default_factory=list)  # Elements used in this view


@dataclass
class Workspace:
    """Collection of related diagrams with shared element library.

    Manages multiple diagram views with consistent element definitions,
    enabling navigation, validation, and consistent styling across views.
    """

    id: str
    name: str
    description: str = ''

    # Shared element library - single source of truth
    elements: dict[str, ElementDefinition] = field(default_factory=dict)

    # Multiple views/diagrams
    views: dict[str, DiagramView] = field(default_factory=dict)

    # Metadata
    created: str = ''
    modified: str = ''
    author: str = ''
    version: str = '1.0.0'

    def get_element(self, element_id: str) -> ElementDefinition | None:
        """Get element definition by ID.

        Args:
            element_id: Element identifier

        Returns:
            ElementDefinition or None if not found
        """
        return self.elements.get(element_id)

    def get_view(self, view_id: str) -> DiagramView | None:
        """Get diagram view by ID.

        Args:
            view_id: View identifier

        Returns:
            DiagramView or None if not found
        """
        return self.views.get(view_id)

    def get_related_views(self, view_id: str) -> list[DiagramView]:
        """Get views related to this one (parent, children, siblings).

        Args:
            view_id: View identifier

        Returns:
            List of related DiagramView objects
        """
        view = self.views.get(view_id)
        if not view:
            return []

        related = []

        # Parent view
        if view.parent_view:
            parent = self.views.get(view.parent_view)
            if parent:
                related.append(parent)

        # Child views (views that have this as parent)
        related.extend(v for v in self.views.values() if v.parent_view == view_id)

        return related

    def get_child_views(self, view_id: str) -> list[DiagramView]:
        """Get all child views of a given view.

        Args:
            view_id: Parent view identifier

        Returns:
            List of child DiagramView objects
        """
        return [v for v in self.views.values() if v.parent_view == view_id]

    def get_parent_view(self, view_id: str) -> DiagramView | None:
        """Get parent view of a given view.

        Args:
            view_id: Child view identifier

        Returns:
            Parent DiagramView or None
        """
        view = self.views.get(view_id)
        if not view or not view.parent_view:
            return None
        return self.views.get(view.parent_view)

    def validate_references(self) -> list[str]:
        """Validate that all element references in views exist in element library.

        Returns:
            List of error messages (empty if valid)
        """
        errors: list[str] = []

        for view_id, view in self.views.items():
            errors.extend(
                f"View '{view_id}' references undefined element '{elem_ref}'"
                for elem_ref in view.element_refs
                if elem_ref not in self.elements
            )

            # Validate parent view exists
            if view.parent_view and view.parent_view not in self.views:
                errors.append(f"View '{view_id}' references undefined parent view '{view.parent_view}'")

            # Validate focused element exists
            if view.focused_element and view.focused_element not in self.elements:
                errors.append(f"View '{view_id}' focuses on undefined element '{view.focused_element}'")

        return errors

    def get_element_usage(self, element_id: str) -> list[str]:
        """Get list of views that use this element.

        Args:
            element_id: Element identifier

        Returns:
            List of view IDs that reference this element
        """
        usage = []
        for view_id, view in self.views.items():
            if element_id in view.element_refs:
                usage.append(view_id)
        return usage

    def add_element(self, element: ElementDefinition) -> None:
        """Add element to workspace library.

        Args:
            element: ElementDefinition to add
        """
        self.elements[element.id] = element

    def add_view(self, view: DiagramView) -> None:
        """Add view to workspace.

        Args:
            view: DiagramView to add
        """
        self.views[view.id] = view

    def remove_element(self, element_id: str) -> bool:
        """Remove element from workspace.

        Args:
            element_id: Element identifier

        Returns:
            True if element was removed, False if not found
        """
        if element_id in self.elements:
            del self.elements[element_id]
            return True
        return False

    def remove_view(self, view_id: str) -> bool:
        """Remove view from workspace.

        Args:
            view_id: View identifier

        Returns:
            True if view was removed, False if not found
        """
        if view_id in self.views:
            del self.views[view_id]
            return True
        return False

    def get_view_hierarchy(self) -> dict[str, list[str]]:
        """Get the hierarchical structure of views.

        Returns:
            Dictionary mapping parent view IDs to lists of child view IDs
        """
        hierarchy: dict[str, list[str]] = {}

        # Find root views (no parent)
        hierarchy['_root'] = []
        for view_id, view in self.views.items():
            if not view.parent_view:
                hierarchy['_root'].append(view_id)

        # Build parent → children mapping
        for view_id, view in self.views.items():
            if view.parent_view:
                if view.parent_view not in hierarchy:
                    hierarchy[view.parent_view] = []
                hierarchy[view.parent_view].append(view_id)

        return hierarchy
