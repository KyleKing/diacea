"""TLDraw parser - converts TLDraw JSON to IR.

TLDraw is a modern infinite canvas diagramming tool with a structured JSON format.

Two on-disk formats are supported:
1. Legacy v1 documents: ``{"document": {"pages": {...}}}`` with per-page
   ``shapes``/``bindings`` dicts and ``point``/``size`` arrays.
2. Modern v2 ``.tldr`` files: ``{"tldrawFileFormatVersion": 1, "schema": {...},
   "records": [...]}`` where records is a flat array of typed records
   (see https://tldraw.dev/docs/persistence and packages/tlschema in
   https://github.com/tldraw/tldraw).

Design decisions:
1. Multi-page handling: Process all pages or specific page by index/id
2. Custom shapes: Map unknown types to rectangle, log warning
3. Freehand elements: Convert to polygon shapes with bounding box
4. v2 labels: ``props.richText`` (ProseMirror JSON) or older ``props.text``
"""

from __future__ import annotations

import logging
from typing import Any

from ..ir import (
    Connection,
    Diagram,
    Dimensions,
    Element,
    Group,
    Parser,
    Point,
    Shape,
    Style,
    Text,
)
from ..ir.semantic import infer_semantic_type

_logger = logging.getLogger(__name__)

_V2_COLOR_MAP = {
    'black': '#1d1d1d',
    'blue': '#4465e9',
    'green': '#099268',
    'grey': '#9fa8b2',
    'light-blue': '#4ba1f1',
    'light-green': '#4cb05e',
    'light-red': '#f87777',
    'light-violet': '#e085f4',
    'orange': '#e16919',
    'red': '#e03131',
    'violet': '#ae3ec9',
    'white': '#ffffff',
    'yellow': '#f1ac4b',
}

_V2_STROKE_WIDTH_MAP = {
    'l': 5.0,
    'm': 3.5,
    's': 2.0,
    'xl': 10.0,
}

_V2_GEO_TYPE_MAP = {
    'check-box': 'rectangle',
    'cloud': 'cloud',
    'diamond': 'diamond',
    'ellipse': 'ellipse',
    'hexagon': 'hexagon',
    'octagon': 'octagon',
    'oval': 'ellipse',
    'pentagon': 'pentagon',
    'rectangle': 'rectangle',
    'rhombus': 'diamond',
    'rhombus-2': 'diamond',
    'star': 'star',
    'trapezoid': 'trapezoid',
    'triangle': 'triangle',
    'x-box': 'rectangle',
}


def is_tldraw_v2(data: dict[str, Any]) -> bool:
    """Check whether data is a modern tldraw v2 record-store file."""
    return 'tldrawFileFormatVersion' in data or isinstance(data.get('records'), list)


def _extract_rich_text(node: Any) -> str:
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return ''.join(_extract_rich_text(child) for child in node)
    if isinstance(node, dict):
        if node.get('type') == 'text':
            return node.get('text', '')
        content = node.get('content', [])
        parts = [_extract_rich_text(child) for child in content]
        if node.get('type') == 'doc':
            return '\n'.join(part for part in parts if part)
        return ''.join(parts)
    return ''


def _v2_label(props: dict[str, Any]) -> str:
    if 'richText' in props:
        return _extract_rich_text(props['richText']).strip()
    text = props.get('text', '')
    return text.strip() if isinstance(text, str) else ''


def _v2_style(record: dict[str, Any]) -> Style:
    props = record.get('props', {})
    stroke_color = _V2_COLOR_MAP.get(props.get('color', 'black'), '#1d1d1d')
    fill = props.get('fill', 'none')
    fill_color = stroke_color if fill not in {None, 'none'} else None
    dash = props.get('dash', 'draw')
    stroke_style = 'dashed' if dash in {'dashed', 'dotted'} else 'solid'
    stroke_width = _V2_STROKE_WIDTH_MAP.get(props.get('size', 'm'), 3.5)

    opacity_raw = record.get('opacity', props.get('opacity'))
    opacity = float(opacity_raw) if opacity_raw is not None else None

    return Style(
        fill_color=fill_color,
        stroke_color=stroke_color,
        stroke_width=stroke_width,
        stroke_style=stroke_style,
        opacity=opacity,
    )


