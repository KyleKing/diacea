"""SVG parser - converts basic SVG to IR.

Supports basic SVG shapes, text, groups, paths (including curve commands,
approximated by sampled points), and common transforms.
Does NOT support gradients, filters, or masks.

Design decisions:
1. Path support: all commands; curves (C/S/Q/T/A) are sampled so bounding
   boxes are accurate, but curved outlines still reduce to polygons/boxes
2. Transform support: translate, scale, rotate (basic)
3. Connection detection: Line elements can become connections
"""

from __future__ import annotations

import logging
import math
import re
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from ..ir import (
    Connection,
    Diagram,
    Dimensions,
    Group,
    Parser,
    Point,
    Shape,
    Style,
    Text,
)
from ..ir.semantic import SemanticType, infer_semantic_type

_logger = logging.getLogger(__name__)

_CURVE_COMMANDS_RE = re.compile(r'[CcSsQqTtAa]')
_CURVE_WARNING = (
    'SVG path curve commands (C/S/Q/T/A) are approximated by sampled points; '
    'curved outlines are reduced to polygons and bounding boxes'
)

_PATH_TOKEN_RE = re.compile(r'[MmLlHhVvCcSsQqTtAaZz]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?')
_PATH_COMMAND_ARITY = {'A': 7, 'C': 6, 'H': 1, 'L': 2, 'M': 2, 'Q': 4, 'S': 4, 'T': 2, 'V': 1, 'Z': 0}

_CURVE_SAMPLES = 16

_XY = tuple[float, float]


def _sample_cubic(p0: _XY, p1: _XY, p2: _XY, p3: _XY) -> list[_XY]:
    points = []
    for step in range(1, _CURVE_SAMPLES + 1):
        t = step / _CURVE_SAMPLES
        mt = 1.0 - t
        points.append((
            mt**3 * p0[0] + 3 * mt**2 * t * p1[0] + 3 * mt * t**2 * p2[0] + t**3 * p3[0],
            mt**3 * p0[1] + 3 * mt**2 * t * p1[1] + 3 * mt * t**2 * p2[1] + t**3 * p3[1],
        ))
    return points


def _sample_quadratic(p0: _XY, p1: _XY, p2: _XY) -> list[_XY]:
    points = []
    for step in range(1, _CURVE_SAMPLES + 1):
        t = step / _CURVE_SAMPLES
        mt = 1.0 - t
        points.append((
            mt**2 * p0[0] + 2 * mt * t * p1[0] + t**2 * p2[0],
            mt**2 * p0[1] + 2 * mt * t * p1[1] + t**2 * p2[1],
        ))
    return points


def _sample_arc(  # noqa: PLR0913
    start: _XY,
    rx: float,
    ry: float,
    rotation_deg: float,
    large_arc: bool,
    sweep: bool,
    end: _XY,
) -> list[_XY]:
    """Sample an elliptical arc via the SVG endpoint-to-center conversion (spec F.6.5)."""
    if start == end:
        return []
    rx, ry = abs(rx), abs(ry)
    if rx == 0 or ry == 0:
        return [end]

    phi = math.radians(rotation_deg % 360)
    cos_phi, sin_phi = math.cos(phi), math.sin(phi)
    dx2 = (start[0] - end[0]) / 2
    dy2 = (start[1] - end[1]) / 2
    x1p = cos_phi * dx2 + sin_phi * dy2
    y1p = -sin_phi * dx2 + cos_phi * dy2

    lam = x1p**2 / rx**2 + y1p**2 / ry**2
    if lam > 1:
        scale = math.sqrt(lam)
        rx *= scale
        ry *= scale

    numerator = rx**2 * ry**2 - rx**2 * y1p**2 - ry**2 * x1p**2
    denominator = rx**2 * y1p**2 + ry**2 * x1p**2
    coefficient = math.sqrt(max(numerator / denominator, 0.0))
    if large_arc == sweep:
        coefficient = -coefficient
    cxp = coefficient * rx * y1p / ry
    cyp = -coefficient * ry * x1p / rx
    cx = cos_phi * cxp - sin_phi * cyp + (start[0] + end[0]) / 2
    cy = sin_phi * cxp + cos_phi * cyp + (start[1] + end[1]) / 2

    theta1 = math.atan2((y1p - cyp) / ry, (x1p - cxp) / rx)
    theta2 = math.atan2((-y1p - cyp) / ry, (-x1p - cxp) / rx)
    delta = theta2 - theta1
    if sweep and delta < 0:
        delta += 2 * math.pi
    elif not sweep and delta > 0:
        delta -= 2 * math.pi

    points = []
    for step in range(1, _CURVE_SAMPLES + 1):
        theta = theta1 + delta * step / _CURVE_SAMPLES
        cos_t, sin_t = math.cos(theta), math.sin(theta)
        points.append((
            cx + rx * cos_t * cos_phi - ry * sin_t * sin_phi,
            cy + rx * cos_t * sin_phi + ry * sin_t * cos_phi,
        ))
    points[-1] = end
    return points


