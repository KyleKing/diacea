"""Excalidraw generator - converts IR to an editable Excalidraw scene.

Shapes become rectangles, ellipses, or diamonds with bound text labels,
connections become arrows bound to both endpoints (so they follow when a
shape is dragged), and groups become labelled container rectangles drawn
behind their children.

Excalidraw has only three closed shapes, so the original shape type and any
declared semantic type are stored in each element's
``customData.diacea``; `ExcalidrawParser` reads them back, which keeps a
cylinder a cylinder across a text -> Excalidraw -> text round trip.

Output is deterministic: element seeds derive from element ids, so
regenerating an unchanged diagram yields an identical file.
"""

from __future__ import annotations

import json
import zlib
from dataclasses import dataclass
from typing import Any

from ..ir import Connection, Diagram, Element, Generator, Group, Shape, Style
from ..layout import layout_diagram, wrap_label
from ._text import DECLARED_CONFIDENCE, canonical_shape

_SOURCE_URL = 'https://github.com/KyleKing/diacea'

_FONT_SIZE = 20
_LABEL_FONT_SIZE = 16
_LINE_HEIGHT = 1.25
_CHAR_WIDTH_RATIO = 0.55
_FONT_FAMILY = 5  # Excalifont
_ARROW_GAP = 4.0
_GROUP_LABEL_INSET = 10.0

_STROKE_COLOR = '#1e1e1e'
_GROUP_STROKE_COLOR = '#868e96'

_EXCALIDRAW_TYPES = {
    'circle': 'ellipse',
    'diamond': 'diamond',
    'ellipse': 'ellipse',
    'person': 'ellipse',
}

_ROUNDED_SHAPES = {'cylinder', 'queue', 'rounded_rectangle', 'stadium'}


@dataclass
class ExcalidrawConfig:
    """Configuration for the Excalidraw generator."""

    roughness: int = 1  # 0 = architect (clean), 1 = artist (hand-drawn), 2 = cartoonist
    indent: int | None = 2


