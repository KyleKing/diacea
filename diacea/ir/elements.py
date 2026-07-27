"""Core IR (Intermediate Representation) elements for diagrams.

This module defines the fundamental data structures for representing diagrams
in a format-agnostic way. The IR focuses on semantic meaning while preserving
geometric information for manual alignment.

Design principles (aligned with pandoc):
- Semantic meaning over visual representation
- Preserve geometry for manual layouts
- Efficient binary representation (metadata for roundtrip)
- Some data loss acceptable for conversion
- Version field for future compatibility
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


# Version of the IR format
IR_VERSION = '1.0.0'

# Prefix used for group IDs derived from container shapes
GROUP_ID_PREFIX = 'group-'


@dataclass
class Point:
    """2D point for positioning elements."""

    x: float
    y: float

    def __post_init__(self):
        """Validate coordinates."""
        self.x = float(self.x)
        self.y = float(self.y)


@dataclass
class Dimensions:
    """Size of an element."""

    width: float
    height: float

    def __post_init__(self):
        """Validate dimensions."""
        self.width = float(self.width)
        self.height = float(self.height)

    @property
    def area(self) -> float:
        """Calculate area."""
        return self.width * self.height


@dataclass
class Style:
    """Visual styling for elements.

    Preserves basic styling information. Format-specific advanced styling
    should be stored in metadata for round-tripping.
    """

    fill_color: Optional[str] = None  # Hex color or name
    stroke_color: Optional[str] = None  # Hex color or name
    stroke_width: Optional[float] = None
    stroke_style: str = 'solid'  # solid, dashed, dotted
    opacity: Optional[float] = None  # 0.0 to 1.0
    font_family: Optional[str] = None
    font_size: Optional[float] = None

    # Metadata for format-specific styling (preserves data for roundtrip)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Element:
    """Base class for all diagram elements."""

    id: str
    position: Point
    size: Dimensions
    element_type: str = ''  # shape, connection, text, group (set by subclass)
    style: Style = field(default_factory=Style)

    # Semantic information
    semantic_type: Optional[str] = None  # Will use enum in semantic.py
    semantic_confidence: float = 0.0  # 0.0 to 1.0

    # Metadata for format-specific data (preserves for roundtrip)
    # Example: {"excalidraw": {"roughness": 1}, "icon_url": "..."}
    metadata: dict[str, Any] = field(default_factory=dict)

    # Z-index for layering
    z_index: int = 0


@dataclass
class Shape(Element):
    """A shape element (rectangle, ellipse, etc.)."""

    label: str = ''
    shape_type: str = 'rectangle'  # rectangle, ellipse, diamond, etc.

    def __post_init__(self):
        """Set element type."""
        self.element_type = 'shape'


@dataclass
class Connection(Element):
    """A connection/arrow between elements."""

    from_id: str = ''
    to_id: str = ''
    label: str = ''
    connection_type: str = 'directed'  # directed, bidirectional, undirected

    # Connection points (optional, for precise routing)
    start_point: Optional[Point] = None
    end_point: Optional[Point] = None
    waypoints: list[Point] = field(default_factory=list)

    def __post_init__(self):
        """Set element type."""
        self.element_type = 'connection'


@dataclass
class Text(Element):
    """A text element."""

    content: str = ''
    alignment: str = 'left'  # left, center, right

    def __post_init__(self):
        """Set element type."""
        self.element_type = 'text'


@dataclass
class Group(Element):
    """A group/container of elements."""

    label: str = ''
    children: list[str] = field(default_factory=list)  # List of element IDs

    def __post_init__(self):
        """Set element type."""
        self.element_type = 'group'

    @property
    def source_shape_id(self) -> str:
        """ID of the container shape this group was derived from, if any."""
        return self.id.removeprefix(GROUP_ID_PREFIX)


@dataclass
class Diagram:
    """Complete diagram representation.

    A diagram contains all elements and metadata about the diagram itself.
    """

    id: str
    name: Optional[str] = None
    description: Optional[str] = None

    # All elements in the diagram
    elements: list[Element] = field(default_factory=list)

    # Metadata
    version: str = IR_VERSION  # IR version for compatibility
    created: Optional[str] = None
    modified: Optional[str] = None
    author: Optional[str] = None

    # Format-specific metadata (preserves for roundtrip)
    # Example: {"excalidraw": {"appState": {...}}}
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_element(self, element_id: str) -> Optional[Element]:
        """Get element by ID."""
        for elem in self.elements:
            if elem.id == element_id:
                return elem
        return None

    def get_elements_by_type(self, element_type: str) -> list[Element]:
        """Get all elements of a specific type."""
        return [elem for elem in self.elements if elem.element_type == element_type]

    def get_shapes(self) -> list[Shape]:
        """Get all shape elements."""
        return [elem for elem in self.elements if isinstance(elem, Shape)]

    def get_connections(self) -> list[Connection]:
        """Get all connection elements."""
        return [elem for elem in self.elements if isinstance(elem, Connection)]

    def get_groups(self) -> list[Group]:
        """Get all group elements."""
        return [elem for elem in self.elements if isinstance(elem, Group)]

    def get_texts(self) -> list[Text]:
        """Get all text elements."""
        return [elem for elem in self.elements if isinstance(elem, Text)]

    def add_element(self, element: Element) -> None:
        """Add an element to the diagram."""
        self.elements.append(element)

    def remove_element(self, element_id: str) -> bool:
        """Remove an element by ID. Returns True if removed."""
        initial_length = len(self.elements)
        self.elements = [elem for elem in self.elements if elem.id != element_id]
        return len(self.elements) < initial_length