def _tokenize_path(d: str) -> Iterator[tuple[str, list[float]]]:
    tokens = _PATH_TOKEN_RE.findall(d)
    i = 0
    command: str | None = None
    while i < len(tokens):
        if tokens[i].isalpha():
            command = tokens[i]
            i += 1
        if command is None:
            i += 1
            continue
        arity = _PATH_COMMAND_ARITY[command.upper()]
        if arity == 0:
            yield (command, [])
            command = None
            continue
        if i + arity > len(tokens) or any(tokens[i + j].isalpha() for j in range(arity)):
            _logger.debug('Malformed SVG path data near token %d: %s', i, d[:80])
            return
        yield (command, [float(t) for t in tokens[i:i + arity]])
        i += arity
        if command == 'M':
            command = 'L'
        elif command == 'm':
            command = 'l'


@dataclass
class Transform:
    """2D transformation matrix representation."""

    translate_x: float = 0.0
    translate_y: float = 0.0
    scale_x: float = 1.0
    scale_y: float = 1.0
    rotate: float = 0.0
    rotate_cx: float = 0.0
    rotate_cy: float = 0.0

    def apply_point(self, x: float, y: float) -> tuple[float, float]:
        """Apply transformation to a point."""
        if self.rotate != 0:
            rad = math.radians(self.rotate)
            cos_r, sin_r = math.cos(rad), math.sin(rad)
            rx = x - self.rotate_cx
            ry = y - self.rotate_cy
            x = rx * cos_r - ry * sin_r + self.rotate_cx
            y = rx * sin_r + ry * cos_r + self.rotate_cy

        x = x * self.scale_x + self.translate_x
        y = y * self.scale_y + self.translate_y
        return (x, y)

    def apply_size(self, width: float, height: float) -> tuple[float, float]:
        """Apply scale transformation to dimensions."""
        return (width * abs(self.scale_x), height * abs(self.scale_y))

    def combine(self, other: 'Transform') -> 'Transform':
        """Combine with another transform (self applied first, then other)."""
        return Transform(
            translate_x=self.translate_x * other.scale_x + other.translate_x,
            translate_y=self.translate_y * other.scale_y + other.translate_y,
            scale_x=self.scale_x * other.scale_x,
            scale_y=self.scale_y * other.scale_y,
            rotate=self.rotate + other.rotate,
        )