def _v2_shape_metadata(record: dict[str, Any]) -> dict[str, Any]:
    props = record.get('props', {})
    return {
        'type': record.get('type'),
        'parentId': record.get('parentId'),
        'index': record.get('index'),
        'rotation': record.get('rotation'),
        'isLocked': record.get('isLocked'),
        'props': {
            key: props[key] for key in ('geo', 'fill', 'dash', 'size', 'font', 'align', 'color', 'url') if key in props
        },
    }


def _nearest_shape(point: Point, shapes: list[Shape]) -> Shape | None:
    if not shapes:
        return None

    containing = [
        shape
        for shape in shapes
        if shape.position.x <= point.x <= shape.position.x + shape.size.width
        and shape.position.y <= point.y <= shape.position.y + shape.size.height
    ]
    if containing:
        return min(containing, key=lambda s: s.size.area)

    def distance(shape: Shape) -> float:
        center_x = shape.position.x + shape.size.width / 2
        center_y = shape.position.y + shape.size.height / 2
        return ((center_x - point.x) ** 2 + (center_y - point.y) ** 2) ** 0.5

    return min(shapes, key=distance)


def _resolve_page_id(shape_id: str, parent_map: dict[str, str | None]) -> str | None:
    current = shape_id
    seen: set[str] = set()
    while current in parent_map and current not in seen:
        seen.add(current)
        parent = parent_map[current]
        if parent is None:
            return None
        if parent.startswith('page:'):
            return parent
        current = parent
    return None