class ExcalidrawGenerator(Generator):
    """Generate an Excalidraw scene (JSON text) from IR."""

    def __init__(self, config: ExcalidrawConfig | None = None) -> None:
        """Initialize generator.

        Args:
            config: Excalidraw configuration or None for defaults
        """
        self.config = config or ExcalidrawConfig()

    def generate(self, diagram: Diagram) -> str:
        """Generate an Excalidraw scene from IR.

        Args:
            diagram: IR Diagram object

        Returns:
            Excalidraw scene as a JSON string
        """
        if _needs_layout(diagram):
            layout_diagram(diagram, diagram.direction or 'TB')

        self._elements: list[dict[str, Any]] = []
        self._by_id: dict[str, dict[str, Any]] = {}

        groups = diagram.get_groups()
        source_shape_ids = {group.source_shape_id for group in groups}
        self._endpoint_ids = {group.source_shape_id: group.id for group in groups}

        for group in sorted(groups, key=lambda g: -g.size.area):
            self._add_group(group)
        for shape in diagram.get_shapes():
            if shape.id not in source_shape_ids:
                self._add_shape(shape)
        for connection in diagram.get_connections():
            self._add_connection(connection)

        scene = {
            'type': 'excalidraw',
            'version': 2,
            'source': _SOURCE_URL,
            'elements': self._elements,
            'appState': {'gridSize': None, 'viewBackgroundColor': '#ffffff'},
            'files': {},
        }
        return json.dumps(scene, indent=self.config.indent, ensure_ascii=False)

    def _element(
        self,
        element_id: str,
        element_type: str,
        box: tuple[float, float, float, float],
        style: Style | None = None,
    ) -> dict[str, Any]:
        """Append an element with the fields every Excalidraw element carries."""
        seed = zlib.crc32(element_id.encode('utf-8'))
        style = style or Style()
        x, y, width, height = box
        element = {
            'id': element_id,
            'type': element_type,
            'x': round(x, 2),
            'y': round(y, 2),
            'width': round(width, 2),
            'height': round(height, 2),
            'angle': 0,
            'strokeColor': style.stroke_color or _STROKE_COLOR,
            'backgroundColor': style.fill_color or 'transparent',
            'fillStyle': 'solid',
            'strokeWidth': style.stroke_width or 2,
            'strokeStyle': style.stroke_style if style.stroke_style in {'dashed', 'dotted'} else 'solid',
            'roughness': self.config.roughness,
            'opacity': round((style.opacity if style.opacity is not None else 1.0) * 100),
            'groupIds': [],
            'frameId': None,
            'roundness': None,
            'seed': seed,
            'version': 1,
            'versionNonce': seed ^ 0x5F5F5F5F,
            'isDeleted': False,
            'boundElements': [],
            'updated': 1,
            'link': None,
            'locked': False,
        }
        self._elements.append(element)
        self._by_id[element_id] = element
        return element

    def _boxed(self, element: Element, element_type: str) -> dict[str, Any]:
        box = (element.position.x, element.position.y, element.size.width, element.size.height)
        return self._element(element.id, element_type, box, element.style)

    def _add_text(
        self,
        text_id: str,
        content: str,
        container: dict[str, Any] | None,
        center: tuple[float, float],
        font_size: int = _FONT_SIZE,
    ) -> dict[str, Any]:
        wrapped = wrap_label(content) if container is not None and container['type'] != 'arrow' else content
        lines = wrapped.split('\n')
        width = max(len(line) for line in lines) * font_size * _CHAR_WIDTH_RATIO
        height = len(lines) * font_size * _LINE_HEIGHT
        text = self._element(text_id, 'text', (center[0] - width / 2, center[1] - height / 2, width, height))
        text.update(
            {
                'text': wrapped,
                'originalText': content,
                'fontSize': font_size,
                'fontFamily': _FONT_FAMILY,
                'textAlign': 'center',
                'verticalAlign': 'middle',
                'containerId': container['id'] if container else None,
                'autoResize': True,
                'lineHeight': _LINE_HEIGHT,
            }
        )
        if container is not None:
            container['boundElements'].append({'id': text_id, 'type': 'text'})
        return text

    def _add_group(self, group: Group) -> None:
        element = self._boxed(group, 'rectangle')
        element['strokeColor'] = group.style.stroke_color or _GROUP_STROKE_COLOR
        element['strokeWidth'] = group.style.stroke_width or 1
        element['roundness'] = {'type': 3}
        if not group.label:
            return
        label = self._add_text(f'{group.id}-label', group.label, None, (0.0, 0.0), _LABEL_FONT_SIZE)
        label['x'] = round(group.position.x + _GROUP_LABEL_INSET, 2)
        label['y'] = round(group.position.y + _GROUP_LABEL_INSET, 2)
        label['textAlign'] = 'left'
        label['verticalAlign'] = 'top'
        label['strokeColor'] = element['strokeColor']
        # Sharing a group id makes the label move with its container
        element['groupIds'] = label['groupIds'] = [f'{group.id}-frame']

    def _add_shape(self, shape: Shape) -> None:
        shape_type = canonical_shape(shape.shape_type)
        element = self._boxed(shape, _EXCALIDRAW_TYPES.get(shape_type, 'rectangle'))
        if shape_type in _ROUNDED_SHAPES:
            element['roundness'] = {'type': 3}

        hints: dict[str, str] = {}
        if shape_type != element['type']:
            hints['shape_type'] = shape_type
        if shape.semantic_type and shape.semantic_confidence >= DECLARED_CONFIDENCE:
            hints['semantic_type'] = getattr(shape.semantic_type, 'value', shape.semantic_type)
        if hints:
            element['customData'] = {'diacea': hints}

        if shape.label:
            center = (
                shape.position.x + shape.size.width / 2,
                shape.position.y + shape.size.height / 2,
            )
            self._add_text(f'{shape.id}-label', shape.label, element, center)

    def _add_connection(self, connection: Connection) -> None:
        source = self._by_id.get(self._endpoint_ids.get(connection.from_id, connection.from_id))
        target = self._by_id.get(self._endpoint_ids.get(connection.to_id, connection.to_id))
        start = connection.start_point
        end = connection.end_point
        if start is None or end is None:
            if source is None or target is None:
                return
            start_xy = (source['x'] + source['width'] / 2, source['y'] + source['height'] / 2)
            end_xy = (target['x'] + target['width'] / 2, target['y'] + target['height'] / 2)
        else:
            start_xy, end_xy = (start.x, start.y), (end.x, end.y)

        waypoints = [(point.x, point.y) for point in connection.waypoints]
        points = [start_xy, *waypoints, end_xy]
        xs = [x for x, _y in points]
        ys = [y for _x, y in points]

        arrow = self._boxed(connection, 'arrow')
        arrow.update(
            {
                'x': round(start_xy[0], 2),
                'y': round(start_xy[1], 2),
                'width': round(max(xs) - min(xs), 2),
                'height': round(max(ys) - min(ys), 2),
                'roundness': {'type': 2},
                'points': [[round(x - start_xy[0], 2), round(y - start_xy[1], 2)] for x, y in points],
                'lastCommittedPoint': None,
                'startBinding': _binding(source),
                'endBinding': _binding(target),
                'startArrowhead': 'arrow' if connection.connection_type == 'bidirectional' else None,
                'endArrowhead': None if connection.connection_type == 'undirected' else 'arrow',
                'elbowed': False,
            }
        )
        for endpoint in (source, target):
            if endpoint is not None:
                endpoint['boundElements'].append({'id': connection.id, 'type': 'arrow'})

        if connection.label:
            center = ((start_xy[0] + end_xy[0]) / 2, (start_xy[1] + end_xy[1]) / 2)
            self._add_text(f'{connection.id}-label', connection.label, arrow, center, _LABEL_FONT_SIZE)


def _binding(endpoint: dict[str, Any] | None) -> dict[str, Any] | None:
    if endpoint is None:
        return None
    return {'elementId': endpoint['id'], 'focus': 0, 'gap': _ARROW_GAP}


def _needs_layout(diagram: Diagram) -> bool:
    """Whether the shapes lack usable positions (e.g. a hand-built IR with everything at the origin)."""
    shapes = diagram.get_shapes()
    if len(shapes) < 2:
        return False
    return len({(shape.position.x, shape.position.y) for shape in shapes}) == 1


__all__ = ['ExcalidrawConfig', 'ExcalidrawGenerator']
