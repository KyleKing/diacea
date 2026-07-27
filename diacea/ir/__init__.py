"""Intermediate Representation (IR) for diagrams.

This package provides format-agnostic representation of diagrams.
"""

from .base import Generator, Parser
from .elements import (
    Connection,
    Diagram,
    Dimensions,
    Element,
    GROUP_ID_PREFIX,
    Group,
    Point,
    Shape,
    Style,
    Text,
    IR_VERSION,
)
from .semantic import SemanticType, infer_semantic_type, validate_confidence
from .workspace import DiagramView, ElementDefinition, Workspace

__all__ = [
    # Base classes
    'Parser',
    'Generator',
    # Core elements
    'Point',
    'Dimensions',
    'Style',
    'Element',
    'Shape',
    'Connection',
    'Text',
    'GROUP_ID_PREFIX',
    'Group',
    'Diagram',
    # Semantic
    'SemanticType',
    'infer_semantic_type',
    'validate_confidence',
    # Workspace
    'Workspace',
    'ElementDefinition',
    'DiagramView',
    # Version
    'IR_VERSION',
]
