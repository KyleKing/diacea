"""SVG generator - draws the IR directly, with no external renderer.

The output shows a diagram exactly as diacea understood it: every shape at
its (original or synthesized) position, groups as labelled boundaries, and
connections as arrows. That makes it the quickest way to preview a
conversion or to check what was read from a drawing.

Each element carries a ``data-semantic`` attribute, which `SVGParser` reads
back as an explicit type hint.
"""

from __future__ import annotations

from html import escape

from ..ir import Connection, Diagram, Element, Generator, Group, Shape
from ..layout import ensure_layout, wrap_label
from ._text import canonical_shape, readable_id

_MARGIN = 24.0
_FONT_SIZE = 14
_LINE_HEIGHT = 18.0
_STROKE = '#1e1e1e'
_GROUP_STROKE = '#868e96'
_FILL = '#ffffff'
_CYLINDER_CAP = 10.0

_ARROW_MARKER = (
    '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" '
    f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{_STROKE}"/></marker></defs>'
)

_STYLE = (
    f'text{{font-family:Helvetica,Arial,sans-serif;font-size:{_FONT_SIZE}px;fill:{_STROKE}}}'
    f'.group-label{{font-size:12px;fill:{_GROUP_STROKE}}}'
    '.edge-label{font-size:12px;paint-order:stroke;stroke:#ffffff;stroke-width:4px}'
)


