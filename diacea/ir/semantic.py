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

import re
from enum import Enum
from typing import Any

from .elements import Dimensions, Style

# Confidence threshold for semantic inference warnings
CONFIDENCE_THRESHOLD = 0.7


class SemanticType(str, Enum):
    """Semantic types for diagram elements.

    Based on common architecture diagram patterns (C4, UML, etc.)
    """

    # C4 Model types
    PERSON = 'person'
    SYSTEM = 'system'
    CONTAINER = 'container'
    COMPONENT = 'component'

    # Infrastructure types
    DATABASE = 'database'
    QUEUE = 'queue'
    STORAGE = 'storage'
    SERVICE = 'service'

    # Network/deployment types
    SERVER = 'server'
    CLOUD = 'cloud'
    EXTERNAL = 'external'

    # UI types
    INTERFACE = 'interface'
    SCREEN = 'screen'

    # Data/document types
    DOCUMENT = 'document'
    FILE = 'file'

    # Flow types
    DECISION = 'decision'
    PROCESS = 'process'
    START_END = 'start_end'

    # Generic types (fallback)
    NOTE = 'note'
    GENERIC = 'generic'


# Keyword mappings for text-based inference
# Format: {semantic_type: [keywords]}
# More specific keywords listed first for priority matching
SEMANTIC_KEYWORDS = {
    SemanticType.DATABASE: [
        'database',
        'db',
        'sql',
        'postgres',
        'postgresql',
        'mysql',
        'mariadb',
        'mongodb',
        'redis',
        'dynamodb',
        'cassandra',
        'elasticsearch',
        'sqlite',
        'oracle',
        'mssql',
        'cockroachdb',
        'neo4j',
        'data store',
        'datastore',
        'cache',
        'memcached',
    ],
    SemanticType.PERSON: [
        'user',
        'person',
        'actor',
        'customer',
        'admin',
        'administrator',
        'operator',
        'developer',
        'engineer',
        'manager',
        'client',
        'visitor',
        'member',
        'staff',
    ],
    SemanticType.QUEUE: [
        'queue',
        'mq',
        'kafka',
        'rabbitmq',
        'sqs',
        'sns',
        'pubsub',
        'pub/sub',
        'message broker',
        'message bus',
        'event bus',
        'event stream',
        'kinesis',
        'nats',
        'activemq',
        'zeromq',
    ],
    SemanticType.STORAGE: [
        'storage',
        's3',
        'blob',
        'bucket',
        'file storage',
        'object store',
        'file system',
        'filesystem',
        'cdn',
        'cloudfront',
        'gcs',
        'minio',
    ],
    SemanticType.SERVICE: [
        'service',
        'api',
        'rest api',
        'graphql',
        'grpc',
        'microservice',
        'endpoint',
        'handler',
        'controller',
        'gateway',
        'proxy',
        'load balancer',
        'balancer',
        'nginx',
        'envoy',
        'backend',
        'frontend',
        'server',
        'worker',
        'lambda',
        'function',
        'serverless',
    ],
    SemanticType.CLOUD: [
        'cloud',
        'aws',
        'gcp',
        'azure',
        'kubernetes',
        'k8s',
        'eks',
        'gke',
        'aks',
        'ecs',
        'fargate',
        'heroku',
        'vercel',
        'netlify',
        'digitalocean',
        'linode',
        'infrastructure',
        'infra',
        'cluster',
        'region',
        'vpc',
        'network',
    ],
    SemanticType.EXTERNAL: [
        'external',
        'third party',
        '3rd party',
        'vendor',
        'saas',
        'partner',
        'integration',
        'legacy',
        'existing',
        'payment',
        'stripe',
        'paypal',
        'twilio',
        'sendgrid',
        'auth0',
        'okta',
        'oauth',
        'sso',
    ],
    SemanticType.SYSTEM: [
        'system',
        'platform',
        'application',
        'app',
        'product',
        'solution',
        'enterprise',
        'monolith',
        'core',
        'main',
    ],
    SemanticType.CONTAINER: [
        'container',
        'docker',
        'pod',
        'instance',
        'replica',
        'runtime',
        'image',
        'registry',
    ],
    SemanticType.COMPONENT: [
        'component',
        'module',
        'library',
        'package',
        'class',
        'util',
        'utility',
        'helper',
        'adapter',
        'connector',
        'repository',
        'repo',
        'dao',
        'orm',
        'model',
        'entity',
    ],
    SemanticType.INTERFACE: [
        'interface',
        'ui',
        'gui',
        'cli',
        'console',
        'terminal',
        'web app',
        'webapp',
        'website',
        'portal',
        'dashboard',
        'panel',
        'form',
    ],
    SemanticType.SCREEN: [
        'screen',
        'page',
        'view',
        'dialog',
        'modal',
        'window',
        'tab',
    ],
    SemanticType.DOCUMENT: [
        'document',
        'doc',
        'report',
        'pdf',
        'export',
        'template',
        'config',
        'configuration',
        'settings',
        'yaml',
        'json',
        'xml',
    ],
    SemanticType.FILE: [
        'file',
        'log',
        'logs',
        'artifact',
        'asset',
        'upload',
        'download',
    ],
    SemanticType.PROCESS: [
        'process',
        'workflow',
        'pipeline',
        'flow',
        'step',
        'task',
        'job',
        'batch',
        'cron',
        'scheduler',
        'action',
        'operation',
    ],
    SemanticType.DECISION: [
        'decision',
        'condition',
        'check',
        'validate',
        'if',
        'branch',
        'switch',
        'route',
        'filter',
    ],
    SemanticType.NOTE: [
        'note',
        'comment',
        'annotation',
        'todo',
        'fixme',
        'warning',
        'info',
        'hint',
        'tip',
    ],
}