class TLDrawParser(Parser):
    """Parse TLDraw JSON to IR.

    Args:
        page_index: Index of page to process (0-based), or None for all pages
        page_id: ID of specific page to process, or None for all pages
        include_freehand: Whether to convert freehand drawings to shapes
    """

    def __init__(
        self,
        page_index: int | None = 0,
        page_id: str | None = None,
        include_freehand: bool = False,
    ) -> None:
        """Initialize parser with options."""
        self.page_index = page_index
        self.page_id = page_id
        self.include_freehand = include_freehand
        self.warnings: list[str] = []

    def parse(self, data: Any) -> Diagram:
        """Parse TLDraw document to IR diagram.

        Args:
            data: TLDraw JSON data (full document structure)

        Returns:
            IR Diagram object (merged if multiple pages)
        """
        self.warnings = []

        if isinstance(data, dict) and is_tldraw_v2(data):
            return self._parse_v2(data)

        pages = data.get('document', {}).get('pages', {})

        if not pages:
            return Diagram(id='empty', name='Empty Diagram', elements=[])

        pages_to_process = self._select_pages(pages)
        self._warn_skipped_pages(len(pages), len(pages_to_process))

        if not pages_to_process:
            return Diagram(id='empty', name='Empty Diagram', elements=[])

        all_elements: list[Element] = []
        diagram_name = 'TLDraw Diagram'
        diagram_id = 'diagram'

        for _page_id, page in pages_to_process:
            elements = self._parse_page(page)
            all_elements.extend(elements)

            if len(pages_to_process) == 1:
                diagram_name = page.get('name', 'TLDraw Diagram')
                diagram_id = page.get('id', 'diagram')

        if len(pages_to_process) > 1:
            diagram_name = f'TLDraw Diagram ({len(pages_to_process)} pages)'

        return Diagram(id=diagram_id, name=diagram_name, elements=all_elements)

    def _parse_v2(self, data: dict[str, Any]) -> Diagram:
        records = data.get('records', [])
        pages = sorted(
            (r for r in records if r.get('typeName') == 'page'),
            key=lambda r: str(r.get('index', '')),
        )
        selected_pages = self._select_v2_pages(pages)
        self._warn_skipped_pages(len(pages), len(selected_pages))

        metadata = {
            'tldraw': {
                'tldrawFileFormatVersion': data.get('tldrawFileFormatVersion'),
                'schema': data.get('schema', {}),
                'document': next((r for r in records if r.get('typeName') == 'document'), {}),
            }
        }

        if not selected_pages:
            return Diagram(id='empty', name='Empty Diagram', elements=[], metadata=metadata)

        shape_records = [r for r in records if r.get('typeName') == 'shape']
        arrow_bindings = [r for r in records if r.get('typeName') == 'binding' and r.get('type') == 'arrow']

        parent_map = {r['id']: r.get('parentId') for r in shape_records}
        page_ids = {p['id'] for p in selected_pages}
        page_shapes = [r for r in shape_records if _resolve_page_id(r['id'], parent_map) in page_ids]

        elements: list[Element] = []
        node_shapes: list[Shape] = []
        for record in page_shapes:
            parsed = self._parse_v2_shape(record, page_shapes)
            if parsed is not None:
                elements.append(parsed)
                if isinstance(parsed, Shape):
                    node_shapes.append(parsed)

        bindings_by_arrow: dict[str, dict[str, str]] = {}
        for binding in arrow_bindings:
            terminal = binding.get('props', {}).get('terminal')
            if terminal in {'start', 'end'}:
                bindings_by_arrow.setdefault(binding['fromId'], {})[terminal] = binding['toId']

        for record in page_shapes:
            if record.get('type') == 'arrow':
                conn = self._parse_v2_arrow(record, bindings_by_arrow.get(record['id'], {}), node_shapes)
                if conn is not None:
                    elements.append(conn)

        if len(selected_pages) == 1:
            diagram_id = selected_pages[0].get('id', 'diagram')
            diagram_name = selected_pages[0].get('name', 'TLDraw Diagram')
        else:
            diagram_id = 'diagram'
            diagram_name = f'TLDraw Diagram ({len(selected_pages)} pages)'

        return Diagram(id=diagram_id, name=diagram_name, elements=elements, metadata=metadata)

    def _warn_skipped_pages(self, total_pages: int, selected_pages: int) -> None:
        if 0 < selected_pages < total_pages:
            self.warnings.append(
                f'TLDraw document has {total_pages} pages; only {selected_pages} '
                'was converted (use page_index=None to merge all pages)'
            )

    def _select_v2_pages(self, pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if self.page_id:
            matches = [p for p in pages if p.get('id') == self.page_id]
            if matches:
                return matches
            _logger.warning('Page ID %s not found, processing first page', self.page_id)
            return pages[:1]

        if self.page_index is not None:
            if 0 <= self.page_index < len(pages):
                return [pages[self.page_index]]
            _logger.warning('Page index %d out of range, processing first page', self.page_index)
            return pages[:1]

        return pages

    def _parse_v2_shape(self, record: dict[str, Any], page_shapes: list[dict[str, Any]]) -> Shape | Group | Text | None:
        match record.get('type'):
            case 'arrow':
                return None
            case 'draw':
                return self._parse_v2_freehand(record)
            case 'frame' | 'group':
                return self._parse_v2_frame(record, page_shapes)
            case 'text':
                return self._parse_v2_text(record)
            case _:
                return self._parse_v2_geo(record)

    def _parse_v2_geo(self, record: dict[str, Any]) -> Shape:
        props = record.get('props', {})
        position = Point(x=float(record.get('x', 0.0)), y=float(record.get('y', 0.0)))
        size = Dimensions(width=float(props.get('w', 100.0)), height=float(props.get('h', 100.0)))
        label = _v2_label(props)
        style = _v2_style(record)

        record_type = record.get('type')
        if record_type == 'geo':
            ir_shape_type = _V2_GEO_TYPE_MAP.get(props.get('geo', 'rectangle'), 'rectangle')
        elif record_type == 'note':
            ir_shape_type = 'note'
        else:
            _logger.debug('Mapping unknown tldraw shape type %r to rectangle', record_type)
            ir_shape_type = 'rectangle'

        shape = Shape(
            id=record['id'],
            label=label,
            shape_type=ir_shape_type,
            position=position,
            size=size,
            style=style,
        )
        shape.metadata['tldraw'] = _v2_shape_metadata(record)

        shape.semantic_type, shape.semantic_confidence = infer_semantic_type(
            shape_type=ir_shape_type,
            label=label,
            size=size,
            style=style,
        )

        return shape

    def _parse_v2_frame(self, record: dict[str, Any], page_shapes: list[dict[str, Any]]) -> Group:
        props = record.get('props', {})
        children = [s['id'] for s in page_shapes if s.get('parentId') == record['id']]
        group = Group(
            id=record['id'],
            label=props.get('name', '') or _v2_label(props),
            position=Point(x=float(record.get('x', 0.0)), y=float(record.get('y', 0.0))),
            size=Dimensions(
                width=float(props.get('w', 100.0)),
                height=float(props.get('h', 100.0)),
            ),
            style=_v2_style(record),
            children=children,
        )
        group.metadata['tldraw'] = _v2_shape_metadata(record)
        return group

    def _parse_v2_text(self, record: dict[str, Any]) -> Text:
        props = record.get('props', {})
        text = Text(
            id=record['id'],
            content=_v2_label(props),
            alignment=props.get('textAlign', props.get('align', 'left')),
            position=Point(x=float(record.get('x', 0.0)), y=float(record.get('y', 0.0))),
            size=Dimensions(
                width=float(props.get('w', 100.0)),
                height=float(props.get('h', 30.0)),
            ),
            style=_v2_style(record),
        )
        text.metadata['tldraw'] = _v2_shape_metadata(record)
        return text

    def _parse_v2_freehand(self, record: dict[str, Any]) -> Shape | None:
        if not self.include_freehand:
            return None

        props = record.get('props', {})
        base_x = float(record.get('x', 0.0))
        base_y = float(record.get('y', 0.0))

        points = [point for segment in props.get('segments', []) for point in segment.get('points', [])]
        if not points:
            return None

        xs = [base_x + float(p['x']) for p in points]
        ys = [base_y + float(p['y']) for p in points]
        width = max(xs) - min(xs)
        height = max(ys) - min(ys)
        if width < 5 and height < 5:
            return None

        shape = Shape(
            id=record['id'],
            label='',
            shape_type='freehand',
            position=Point(x=min(xs), y=min(ys)),
            size=Dimensions(width=width, height=height),
            style=_v2_style(record),
        )
        shape.metadata['tldraw'] = _v2_shape_metadata(record)
        shape.metadata['freehand'] = {
            'point_count': len(points),
            'is_complete': props.get('isComplete', False),
        }
        return shape

    def _parse_v2_arrow(
        self,
        record: dict[str, Any],
        terminals: dict[str, str],
        shapes: list[Shape],
    ) -> Connection | None:
        props = record.get('props', {})
        base_x = float(record.get('x', 0.0))
        base_y = float(record.get('y', 0.0))

        start = props.get('start', {})
        end = props.get('end', {})
        start_point = Point(x=base_x + float(start.get('x', 0.0)), y=base_y + float(start.get('y', 0.0)))
        end_point = Point(x=base_x + float(end.get('x', 0.0)), y=base_y + float(end.get('y', 0.0)))

        from_id = terminals.get('start') or start.get('boundShapeId')
        to_id = terminals.get('end') or end.get('boundShapeId')

        if not from_id:
            from_shape = _nearest_shape(start_point, shapes)
            from_id = from_shape.id if from_shape else None
        if not to_id:
            to_shape = _nearest_shape(end_point, shapes)
            to_id = to_shape.id if to_shape else None

        if not from_id or not to_id or from_id == to_id:
            _logger.debug('Dropping arrow %r: unresolved endpoints', record.get('id'))
            return None

        arrowhead_start = props.get('arrowheadStart', 'none')
        arrowhead_end = props.get('arrowheadEnd', 'arrow')
        if arrowhead_start != 'none' and arrowhead_end != 'none':
            connection_type = 'bidirectional'
        elif arrowhead_start == 'none' and arrowhead_end == 'none':
            connection_type = 'undirected'
        else:
            connection_type = 'directed'

        conn = Connection(
            id=record['id'],
            from_id=from_id,
            to_id=to_id,
            label=_v2_label(props),
            connection_type=connection_type,
            position=Point(
                x=(start_point.x + end_point.x) / 2,
                y=(start_point.y + end_point.y) / 2,
            ),
            size=Dimensions(
                width=abs(end_point.x - start_point.x),
                height=abs(end_point.y - start_point.y),
            ),
            style=_v2_style(record),
            start_point=start_point,
            end_point=end_point,
        )
        conn.metadata['tldraw'] = _v2_shape_metadata(record)
        return conn

    def _select_pages(self, pages: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
        """Select pages to process based on parser options."""
        page_list = list(pages.items())

        if self.page_id:
            if self.page_id in pages:
                return [(self.page_id, pages[self.page_id])]
            _logger.warning('Page ID %s not found, processing first page', self.page_id)
            return [page_list[0]] if page_list else []

        if self.page_index is not None:
            if 0 <= self.page_index < len(page_list):
                return [page_list[self.page_index]]
            _logger.warning('Page index %d out of range, processing first page', self.page_index)
            return [page_list[0]] if page_list else []

        return page_list

    def _parse_page(self, page: dict[str, Any]) -> list[Element]:
        """Parse a single TLDraw page to IR elements."""
        elements: list[Element] = []

        shapes = page.get('shapes', {})
        bindings = page.get('bindings', {})

        for shape_id, shape_data in shapes.items():
            shape_type = shape_data.get('type')
            if shape_type == 'arrow':
                continue
            if shape_type == 'draw' and not self.include_freehand:
                continue

            parsed = self._parse_shape(shape_id, shape_data)
            if parsed:
                elements.append(parsed)

        for shape_id, shape_data in shapes.items():
            if shape_data.get('type') == 'arrow':
                conn = self._parse_arrow(shape_id, shape_data, bindings)
                if conn:
                    elements.append(conn)

        return elements

    def _parse_shape(self, shape_id: str, shape_data: dict[str, Any]) -> Shape | Group | Text | None:
        """Parse a TLDraw shape to IR element."""
        shape_type = shape_data.get('type')

        if shape_type == 'arrow':
            return None

        if shape_type == 'draw':
            return self._parse_freehand(shape_id, shape_data)

        point = shape_data.get('point', [0.0, 0.0])
        position = Point(x=float(point[0]), y=float(point[1]))

        size_data = shape_data.get('size', [100.0, 100.0])
        size = Dimensions(width=float(size_data[0]), height=float(size_data[1]))

        label = shape_data.get('label', shape_data.get('name', ''))

        style = self._parse_style(shape_data.get('style', {}))

        ir_shape_type = self._map_shape_type(shape_type)

        children_ids = shape_data.get('children', [])
        if children_ids:
            return Group(
                id=shape_id,
                label=label,
                position=position,
                size=size,
                style=style,
                children=children_ids,
            )

        if shape_type == 'text':
            return Text(
                id=shape_id,
                content=label,
                position=position,
                size=size,
                style=style,
            )

        shape = Shape(
            id=shape_id,
            label=label,
            shape_type=ir_shape_type,
            position=position,
            size=size,
            style=style,
        )

        shape.semantic_type, shape.semantic_confidence = infer_semantic_type(
            shape_type=ir_shape_type,
            label=label,
            size=size,
            style=style,
        )

        return shape

    def _parse_freehand(self, shape_id: str, shape_data: dict[str, Any]) -> Shape | None:
        """Parse TLDraw freehand drawing to IR Shape (polygon bounding box)."""
        point = shape_data.get('point', [0.0, 0.0])
        base_x, base_y = float(point[0]), float(point[1])

        points = shape_data.get('points', [])
        if not points:
            return None

        xs = [base_x + p[0] for p in points]
        ys = [base_y + p[1] for p in points]

        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        width = max_x - min_x
        height = max_y - min_y

        if width < 5 and height < 5:
            return None

        position = Point(x=min_x, y=min_y)
        size = Dimensions(width=width, height=height)
        style = self._parse_style(shape_data.get('style', {}))

        shape = Shape(
            id=shape_id,
            label='',
            shape_type='freehand',
            position=position,
            size=size,
            style=style,
        )

        shape.metadata['freehand'] = {
            'point_count': len(points),
            'is_complete': shape_data.get('isComplete', False),
        }

        return shape

    def _parse_arrow(
        self,
        arrow_id: str,
        arrow_data: dict[str, Any],
        bindings: dict[str, Any],
    ) -> Connection | None:
        """Parse TLDraw arrow to IR connection.

        Args:
            arrow_id: Arrow identifier
            arrow_data: Arrow data from TLDraw
            bindings: Bindings dictionary from page

        Returns:
            Parsed Connection or None if invalid
        """
        handles = arrow_data.get('handles', {})

        start_handle = handles.get('start', {})
        end_handle = handles.get('end', {})

        start_binding_id = start_handle.get('bindingId')
        end_binding_id = end_handle.get('bindingId')

        # Get bound shape IDs from bindings
        from_id = None
        to_id = None

        if start_binding_id and start_binding_id in bindings:
            from_id = bindings[start_binding_id].get('toId')

        if end_binding_id and end_binding_id in bindings:
            to_id = bindings[end_binding_id].get('toId')

        if not from_id or not to_id:
            return None  # Can't create connection without both endpoints

        # Get label
        label = arrow_data.get('label', '')

        # Parse style
        style = self._parse_style(arrow_data.get('style', {}))

        # Determine if bidirectional
        decorations = arrow_data.get('decorations', {})
        start_dec = decorations.get('start')
        end_dec = decorations.get('end')

        connection_type = 'directed'
        if start_dec == 'arrow' and end_dec == 'arrow':
            connection_type = 'bidirectional'

        # Calculate approximate position (center of arrow)
        point = arrow_data.get('point', [0.0, 0.0])
        position = Point(x=float(point[0]), y=float(point[1]))

        # Approximate size (arrows don't have meaningful size)
        size = Dimensions(width=100.0, height=0.0)

        return Connection(
            id=arrow_id,
            from_id=from_id,
            to_id=to_id,
            label=label,
            connection_type=connection_type,
            position=position,
            size=size,
            style=style,
        )

    def _parse_style(self, style_data: dict[str, Any]) -> Style:
        """Parse TLDraw style to IR style.

        TLDraw uses named colors and sizes that need mapping.

        Args:
            style_data: Style dictionary from TLDraw shape

        Returns:
            IR Style object
        """
        # TLDraw color mapping
        color_map = {
            'black': '#1d1d1d',
            'white': '#ffffff',
            'lightGray': '#c6cbd1',
            'gray': '#788492',
            'darkGray': '#1d1d1d',
            'red': '#ff0000',
            'orange': '#ff8800',
            'yellow': '#ffff00',
            'green': '#00ff00',
            'blue': '#0000ff',
            'indigo': '#4b0082',
            'violet': '#ee82ee',
        }

        # TLDraw size mapping
        size_map = {
            'small': 2.0,
            'medium': 3.0,
            'large': 5.0,
        }

        color = style_data.get('color', 'black')
        stroke_color = color_map.get(color, '#000000')

        size = style_data.get('size', 'medium')
        stroke_width = size_map.get(size, 3.0)

        is_filled = style_data.get('isFilled', False)
        fill_color = stroke_color if is_filled else None

        dash = style_data.get('dash', 'solid')
        stroke_style = 'dashed' if dash in {'dashed', 'dotted'} else 'solid'

        return Style(
            fill_color=fill_color,
            stroke_color=stroke_color,
            stroke_width=stroke_width,
            stroke_style=stroke_style,
        )

    def _map_shape_type(self, tldraw_type: str | None) -> str:
        """Map TLDraw shape type to IR shape type.

        Args:
            tldraw_type: TLDraw shape type name

        Returns:
            IR shape type name
        """
        if not tldraw_type:
            return 'rectangle'

        type_map = {
            'rectangle': 'rectangle',
            'ellipse': 'ellipse',
            'triangle': 'triangle',
            'diamond': 'diamond',
            'text': 'text',
            'draw': 'freehand',
            'sticky': 'note',
            'group': 'group',
        }

        return type_map.get(tldraw_type, 'rectangle')
