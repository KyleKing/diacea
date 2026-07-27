"""Intermediate Representation (IR) for diagrams.

This package provides format-agnostic representation of diagrams.
"""

from .base import Generator, Parser
from .elements import (
    GROUP_ID_PREFIX,
    IR_VERSION,
    Connection,
    Diagram,
    Dimensions,
    Element,
    Group,
    Point,
    Shape,
    Style,
    Text,
)
from .semantic import SemanticType, infer_semantic_type, validate_confidence
from .workspace import DiagramView, ElementDefinition, Workspace

__all__ = [
    'GROUP_ID_PREFIX',
    # Version
    'IR_VERSION',
    'Connection',
    'Diagram',
    'DiagramView',
    'Dimensions',
    'Element',
    'ElementDefinition',
    'Generator',
    'Group',
    # Base classes
    'Parser',
    # Core elements
    'Point',
    # Semantic
    'SemanticType',
    'Shape',
    'Style',
    'Text',
    # Workspace
    'Workspace',
    'infer_semantic_type',
    'validate_confidence',
]