_CAMEL_BOUNDARY_RE = re.compile(r'(?<=[a-z0-9])(?=[A-Z])')

_KEYWORD_PATTERNS = {
    semantic_type: re.compile(r'\b(?:' + '|'.join(re.escape(keyword) for keyword in keywords) + r')\b')
    for semantic_type, keywords in SEMANTIC_KEYWORDS.items()
}

# Shape type to semantic type mapping for strong inference
SHAPE_SEMANTIC_MAP = {
    'note': SemanticType.NOTE,
    'sticky': SemanticType.NOTE,
    'cylinder': SemanticType.DATABASE,
    'database': SemanticType.DATABASE,
    'cloud': SemanticType.CLOUD,
    'person': SemanticType.PERSON,
    'actor': SemanticType.PERSON,
    'queue': SemanticType.QUEUE,
    'document': SemanticType.DOCUMENT,
    'file': SemanticType.FILE,
    'parallelogram': SemanticType.INTERFACE,
    'hexagon': SemanticType.PROCESS,
    'stadium': SemanticType.START_END,
    'rounded_rectangle': SemanticType.PROCESS,
}

# Icon/emoji to semantic type mapping
ICON_SEMANTIC_MAP = {
    '👤': SemanticType.PERSON,
    '👥': SemanticType.PERSON,
    '🧑': SemanticType.PERSON,
    '🗄️': SemanticType.DATABASE,
    '💾': SemanticType.DATABASE,
    '📦': SemanticType.CONTAINER,
    '☁️': SemanticType.CLOUD,
    '🌐': SemanticType.EXTERNAL,
    '📄': SemanticType.DOCUMENT,
    '📁': SemanticType.FILE,
    '⚙️': SemanticType.SERVICE,
    '🔧': SemanticType.SERVICE,
    '📝': SemanticType.NOTE,
    '💬': SemanticType.NOTE,
    '❓': SemanticType.DECISION,
    '🔀': SemanticType.DECISION,
}