def _parse_transform(transform_str: str | None) -> Transform:
    """Parse SVG transform attribute into Transform object."""
    if not transform_str:
        return Transform()

    result = Transform()

    translate_match = re.search(r'translate\(\s*([^,\s]+)(?:[,\s]+([^)]+))?\s*\)', transform_str)
    if translate_match:
        result.translate_x = float(translate_match.group(1))
        result.translate_y = float(translate_match.group(2) or 0)

    scale_match = re.search(r'scale\(\s*([^,\s]+)(?:[,\s]+([^)]+))?\s*\)', transform_str)
    if scale_match:
        result.scale_x = float(scale_match.group(1))
        result.scale_y = float(scale_match.group(2) or result.scale_x)

    rotate_match = re.search(r'rotate\(\s*([^,\s]+)(?:[,\s]+([^,\s]+)[,\s]+([^)]+))?\s*\)', transform_str)
    if rotate_match:
        result.rotate = float(rotate_match.group(1))
        if rotate_match.group(2):
            result.rotate_cx = float(rotate_match.group(2))
            result.rotate_cy = float(rotate_match.group(3))

    return result


class SVGParser(Parser):
    """Parse basic SVG to IR.

    Supports: rect, circle, ellipse, polygon, path (curves sampled), line, text, groups
    Does NOT support: gradients, filters
    """

    SVG_NS = '{http://www.w3.org/2000/svg}'

    def __init__(self):
        """Initialize parser."""
        self._id_counter = 0
        self._text_elements: dict[str, Text] = {}
        self._lines: list[tuple[str, Point, Point, Style]] = []
        self.warnings: list[str] = []

    def parse(self, data: Any) -> Diagram:
        """Parse SVG content to IR diagram.

        Args:
            data: SVG string or ElementTree Element

        Returns:
            IR Diagram object
        """
        if isinstance(data, str):
            root = ET.fromstring(data)
        else:
            root = data

        self._lines = []
        self._text_elements = {}
        self.warnings = []
        elements: list = []

        self._process_element(root, elements, transform=Transform(), parent_id=None)

        self._associate_text_labels(elements)

        connections = self._detect_connections_from_lines(elements)
        elements.extend(connections)

        return Diagram(
            id=root.get('id', 'svg-diagram'),
            name='SVG Diagram',
            elements=elements,
        )

    def _process_element(
        self,
        elem: ET.Element,
        elements: list,
        transform: Transform | None,
        parent_id: str | None,
    ) -> None:
        """Process SVG element recursively.

        Args:
            elem: SVG element to process
            elements: List to append parsed elements to
            transform: Current transformation
            parent_id: Parent element ID for grouping
        """
        tag = elem.tag.replace(self.SVG_NS, '')

        elem_transform = _parse_transform(elem.get('transform'))
        current_transform = transform.combine(elem_transform) if transform else elem_transform

        if tag == 'rect':
            shape = self._parse_rect(elem, current_transform)
            if shape:
                elements.append(shape)

        elif tag == 'circle':
            shape = self._parse_circle(elem, current_transform)
            if shape:
                elements.append(shape)

        elif tag == 'ellipse':
            shape = self._parse_ellipse(elem, current_transform)
            if shape:
                elements.append(shape)

        elif tag == 'polygon':
            shape = self._parse_polygon(elem, current_transform)
            if shape:
                elements.append(shape)

        elif tag == 'path':
            result = self._parse_path(elem, current_transform)
            if result:
                if isinstance(result, Shape):
                    elements.append(result)

        elif tag == 'line':
            self._parse_line(elem, current_transform)

        elif tag == 'polyline':
            self._parse_polyline(elem, current_transform)

        elif tag == 'text':
            text = self._parse_text(elem, current_transform)
            if text:
                self._text_elements[text.id] = text
                elements.append(text)

        elif tag == 'g':
            self._parse_group(elem, elements, current_transform)

        if tag != 'g':
            for child in elem:
                self._process_element(child, elements, current_transform, parent_id)

    def _parse_rect(self, elem: ET.Element, transform: Transform) -> Shape | None:
        """Parse SVG rect to IR Shape."""
        x = float(elem.get('x', 0))
        y = float(elem.get('y', 0))
        width = float(elem.get('width', 0))
        height = float(elem.get('height', 0))

        if width == 0 or height == 0:
            return None

        tx, ty = transform.apply_point(x, y)
        tw, th = transform.apply_size(width, height)

        position = Point(x=tx, y=ty)
        size = Dimensions(width=tw, height=th)
        style = self._parse_style_attrs(elem)

        shape_id = elem.get('id') or self._generate_id()
        label = elem.get('data-label', '')

        shape = Shape(
            id=shape_id,
            label=label,
            shape_type='rectangle',
            position=position,
            size=size,
            style=style,
        )

        semantic_hint = elem.get('data-semantic') or elem.get('class', '')
        if semantic_hint:
            shape.semantic_type = self._parse_semantic_hint(semantic_hint)
            shape.semantic_confidence = 0.9
        else:
            shape.semantic_type, shape.semantic_confidence = infer_semantic_type(
                shape_type='rectangle',
                label=label,
                size=size,
                style=style,
            )

        return shape

    def _parse_circle(self, elem: ET.Element, transform: Transform) -> Shape | None:
        """Parse SVG circle to IR Shape."""
        cx = float(elem.get('cx', 0))
        cy = float(elem.get('cy', 0))
        r = float(elem.get('r', 0))

        if r == 0:
            return None

        tcx, tcy = transform.apply_point(cx, cy)
        tr = r * max(abs(transform.scale_x), abs(transform.scale_y))

        position = Point(x=tcx - tr, y=tcy - tr)
        size = Dimensions(width=tr * 2, height=tr * 2)
        style = self._parse_style_attrs(elem)

        shape_id = elem.get('id') or self._generate_id()
        label = elem.get('data-label', '')

        shape = Shape(
            id=shape_id,
            label=label,
            shape_type='ellipse',
            position=position,
            size=size,
            style=style,
        )

        semantic_hint = elem.get('data-semantic')
        if semantic_hint:
            shape.semantic_type = self._parse_semantic_hint(semantic_hint)
            shape.semantic_confidence = 0.9
        else:
            shape.semantic_type, shape.semantic_confidence = infer_semantic_type(
                shape_type='ellipse',
                label=label,
                size=size,
                style=style,
            )

        return shape

    def _parse_ellipse(self, elem: ET.Element, transform: Transform) -> Shape | None:
        """Parse SVG ellipse to IR Shape."""
        cx = float(elem.get('cx', 0))
        cy = float(elem.get('cy', 0))
        rx = float(elem.get('rx', 0))
        ry = float(elem.get('ry', 0))

        if rx == 0 or ry == 0:
            return None

        tcx, tcy = transform.apply_point(cx, cy)
        trx = rx * abs(transform.scale_x)
        try_ = ry * abs(transform.scale_y)

        position = Point(x=tcx - trx, y=tcy - try_)
        size = Dimensions(width=trx * 2, height=try_ * 2)
        style = self._parse_style_attrs(elem)

        shape_id = elem.get('id') or self._generate_id()
        label = elem.get('data-label', '')

        shape = Shape(
            id=shape_id,
            label=label,
            shape_type='ellipse',
            position=position,
            size=size,
            style=style,
        )

        semantic_hint = elem.get('data-semantic')
        if semantic_hint:
            shape.semantic_type = self._parse_semantic_hint(semantic_hint)
            shape.semantic_confidence = 0.9
        else:
            shape.semantic_type, shape.semantic_confidence = infer_semantic_type(
                shape_type='ellipse',
                label=label,
                size=size,
                style=style,
            )

        return shape

    def _parse_polygon(self, elem: ET.Element, transform: Transform) -> Shape | None:
        """Parse SVG polygon to IR Shape (4 points = diamond, otherwise polygon)."""
        points_str = elem.get('points', '')
        if not points_str:
            return None

        coords = [float(x) for x in points_str.replace(',', ' ').split()]
        if len(coords) < 6:
            return None

        transformed_points = []
        for i in range(0, len(coords), 2):
            tx, ty = transform.apply_point(coords[i], coords[i + 1])
            transformed_points.extend([tx, ty])

        xs = transformed_points[0::2]
        ys = transformed_points[1::2]

        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        position = Point(x=min_x, y=min_y)
        size = Dimensions(width=max_x - min_x, height=max_y - min_y)

        shape_type = 'diamond' if len(coords) == 8 else 'polygon'

        style = self._parse_style_attrs(elem)
        shape_id = elem.get('id') or self._generate_id()
        label = elem.get('data-label', '')

        shape = Shape(
            id=shape_id,
            label=label,
            shape_type=shape_type,
            position=position,
            size=size,
            style=style,
        )

        semantic_hint = elem.get('data-semantic')
        if semantic_hint:
            shape.semantic_type = self._parse_semantic_hint(semantic_hint)
            shape.semantic_confidence = 0.9
        else:
            shape.semantic_type, shape.semantic_confidence = infer_semantic_type(
                shape_type=shape_type,
                label=label,
                size=size,
                style=style,
            )

        return shape

    def _parse_path(self, elem: ET.Element, transform: Transform) -> Shape | None:
        """Parse SVG path to IR Shape (curves are sampled so bounding boxes are accurate)."""
        d = elem.get('d', '')
        if not d:
            return None

        if _CURVE_COMMANDS_RE.search(d) and _CURVE_WARNING not in self.warnings:
            self.warnings.append(_CURVE_WARNING)

        points = self._parse_path_commands(d)
        if len(points) < 2:
            _logger.debug('Skipping path with < 2 points: %s', elem.get('id', 'unknown'))
            return None

        transformed = [transform.apply_point(p[0], p[1]) for p in points]

        xs = [p[0] for p in transformed]
        ys = [p[1] for p in transformed]

        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        width = max_x - min_x
        height = max_y - min_y

        if width < 5 and height < 5:
            return None

        position = Point(x=min_x, y=min_y)
        size = Dimensions(width=width, height=height)

        if len(points) == 2:
            start = Point(x=transformed[0][0], y=transformed[0][1])
            end = Point(x=transformed[1][0], y=transformed[1][1])
            style = self._parse_style_attrs(elem)
            line_id = elem.get('id') or self._generate_id()
            self._lines.append((line_id, start, end, style))
            return None

        style = self._parse_style_attrs(elem)
        shape_id = elem.get('id') or self._generate_id()
        label = elem.get('data-label', '')

        shape_type = 'polygon'
        if len(points) == 4:
            shape_type = 'diamond'
        elif len(points) == 5 and self._is_rectangle_path(points):
            shape_type = 'rectangle'

        shape = Shape(
            id=shape_id,
            label=label,
            shape_type=shape_type,
            position=position,
            size=size,
            style=style,
        )

        semantic_hint = elem.get('data-semantic')
        if semantic_hint:
            shape.semantic_type = self._parse_semantic_hint(semantic_hint)
            shape.semantic_confidence = 0.9
        else:
            shape.semantic_type, shape.semantic_confidence = infer_semantic_type(
                shape_type=shape_type,
                label=label,
                size=size,
                style=style,
            )

        return shape

    def _parse_path_commands(self, d: str) -> list[tuple[float, float]]:
        """Parse SVG path d attribute into sampled points for bounding-box computation."""
        points: list[tuple[float, float]] = []
        current_x, current_y = 0.0, 0.0
        start_x, start_y = 0.0, 0.0
        prev_cubic_ctrl: _XY | None = None
        prev_quad_ctrl: _XY | None = None

        for command, ops in _tokenize_path(d):
            relative = command.islower()
            ox, oy = (current_x, current_y) if relative else (0.0, 0.0)
            upper = command.upper()

            match upper:
                case 'M':
                    current_x, current_y = ox + ops[0], oy + ops[1]
                    start_x, start_y = current_x, current_y
                    points.append((current_x, current_y))
                case 'L':
                    current_x, current_y = ox + ops[0], oy + ops[1]
                    points.append((current_x, current_y))
                case 'H':
                    current_x = ox + ops[0]
                    points.append((current_x, current_y))
                case 'V':
                    current_y = oy + ops[0]
                    points.append((current_x, current_y))
                case 'C' | 'S':
                    if upper == 'C':
                        ctrl1 = (ox + ops[0], oy + ops[1])
                        ctrl2 = (ox + ops[2], oy + ops[3])
                        end = (ox + ops[4], oy + ops[5])
                    else:
                        ctrl1 = (
                            (2 * current_x - prev_cubic_ctrl[0], 2 * current_y - prev_cubic_ctrl[1])
                            if prev_cubic_ctrl
                            else (current_x, current_y)
                        )
                        ctrl2 = (ox + ops[0], oy + ops[1])
                        end = (ox + ops[2], oy + ops[3])
                    points.extend(_sample_cubic((current_x, current_y), ctrl1, ctrl2, end))
                    prev_cubic_ctrl = ctrl2
                    current_x, current_y = end
                case 'Q' | 'T':
                    if upper == 'Q':
                        ctrl = (ox + ops[0], oy + ops[1])
                        end = (ox + ops[2], oy + ops[3])
                    else:
                        ctrl = (
                            (2 * current_x - prev_quad_ctrl[0], 2 * current_y - prev_quad_ctrl[1])
                            if prev_quad_ctrl
                            else (current_x, current_y)
                        )
                        end = (ox + ops[0], oy + ops[1])
                    points.extend(_sample_quadratic((current_x, current_y), ctrl, end))
                    prev_quad_ctrl = ctrl
                    current_x, current_y = end
                case 'A':
                    end = (ox + ops[5], oy + ops[6])
                    points.extend(
                        _sample_arc((current_x, current_y), ops[0], ops[1], ops[2], bool(ops[3]), bool(ops[4]), end),
                    )
                    current_x, current_y = end
                case 'Z':
                    if points and (current_x != start_x or current_y != start_y):
                        points.append((start_x, start_y))
                    current_x, current_y = start_x, start_y

            if upper not in {'C', 'S'}:
                prev_cubic_ctrl = None
            if upper not in {'Q', 'T'}:
                prev_quad_ctrl = None

        return points

    def _is_rectangle_path(self, points: list[tuple[float, float]]) -> bool:
        """Check if path points form a rectangle."""
        if len(points) != 5:
            return False
        if points[0] != points[4]:
            return False

        xs = sorted({p[0] for p in points[:4]})
        ys = sorted({p[1] for p in points[:4]})

        return len(xs) == 2 and len(ys) == 2

    def _parse_line(self, elem: ET.Element, transform: Transform) -> None:
        """Parse SVG line element and store for connection detection."""
        x1 = float(elem.get('x1', 0))
        y1 = float(elem.get('y1', 0))
        x2 = float(elem.get('x2', 0))
        y2 = float(elem.get('y2', 0))

        tx1, ty1 = transform.apply_point(x1, y1)
        tx2, ty2 = transform.apply_point(x2, y2)

        style = self._parse_style_attrs(elem)
        line_id = elem.get('id') or self._generate_id()

        self._lines.append((line_id, Point(x=tx1, y=ty1), Point(x=tx2, y=ty2), style))

    def _parse_polyline(self, elem: ET.Element, transform: Transform) -> None:
        """Parse SVG polyline element and store segments for connection detection."""
        points_str = elem.get('points', '')
        if not points_str:
            return

        coords = [float(x) for x in points_str.replace(',', ' ').split()]
        if len(coords) < 4:
            return

        style = self._parse_style_attrs(elem)
        base_id = elem.get('id') or self._generate_id()

        for i in range(0, len(coords) - 2, 2):
            x1, y1 = coords[i], coords[i + 1]
            x2, y2 = coords[i + 2], coords[i + 3]

            tx1, ty1 = transform.apply_point(x1, y1)
            tx2, ty2 = transform.apply_point(x2, y2)

            segment_id = f'{base_id}_seg{i // 2}'
            self._lines.append((segment_id, Point(x=tx1, y=ty1), Point(x=tx2, y=ty2), style))

    def _detect_connections_from_lines(self, elements: list) -> list[Connection]:
        """Detect connections from line elements that connect shapes."""
        connections = []
        shapes = [e for e in elements if isinstance(e, Shape)]

        for line_id, start, end, style in self._lines:
            from_shape = self._find_shape_at_point(start, shapes)
            to_shape = self._find_shape_at_point(end, shapes)

            if from_shape and to_shape and from_shape.id != to_shape.id:
                conn = Connection(
                    id=line_id,
                    from_id=from_shape.id,
                    to_id=to_shape.id,
                    label='',
                    connection_type='directed',
                    position=Point(x=(start.x + end.x) / 2, y=(start.y + end.y) / 2),
                    size=Dimensions(width=abs(end.x - start.x), height=abs(end.y - start.y)),
                    style=style,
                    start_point=start,
                    end_point=end,
                )
                connections.append(conn)

        return connections

    def _find_shape_at_point(self, point: Point, shapes: list[Shape], tolerance: float = 10.0) -> Shape | None:
        """Find a shape that contains or is near a point."""
        for shape in shapes:
            if self._point_near_shape(point, shape, tolerance):
                return shape
        return None

    def _point_near_shape(self, point: Point, shape: Shape, tolerance: float) -> bool:
        """Check if point is inside or near shape bounds."""
        return (
            shape.position.x - tolerance <= point.x <= shape.position.x + shape.size.width + tolerance
            and shape.position.y - tolerance <= point.y <= shape.position.y + shape.size.height + tolerance
        )

    def _parse_text(self, elem: ET.Element, transform: Transform) -> Text | None:
        """Parse SVG text to IR Text."""
        x = float(elem.get('x', 0))
        y = float(elem.get('y', 0))

        content = ''.join(elem.itertext()).strip()
        if not content:
            return None

        tx, ty = transform.apply_point(x, y)
        position = Point(x=tx, y=ty)

        font_size = self._parse_font_size(elem)
        scaled_font = font_size * max(abs(transform.scale_x), abs(transform.scale_y))
        width = len(content) * scaled_font * 0.6
        height = scaled_font * 1.2

        size = Dimensions(width=width, height=height)
        style = self._parse_style_attrs(elem)
        style.font_size = scaled_font

        text_id = elem.get('id') or self._generate_id()

        return Text(
            id=text_id,
            content=content,
            position=position,
            size=size,
            style=style,
        )

    def _parse_group(
        self,
        elem: ET.Element,
        elements: list,
        transform: Transform,
    ) -> Group | None:
        """Parse SVG group to IR Group."""
        group_id = elem.get('id') or self._generate_id()

        child_elements: list = []
        for child in elem:
            self._process_element(child, child_elements, transform, parent_id=group_id)

        child_ids = [e.id for e in child_elements]

        if not child_elements:
            return None

        shapes = [e for e in child_elements if isinstance(e, Shape)]
        if not shapes:
            elements.extend(child_elements)
            return None

        min_x = min(s.position.x for s in shapes)
        min_y = min(s.position.y for s in shapes)
        max_x = max(s.position.x + s.size.width for s in shapes)
        max_y = max(s.position.y + s.size.height for s in shapes)

        position = Point(x=min_x, y=min_y)
        size = Dimensions(width=max_x - min_x, height=max_y - min_y)

        label = elem.get('data-label', '')

        group = Group(
            id=group_id,
            label=label,
            position=position,
            size=size,
            children=child_ids,
        )

        elements.append(group)
        elements.extend(child_elements)

        return group

    def _parse_style_attrs(self, elem: ET.Element) -> Style:
        """Parse SVG style attributes to IR Style.

        Args:
            elem: SVG element

        Returns:
            Style object
        """
        fill = elem.get("fill")
        stroke = elem.get("stroke")
        stroke_width = elem.get("stroke-width")
        stroke_dasharray = elem.get("stroke-dasharray")

        # Parse style attribute if present
        style_str = elem.get("style", "")
        if style_str:
            style_dict = self._parse_style_string(style_str)
            fill = style_dict.get("fill", fill)
            stroke = style_dict.get("stroke", stroke)
            stroke_width = style_dict.get("stroke-width", stroke_width)
            stroke_dasharray = style_dict.get("stroke-dasharray", stroke_dasharray)

        return Style(
            fill_color=fill if fill and fill != "none" else None,
            stroke_color=stroke if stroke and stroke != "none" else None,
            stroke_width=float(stroke_width) if stroke_width else None,
            stroke_style="dashed" if stroke_dasharray else "solid",
        )

    def _parse_style_string(self, style_str: str) -> dict[str, str]:
        """Parse SVG style string to dict.

        Args:
            style_str: CSS-like style string

        Returns:
            Dictionary of style properties
        """
        result = {}
        for item in style_str.split(";"):
            if ":" in item:
                key, value = item.split(":", 1)
                result[key.strip()] = value.strip()
        return result

    def _parse_font_size(self, elem: ET.Element) -> float:
        """Extract font size from element.

        Args:
            elem: SVG element

        Returns:
            Font size in pixels
        """
        font_size = elem.get("font-size")
        if font_size:
            # Remove units (px, pt, etc.)
            return float("".join(c for c in font_size if c.isdigit() or c == ".") or "14")

        # Check style attribute
        style_str = elem.get("style", "")
        style_dict = self._parse_style_string(style_str)
        if "font-size" in style_dict:
            fs = style_dict["font-size"]
            return float("".join(c for c in fs if c.isdigit() or c == ".") or "14")

        return 14.0  # Default

    def _parse_semantic_hint(self, hint: str) -> SemanticType | None:
        """Parse semantic type from hint string.

        Args:
            hint: Semantic hint from data-semantic or class

        Returns:
            SemanticType or None
        """
        hint_lower = hint.lower()

        hint_map = {
            "database": SemanticType.DATABASE,
            "db": SemanticType.DATABASE,
            "person": SemanticType.PERSON,
            "user": SemanticType.PERSON,
            "actor": SemanticType.PERSON,
            "system": SemanticType.SYSTEM,
            "component": SemanticType.COMPONENT,
            "service": SemanticType.SERVICE,
            "container": SemanticType.CONTAINER,
            "queue": SemanticType.QUEUE,
            "storage": SemanticType.STORAGE,
            "external": SemanticType.EXTERNAL,
            "cloud": SemanticType.CLOUD,
        }

        return hint_map.get(hint_lower)

    def _associate_text_labels(self, elements: list) -> None:
        """Associate text elements with nearby shapes as labels.

        Args:
            elements: List of all elements
        """
        shapes = [e for e in elements if isinstance(e, Shape) and not e.label]
        texts = [e for e in elements if isinstance(e, Text)]

        for text in texts:
            # Find shapes that contain this text
            for shape in shapes:
                if self._point_in_shape(text.position, shape):
                    shape.label = text.content
                    break

    def _point_in_shape(self, point: Point, shape: Shape) -> bool:
        """Check if point is inside shape bounds.

        Args:
            point: Point to check
            shape: Shape to check against

        Returns:
            True if point is inside shape
        """
        return (
            shape.position.x <= point.x <= shape.position.x + shape.size.width
            and shape.position.y <= point.y <= shape.position.y + shape.size.height
        )

    def _generate_id(self) -> str:
        """Generate unique ID.

        Returns:
            Unique element ID
        """
        self._id_counter += 1
        return f"elem_{self._id_counter}"