class SVGGenerator(Generator):
    """Generate a standalone SVG drawing from IR."""

    def generate(self, diagram: Diagram) -> str:
        """Generate SVG from IR.

        Args:
            diagram: IR Diagram object

        Returns:
            SVG document as a string
        """
        ensure_layout(diagram)
        shapes = diagram.get_shapes()
        groups = diagram.get_groups()
        source_shape_ids = {group.source_shape_id for group in groups}
        leaves = [shape for shape in shapes if shape.id not in source_shape_ids]
        boxes: list[Element] = [*groups, *leaves]
        if not boxes:
            return '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"/>'

        min_x = min(box.position.x for box in boxes) - _MARGIN
        min_y = min(box.position.y for box in boxes) - _MARGIN
        width = max(box.position.x + box.size.width for box in boxes) + _MARGIN - min_x
        height = max(box.position.y + box.size.height for box in boxes) + _MARGIN - min_y

        parts = [
            (
                f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" '
                f'viewBox="{min_x:.1f} {min_y:.1f} {width:.1f} {height:.1f}">'
            ),
            f'<style>{_STYLE}</style>',
            _ARROW_MARKER,
            f'<rect x="{min_x:.1f}" y="{min_y:.1f}" width="{width:.1f}" height="{height:.1f}" fill="#ffffff"/>',
        ]
        parts.extend(self._group(group) for group in sorted(groups, key=lambda g: -g.size.area))
        parts.extend(self._shape(shape) for shape in leaves)
        parts.extend(line for conn in diagram.get_connections() if (line := self._connection(conn)))
        parts.append('</svg>')
        return '\n'.join(parts)

    def _group(self, group: Group) -> str:
        x, y = group.position.x, group.position.y
        stroke = group.style.stroke_color or _GROUP_STROKE
        fill = group.style.fill_color or 'none'
        label = escape(group.label or readable_id(group.source_shape_id)).strip()
        return (
            f'<g id="{escape(group.id, quote=True)}" data-semantic="group">'
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{group.size.width:.1f}" height="{group.size.height:.1f}" rx="8" '
            f'fill="{fill}" fill-opacity="0.25" stroke="{stroke}" stroke-dasharray="6 4"/>'
            f'<text class="group-label" x="{x + 10:.1f}" y="{y + 18:.1f}">{label}</text></g>'
        )

    def _shape(self, shape: Shape) -> str:
        style = shape.style
        dash = ' stroke-dasharray="6 4"' if style.stroke_style in {'dashed', 'dotted'} else ''
        paint = (
            f'fill="{style.fill_color or _FILL}" stroke="{style.stroke_color or _STROKE}" '
            f'stroke-width="{style.stroke_width or 1.5}"{dash}'
        )
        semantic = getattr(shape.semantic_type, 'value', shape.semantic_type) or ''
        label = wrap_label(shape.label or readable_id(shape.id)).split('\n')
        center_x = shape.position.x + shape.size.width / 2
        first_line_y = shape.position.y + shape.size.height / 2 - (len(label) - 1) * _LINE_HEIGHT / 2 + _FONT_SIZE / 3
        text = ''.join(
            f'<text x="{center_x:.1f}" y="{first_line_y + index * _LINE_HEIGHT:.1f}" text-anchor="middle">'
            f'{escape(line)}</text>'
            for index, line in enumerate(label)
        )
        return (
            f'<g id="{escape(shape.id, quote=True)}" data-semantic="{escape(semantic, quote=True)}">'
            f'{_outline(shape, paint)}{text}</g>'
        )

    def _connection(self, conn: Connection) -> str:
        if conn.start_point is None or conn.end_point is None:
            return ''
        points = [conn.start_point, *conn.waypoints, conn.end_point]
        path = ' '.join(f'{point.x:.1f},{point.y:.1f}' for point in points)
        dash = ' stroke-dasharray="6 4"' if conn.style.stroke_style in {'dashed', 'dotted'} else ''
        end = '' if conn.connection_type == 'undirected' else ' marker-end="url(#arrow)"'
        start = ' marker-start="url(#arrow)"' if conn.connection_type == 'bidirectional' else ''
        line = (
            f'<polyline points="{path}" fill="none" stroke="{conn.style.stroke_color or _STROKE}" '
            f'stroke-width="{conn.style.stroke_width or 1.5}"{dash}{start}{end}/>'
        )
        if not conn.label:
            return line
        # Label the middle segment so the text sits on the line even when it bends
        before, after = points[(len(points) - 1) // 2], points[(len(points) - 1) // 2 + 1]
        middle_x = (before.x + after.x) / 2
        middle_y = (before.y + after.y) / 2
        label = ''.join(
            f'<text class="edge-label" x="{middle_x:.1f}" y="{middle_y + index * 14:.1f}" text-anchor="middle">'
            f'{escape(text)}</text>'
            for index, text in enumerate(conn.label.split('\n'))
        )
        return line + label


def _outline(shape: Shape, paint: str) -> str:
    x, y = shape.position.x, shape.position.y
    width, height = shape.size.width, shape.size.height
    kind = canonical_shape(shape.shape_type)
    if kind in {'ellipse', 'circle', 'person'}:
        return (
            f'<ellipse cx="{x + width / 2:.1f}" cy="{y + height / 2:.1f}" rx="{width / 2:.1f}" '
            f'ry="{height / 2:.1f}" {paint}/>'
        )
    if kind == 'diamond':
        points = f'{x + width / 2:.1f},{y:.1f} {x + width:.1f},{y + height / 2:.1f} '
        points += f'{x + width / 2:.1f},{y + height:.1f} {x:.1f},{y + height / 2:.1f}'
        return f'<polygon points="{points}" {paint}/>'
    if kind == 'hexagon':
        inset = min(width / 4, 20.0)
        points = f'{x + inset:.1f},{y:.1f} {x + width - inset:.1f},{y:.1f} {x + width:.1f},{y + height / 2:.1f} '
        points += f'{x + width - inset:.1f},{y + height:.1f} {x + inset:.1f},{y + height:.1f} '
        points += f'{x:.1f},{y + height / 2:.1f}'
        return f'<polygon points="{points}" {paint}/>'
    if kind == 'cylinder':
        cap = _CYLINDER_CAP
        body = (
            f'M{x:.1f},{y + cap:.1f} a{width / 2:.1f},{cap:.1f} 0 0 1 {width:.1f},0 v{height - 2 * cap:.1f} '
            f'a{width / 2:.1f},{cap:.1f} 0 0 1 {-width:.1f},0 z'
        )
        rim = f'M{x:.1f},{y + cap:.1f} a{width / 2:.1f},{cap:.1f} 0 0 0 {width:.1f},0'
        return f'<path d="{body}" {paint}/><path d="{rim}" fill="none" {paint.split(" ", 1)[1]}/>'
    radius = {'rounded_rectangle': 10.0, 'stadium': height / 2, 'queue': 10.0}.get(kind, 2.0)
    return f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" height="{height:.1f}" rx="{radius:.1f}" {paint}/>'


__all__ = ['SVGGenerator']