def infer_semantic_type(
    shape_type: str,
    label: str = '',
    size: Dimensions | None = None,
    style: Style | None = None,
    metadata: dict[str, Any] | None = None,
) -> tuple[SemanticType | None, float]:
    """Infer semantic type using hybrid approach.

    Priority order:
    1. Explicit user hints (metadata)
    2. Strong heuristics (shape + size + style)
    3. Icon/emoji detection in label
    4. Text-based hints (label keywords)
    5. Fallback to generic

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
        if 'semantic_type' in metadata:
            hint = metadata['semantic_type']
            try:
                return (SemanticType(hint), 1.0)
            except ValueError:
                pass  # Invalid hint, continue with other methods

        # Check for format-specific hints
        if 'data-semantic' in metadata:  # From SVG
            hint = metadata['data-semantic']
            semantic = _parse_semantic_hint(hint)
            if semantic:
                return (semantic, 0.95)

    # Priority 2: Strong heuristics (shape + size + style patterns)
    heuristic_result = _infer_from_heuristics(shape_type, size, style)
    if heuristic_result[0] and heuristic_result[1] >= 0.8:
        return heuristic_result

    # Priority 3: Icon/emoji detection in label
    icon_result = _infer_from_icons(label)
    if icon_result[0] and icon_result[1] >= 0.8:
        return icon_result

    # Priority 4: Text-based hints (label keywords)
    text_result = _infer_from_text(label)
    if text_result[0]:
        # If heuristics also found something, combine confidences
        if heuristic_result[0] == text_result[0]:
            combined_confidence = min(1.0, (heuristic_result[1] + text_result[1]) / 2 + 0.2)
            return (text_result[0], combined_confidence)
        # Text has higher confidence if different
        if text_result[1] > heuristic_result[1]:
            return text_result
        return heuristic_result

    # Priority 5: Fallback - return heuristic result or generic
    if heuristic_result[0]:
        return heuristic_result

    return (SemanticType.GENERIC, 0.3)


def _parse_semantic_hint(hint: str) -> SemanticType | None:
    """Parse semantic type from hint string."""
    hint_lower = hint.lower()

    # Direct mapping
    try:
        return SemanticType(hint_lower)
    except ValueError:
        pass

    # Alias mapping
    alias_map = {
        'db': SemanticType.DATABASE,
        'user': SemanticType.PERSON,
        'actor': SemanticType.PERSON,
        'mq': SemanticType.QUEUE,
        'api': SemanticType.SERVICE,
    }

    return alias_map.get(hint_lower)


def _infer_from_icons(label: str) -> tuple[SemanticType | None, float]:
    """Infer semantic type from icons/emojis in label."""
    if not label:
        return (None, 0.0)

    for icon, semantic_type in ICON_SEMANTIC_MAP.items():
        if icon in label:
            return (semantic_type, 0.85)

    return (None, 0.0)


def _infer_from_heuristics(
    shape_type: str,
    size: Dimensions | None,
    style: Style | None = None,
) -> tuple[SemanticType | None, float]:
    """Infer semantic type from shape, size, and style heuristics.

    Heuristic rules:
    - Direct shape mapping (note, cylinder, cloud, etc.) → High confidence
    - Ellipse → likely Person (if small-medium) or Database (if wider than tall)
    - Diamond → Decision node
    - Large rectangles → System boundary
    - Medium rectangles → Container
    - Small rectangles → Component
    - Very wide, short rectangles → Storage/Database
    - Yellow fill → Note
    - Gray/dashed border → External system
    """
    if not shape_type:
        return (None, 0.0)

    # Direct shape type mapping (highest confidence)
    if shape_type in SHAPE_SEMANTIC_MAP:
        return (SHAPE_SEMANTIC_MAP[shape_type], 0.9)

    # Style-based hints
    style_result = _infer_from_style(style)

    # Shape-based inference
    if shape_type in {'ellipse', 'circle'}:
        if size:
            aspect_ratio = size.width / size.height if size.height > 0 else 1.0
            if aspect_ratio > 2.0:  # Very wide ellipse
                return (SemanticType.DATABASE, 0.7)
            if size.area < 5000:  # Small circle/ellipse
                return (SemanticType.PERSON, 0.65)
        return (SemanticType.PERSON, 0.5)

    if shape_type == 'diamond':
        return (SemanticType.DECISION, 0.9)

    if shape_type == 'triangle':
        return (SemanticType.DECISION, 0.6)

    if shape_type == 'rectangle':
        # Check style hints first
        if style_result[0] and style_result[1] > 0.6:
            return style_result

        if size:
            area = size.area
            aspect_ratio = size.width / size.height if size.height > 0 else 1.0

            # Very large → System boundary
            if area > 100000:
                return (SemanticType.SYSTEM, 0.7)

            # Wide and short → Database/Storage
            if aspect_ratio > 3.0 and size.height < 100:
                return (SemanticType.DATABASE, 0.6)

            # Large → Container
            if area > 30000:
                return (SemanticType.CONTAINER, 0.6)

            # Medium → Component
            if area > 5000:
                return (SemanticType.COMPONENT, 0.55)

            # Small → Component or Note
            return (SemanticType.COMPONENT, 0.4)

        return (SemanticType.COMPONENT, 0.4)

    # Unknown shape - return style-based result if any
    if style_result[0]:
        return style_result

    return (None, 0.0)


def _infer_from_style(style: Style | None) -> tuple[SemanticType | None, float]:
    """Infer semantic type from visual style.

    Color conventions:
    - Yellow/amber fill → Note
    - Gray fill or dashed → External system
    - Blue fill → System/Container
    - Green fill → Service/Component
    """
    if not style:
        return (None, 0.0)

    fill = (style.fill_color or '').lower()

    # Yellow/amber → Note
    if fill and _is_yellow_color(fill):
        return (SemanticType.NOTE, 0.7)

    # Gray + dashed → External
    if style.stroke_style == 'dashed':
        if fill and _is_gray_color(fill):
            return (SemanticType.EXTERNAL, 0.65)
        return (SemanticType.EXTERNAL, 0.5)

    return (None, 0.0)


def _is_yellow_color(color: str) -> bool:
    """Check if color is in yellow/amber range."""
    yellow_hints = ['yellow', 'ffff', 'fff3', 'ffc', 'ffb', 'ffa', 'ff9', 'amber', 'gold']
    return any(hint in color for hint in yellow_hints)


def _is_gray_color(color: str) -> bool:
    """Check if color is gray."""
    if 'gray' in color or 'grey' in color:
        return True
    # Check for hex gray (r=g=b approximately)
    if color.startswith('#') and len(color) >= 7:
        try:
            r = int(color[1:3], 16)
            g = int(color[3:5], 16)
            b = int(color[5:7], 16)
            return abs(r - g) < 20 and abs(g - b) < 20 and abs(r - b) < 20
        except ValueError:
            pass
    return False


def _normalize_label_words(label: str) -> str:
    return _CAMEL_BOUNDARY_RE.sub(' ', label).replace('_', ' ').lower()


def _infer_from_text(label: str) -> tuple[SemanticType | None, float]:
    """Infer semantic type from whole-word keyword matches in the label."""
    if not label:
        return (None, 0.0)

    normalized = _normalize_label_words(label)
    for semantic_type, pattern in _KEYWORD_PATTERNS.items():
        if pattern.search(normalized):
            return (semantic_type, 0.8)

    return (None, 0.0)


def validate_confidence(semantic_type: SemanticType | None, confidence: float) -> str | None:
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
            f'Consider adding explicit hints in metadata.'
        )
    return None
