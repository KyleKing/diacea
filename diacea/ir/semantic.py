"""Semantic type inference for diagram elements.

This module implements hybrid semantic inference using:
1. Explicit user hints (highest priority)
2. Strong heuristics (size, shape, patterns)
3. Text-based hints (labels containing keywords)
4. Fallback to generic types

Design decisions (from Phase 1 open questions):
- Confidence threshold: 0.7 (warn below this)
- Ambiguous diagrams: Use highest confidence, warn user
- Performance: Clarity first, optimize if needed
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from .elements import Dimensions, Style


# Confidence threshold for semantic inference warnings
CONFIDENCE_THRESHOLD = 0.7


class SemanticType(str, Enum):
    """Semantic types for diagram elements.

    Based on common architecture diagram patterns (C4, UML, etc.)
    """

    # C4 Model types
    PERSON = "person"
    SYSTEM = "system"
    CONTAINER = "container"
    COMPONENT = "component"

    # Infrastructure types
    DATABASE = "database"
    QUEUE = "queue"
    STORAGE = "storage"
    SERVICE = "service"

    # Network/deployment types
    SERVER = "server"
    CLOUD = "cloud"
    EXTERNAL = "external"

    # UI types
    INTERFACE = "interface"
    SCREEN = "screen"

    # Data/document types
    DOCUMENT = "document"
    FILE = "file"

    # Flow types
    DECISION = "decision"
    PROCESS = "process"
    START_END = "start_end"

    # Generic types (fallback)
    NOTE = "note"
    GENERIC = "generic"


# Keyword mappings for text-based inference
# Format: {semantic_type: [keywords]}
SEMANTIC_KEYWORDS = {
    SemanticType.DATABASE: [
        "database",
        "db",
        "sql",
        "postgres",
        "mysql",
        "mongodb",
        "redis",
        "dynamodb",
        "data store",
        "datastore",
    ],
    SemanticType.PERSON: [
        "user",
        "person",
        "actor",
        "customer",
        "admin",
        "operator",
        "developer",
    ],
    SemanticType.QUEUE: [
        "queue",
        "mq",
        "kafka",
        "rabbitmq",
        "sqs",
        "pubsub",
        "message",
        "event bus",
    ],
    SemanticType.STORAGE: [
        "storage",
        "s3",
        "blob",
        "bucket",
        "file storage",
        "object store",
    ],
    SemanticType.SERVICE: [
        "service",
        "api",
        "microservice",
        "endpoint",
        "handler",
    ],
    SemanticType.CLOUD: [
        "cloud",
        "aws",
        "gcp",
        "azure",
        "kubernetes",
        "k8s",
        "eks",
        "gke",
    ],
    SemanticType.EXTERNAL: [
        "external",
        "third party",
        "3rd party",
        "vendor",
        "saas",
    ],
    SemanticType.SYSTEM: [
        "system",
        "platform",
        "application",
        "app",
    ],
    SemanticType.CONTAINER: [
        "container",
        "docker",
        "pod",
        "instance",
    ],
    SemanticType.COMPONENT: [
        "component",
        "module",
        "library",
        "package",
    ],
}


def infer_semantic_type(
    shape_type: str,
    label: str = "",
    size: Optional[Dimensions] = None,
    style: Optional[Style] = None,
    metadata: Optional[dict] = None,
) -> tuple[Optional[SemanticType], float]:
    """Infer semantic type using hybrid approach.

    Priority order:
    1. Explicit user hints (metadata)
    2. Strong heuristics (shape + size)
    3. Text-based hints (label keywords)
    4. Fallback to generic

    Args:
        shape_type: Geometric shape type (rectangle, ellipse, etc.)
        label: Element label text
        size: Element dimensions
        style: Element styling
        metadata: Additional metadata (may contain hints)

    Returns:
        Tuple of (semantic_type, confidence)
        - semantic_type: Inferred SemanticType or None
        - confidence: Float from 0.0 to 1.0
    """
    # Priority 1: Explicit user hints (highest confidence)
    if metadata:
        # Check for explicit semantic type hint
        if "semantic_type" in metadata:
            hint = metadata["semantic_type"]
            try:
                return (SemanticType(hint), 1.0)
            except ValueError:
                pass  # Invalid hint, continue with other methods

        # Check for format-specific hints
        if "data-semantic" in metadata:  # From SVG
            hint = metadata["data-semantic"]
            semantic = _parse_semantic_hint(hint)
            if semantic:
                return (semantic, 0.95)

    # Priority 2: Strong heuristics (shape + size patterns)
    heuristic_result = _infer_from_heuristics(shape_type, size)
    if heuristic_result[0] and heuristic_result[1] >= 0.8:
        return heuristic_result

    # Priority 3: Text-based hints (label keywords)
    text_result = _infer_from_text(label)
    if text_result[0]:
        # If heuristics also found something, combine confidences
        if heuristic_result[0] == text_result[0]:
            combined_confidence = min(
                1.0, (heuristic_result[1] + text_result[1]) / 2 + 0.2
            )
            return (text_result[0], combined_confidence)
        # Text has higher confidence if different
        if text_result[1] > heuristic_result[1]:
            return text_result
        return heuristic_result

    # Priority 4: Fallback - return heuristic result or generic
    if heuristic_result[0]:
        return heuristic_result

    return (SemanticType.GENERIC, 0.3)


def _parse_semantic_hint(hint: str) -> Optional[SemanticType]:
    """Parse semantic type from hint string."""
    hint_lower = hint.lower()

    # Direct mapping
    try:
        return SemanticType(hint_lower)
    except ValueError:
        pass

    # Alias mapping
    alias_map = {
        "db": SemanticType.DATABASE,
        "user": SemanticType.PERSON,
        "actor": SemanticType.PERSON,
        "mq": SemanticType.QUEUE,
        "api": SemanticType.SERVICE,
    }

    return alias_map.get(hint_lower)


def _infer_from_heuristics(
    shape_type: str, size: Optional[Dimensions]
) -> tuple[Optional[SemanticType], float]:
    """Infer semantic type from shape and size heuristics.

    Heuristic rules:
    - Ellipse → likely Person (if small-medium) or Database (if wider than tall)
    - Diamond → Decision node
    - Large rectangles → System boundary
    - Medium rectangles → Container
    - Small rectangles → Component
    - Very wide, short rectangles → Storage/Database
    """
    if not shape_type:
        return (None, 0.0)

    # Shape-based inference
    if shape_type == "ellipse" or shape_type == "circle":
        if size:
            aspect_ratio = size.width / size.height if size.height > 0 else 1.0
            if aspect_ratio > 2.0:  # Very wide ellipse
                return (SemanticType.DATABASE, 0.7)
            elif size.area < 5000:  # Small circle/ellipse
                return (SemanticType.PERSON, 0.65)
        return (SemanticType.PERSON, 0.5)

    elif shape_type == "diamond":
        return (SemanticType.DECISION, 0.9)

    elif shape_type == "rectangle":
        if size:
            area = size.area
            aspect_ratio = size.width / size.height if size.height > 0 else 1.0

            # Very large → System boundary
            if area > 100000:
                return (SemanticType.SYSTEM, 0.7)

            # Wide and short → Database/Storage
            elif aspect_ratio > 3.0 and size.height < 100:
                return (SemanticType.DATABASE, 0.6)

            # Large → Container
            elif area > 30000:
                return (SemanticType.CONTAINER, 0.6)

            # Medium → Component
            elif area > 5000:
                return (SemanticType.COMPONENT, 0.55)

            # Small → Component or Note
            else:
                return (SemanticType.COMPONENT, 0.4)

        return (SemanticType.COMPONENT, 0.4)

    return (None, 0.0)


def _infer_from_text(label: str) -> tuple[Optional[SemanticType], float]:
    """Infer semantic type from label text keywords."""
    if not label:
        return (None, 0.0)

    label_lower = label.lower()

    # Check each semantic type's keywords
    best_match = None
    best_confidence = 0.0

    for semantic_type, keywords in SEMANTIC_KEYWORDS.items():
        for keyword in keywords:
            if keyword in label_lower:
                # Exact word match gets higher confidence
                words = label_lower.split()
                if keyword in words:
                    confidence = 0.8
                else:
                    confidence = 0.65

                if confidence > best_confidence:
                    best_match = semantic_type
                    best_confidence = confidence

    return (best_match, best_confidence)


def validate_confidence(
    semantic_type: Optional[SemanticType], confidence: float
) -> Optional[str]:
    """Validate confidence level and return warning if below threshold.

    Args:
        semantic_type: Inferred semantic type
        confidence: Confidence score

    Returns:
        Warning message if confidence below threshold, None otherwise
    """
    if semantic_type and confidence < CONFIDENCE_THRESHOLD:
        return (
            f"Low confidence ({confidence:.2f}) for semantic type '{semantic_type.value}'. "
            f"Consider adding explicit hints in metadata."
        )
    return None
