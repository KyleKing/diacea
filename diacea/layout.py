"""Synthesize positions for diagrams that carry no coordinates.

Text formats (Mermaid, PlantUML, DOT, D2) describe structure only. Parsers
call `layout_diagram` once to give every shape, group, and connection a
position so that position-aware consumers (direction detection, the Excalidraw
generator) work on any input.

The layout is a compound layered layout: each group is laid out on its own
and then treated as a single box in its parent, so nested containers never
overlap their siblings. Within a container, nodes are assigned to layers by
longest path along the flow direction and ordered by barycenter to keep
connected nodes near each other.
"""

from __future__ import annotations

import math
import textwrap
from collections import defaultdict
from dataclasses import dataclass

from .ir.elements import Diagram, Dimensions, Element, Group, Point, Shape

DIRECTIONS = ('TB', 'BT', 'LR', 'RL')

_CHAR_WIDTH = 11.0
_LINE_HEIGHT = 25.0
_WRAP_COLUMNS = 26
_MIN_WIDTH = 120.0
_MIN_HEIGHT = 60.0
_PADDING_X = 40.0
_PADDING_Y = 36.0


@dataclass(frozen=True)
class LayoutOptions:
    """Spacing used by `layout_diagram`."""

    node_gap: float = 50.0
    layer_gap: float = 90.0
    group_padding: float = 30.0
    group_header: float = 30.0


def wrap_label(label: str, columns: int = _WRAP_COLUMNS) -> str:
    """Break long label lines at word boundaries, keeping the author's own line breaks."""
    wrapped: list[str] = []
    for line in label.splitlines() or ['']:
        wrapped.extend(textwrap.wrap(line, width=columns, break_long_words=False) or [''])
    return '\n'.join(wrapped)


def estimate_label_size(label: str) -> Dimensions:
    """Estimate a box size that fits a label once long lines are wrapped."""
    lines = wrap_label(label).splitlines() or ['']
    width = max(_MIN_WIDTH, _CHAR_WIDTH * max(len(line) for line in lines) + _PADDING_X)
    height = max(_MIN_HEIGHT, _LINE_HEIGHT * len(lines) + _PADDING_Y)
    return Dimensions(width, height)


def layout_diagram(diagram: Diagram, direction: str = 'TB', options: LayoutOptions | None = None) -> None:
    """Assign positions to every shape, group, and connection of `diagram` in place.

    Args:
        diagram: Diagram whose shapes already have sizes
        direction: Flow direction, one of `DIRECTIONS`
        options: Spacing overrides
    """
    _Layout(diagram, direction if direction in DIRECTIONS else 'TB', options or LayoutOptions()).run()
    diagram.metadata['synthesized_layout'] = True


def route_connections(diagram: Diagram) -> None:
    """Set connection endpoints on the borders of the boxes they join."""
    boxes: dict[str, Element] = {}
    for element in diagram.elements:
        if isinstance(element, (Shape, Group)):
            boxes[element.id] = element
    for group in diagram.get_groups():
        boxes.setdefault(group.source_shape_id, group)

    for connection in diagram.get_connections():
        source = boxes.get(connection.from_id)
        target = boxes.get(connection.to_id)
        if source is None or target is None:
            continue
        start = _border_point(source, _center(target))
        end = _border_point(target, _center(source))
        connection.start_point = start
        connection.end_point = end
        connection.position = Point(min(start.x, end.x), min(start.y, end.y))
        connection.size = Dimensions(max(abs(end.x - start.x), 1.0), max(abs(end.y - start.y), 1.0))


def _center(element: Element) -> Point:
    return Point(
        element.position.x + element.size.width / 2,
        element.position.y + element.size.height / 2,
    )


def _border_point(element: Element, toward: Point) -> Point:
    """Point where the segment from the element's center to `toward` leaves its box."""
    center = _center(element)
    dx = toward.x - center.x
    dy = toward.y - center.y
    if dx == 0 and dy == 0:
        return center
    half_w = element.size.width / 2
    half_h = element.size.height / 2
    scale_x = half_w / abs(dx) if dx else math.inf
    scale_y = half_h / abs(dy) if dy else math.inf
    scale = min(scale_x, scale_y, 1.0)
    return Point(center.x + dx * scale, center.y + dy * scale)


class _Layout:
    def __init__(self, diagram: Diagram, direction: str, options: LayoutOptions) -> None:
        self._diagram = diagram
        self._horizontal = direction in {'LR', 'RL'}
        self._reversed = direction in {'RL', 'BT'}
        self._options = options
        self._groups = {group.id: group for group in diagram.get_groups()}
        source_ids = {group.source_shape_id for group in self._groups.values()}
        self._source_shapes = {shape.id: shape for shape in diagram.get_shapes() if shape.id in source_ids}
        self._nodes: dict[str, Element] = {
            shape.id: shape for shape in diagram.get_shapes() if shape.id not in self._source_shapes
        }
        self._nodes.update(self._groups)
        self._parent: dict[str, str] = {}
        for group in self._groups.values():
            for child_id in group.children:
                if child_id in self._nodes and child_id != group.id:
                    self._parent.setdefault(child_id, group.id)
        self._break_parent_cycles()
        self._children: dict[str | None, list[str]] = defaultdict(list)
        for node_id in self._nodes:
            self._children[self._parent.get(node_id)].append(node_id)
        self._edges = self._edges_by_container()
        self._relative: dict[str, tuple[float, float]] = {}

    def run(self) -> None:
        self._layout_container(None)
        self._absolutize(None, 0.0, 0.0)
        for group in self._groups.values():
            if (source := self._source_shapes.get(group.source_shape_id)) is not None:
                source.position = Point(group.position.x, group.position.y)
                source.size = Dimensions(group.size.width, group.size.height)
        route_connections(self._diagram)

    def _break_parent_cycles(self) -> None:
        for node_id in list(self._parent):
            seen = {node_id}
            current = node_id
            while (parent := self._parent.get(current)) is not None:
                if parent in seen:
                    del self._parent[current]
                    break
                seen.add(parent)
                current = parent

    def _ancestry(self, node_id: str) -> list[str]:
        """The node followed by its ancestors, innermost first."""
        chain = [node_id]
        while (parent := self._parent.get(chain[-1])) is not None:
            chain.append(parent)
        return chain

    def _edges_by_container(self) -> dict[str | None, list[tuple[str, str]]]:
        """Project each connection onto the two siblings it joins in their common container."""
        edges: dict[str | None, list[tuple[str, str]]] = defaultdict(list)
        source_to_group = {group.source_shape_id: group.id for group in self._groups.values()}
        for connection in self._diagram.get_connections():
            from_id = source_to_group.get(connection.from_id, connection.from_id)
            to_id = source_to_group.get(connection.to_id, connection.to_id)
            if from_id not in self._nodes or to_id not in self._nodes:
                continue
            from_chain = self._ancestry(from_id)
            to_chain = self._ancestry(to_id)
            if from_id in to_chain or to_id in from_chain:
                continue
            while len(from_chain) > 1 and len(to_chain) > 1 and from_chain[-1] == to_chain[-1]:
                from_chain.pop()
                to_chain.pop()
            if from_chain[-1] == to_chain[-1]:
                continue
            edges[self._parent.get(from_chain[-1])].append((from_chain[-1], to_chain[-1]))
        return edges

    def _layout_container(self, container_id: str | None) -> tuple[float, float]:
        """Place the container's children relative to its origin and return its content size."""
        child_ids = self._children.get(container_id, [])
        for child_id in child_ids:
            if child_id in self._groups:
                self._size_group(child_id)
        if not child_ids:
            return (0.0, 0.0)

        edges = self._edges.get(container_id, [])
        layers = self._ordered_layers(child_ids, edges) if edges else self._grid_layers(child_ids)

        def along(node_id: str) -> float:
            size = self._nodes[node_id].size
            return size.width if self._horizontal else size.height

        def across(node_id: str) -> float:
            size = self._nodes[node_id].size
            return size.height if self._horizontal else size.width

        gap = self._options.node_gap
        cross_extents = [sum(across(n) for n in layer) + gap * (len(layer) - 1) for layer in layers]
        max_cross = max(cross_extents)
        if self._reversed:
            layers.reverse()
            cross_extents.reverse()

        offset = 0.0
        for layer, cross_extent in zip(layers, cross_extents, strict=True):
            thickness = max(along(n) for n in layer)
            cursor = (max_cross - cross_extent) / 2
            for node_id in layer:
                along_position = offset + (thickness - along(node_id)) / 2
                self._relative[node_id] = (along_position, cursor) if self._horizontal else (cursor, along_position)
                cursor += across(node_id) + gap
            offset += thickness + self._options.layer_gap
        total_along = offset - self._options.layer_gap
        return (total_along, max_cross) if self._horizontal else (max_cross, total_along)

    def _size_group(self, group_id: str) -> None:
        group = self._groups[group_id]
        width, height = self._layout_container(group_id)
        padding = self._options.group_padding
        label_width = estimate_label_size(group.label).width
        group.size = Dimensions(
            max(width + 2 * padding, label_width),
            max(height + 2 * padding + self._options.group_header, _MIN_HEIGHT),
        )

    def _grid_layers(self, child_ids: list[str]) -> list[list[str]]:
        """Arrange unconnected siblings in a near-square grid."""
        per_layer = max(1, math.ceil(math.sqrt(len(child_ids))))
        if not self._horizontal:
            return [child_ids[i : i + per_layer] for i in range(0, len(child_ids), per_layer)]
        rows = math.ceil(len(child_ids) / per_layer)
        return [child_ids[i : i + rows] for i in range(0, len(child_ids), rows)]

    def _ordered_layers(self, child_ids: list[str], edges: list[tuple[str, str]]) -> list[list[str]]:
        forward = self._acyclic_edges(child_ids, edges)
        rank = self._longest_path_ranks(child_ids, forward)
        layers: list[list[str]] = [[] for _ in range(max(rank.values()) + 1)]
        for node_id in child_ids:
            layers[rank[node_id]].append(node_id)

        predecessors: dict[str, list[str]] = defaultdict(list)
        successors: dict[str, list[str]] = defaultdict(list)
        for from_id, to_id in forward:
            successors[from_id].append(to_id)
            predecessors[to_id].append(from_id)

        for neighbors, order in ((predecessors, range(1, len(layers))), (successors, range(len(layers) - 2, -1, -1))):
            for layer_index in order:
                slot = {node_id: index for layer in layers for index, node_id in enumerate(layer)}
                layers[layer_index].sort(key=lambda node_id: _barycenter(node_id, neighbors, slot))
        return layers

    @staticmethod
    def _acyclic_edges(child_ids: list[str], edges: list[tuple[str, str]]) -> list[tuple[str, str]]:
        """Drop the edges that close a cycle, keeping declaration order as the tie-break."""
        adjacency: dict[str, list[str]] = defaultdict(list)
        for from_id, to_id in dict.fromkeys(edges):
            adjacency[from_id].append(to_id)

        state: dict[str, int] = {}
        forward: list[tuple[str, str]] = []
        for root in child_ids:
            if root in state:
                continue
            state[root] = 1
            stack = [(root, iter(adjacency[root]))]
            while stack:
                node_id, targets = stack[-1]
                for target in targets:
                    if state.get(target) == 1:
                        continue
                    forward.append((node_id, target))
                    if target not in state:
                        state[target] = 1
                        stack.append((target, iter(adjacency[target])))
                        break
                else:
                    state[node_id] = 2
                    stack.pop()
        return forward

    @staticmethod
    def _longest_path_ranks(child_ids: list[str], edges: list[tuple[str, str]]) -> dict[str, int]:
        successors: dict[str, list[str]] = defaultdict(list)
        in_degree = dict.fromkeys(child_ids, 0)
        for from_id, to_id in edges:
            successors[from_id].append(to_id)
            in_degree[to_id] += 1
        rank = dict.fromkeys(child_ids, 0)
        ready = [node_id for node_id in child_ids if in_degree[node_id] == 0]
        while ready:
            node_id = ready.pop()
            for successor in successors[node_id]:
                rank[successor] = max(rank[successor], rank[node_id] + 1)
                in_degree[successor] -= 1
                if in_degree[successor] == 0:
                    ready.append(successor)
        return rank

    def _absolutize(self, container_id: str | None, origin_x: float, origin_y: float) -> None:
        pending = [(container_id, origin_x, origin_y)]
        while pending:
            current, base_x, base_y = pending.pop()
            for child_id in self._children.get(current, []):
                relative_x, relative_y = self._relative.get(child_id, (0.0, 0.0))
                node = self._nodes[child_id]
                node.position = Point(base_x + relative_x, base_y + relative_y)
                if child_id in self._groups:
                    padding = self._options.group_padding
                    pending.append(
                        (child_id, node.position.x + padding, node.position.y + padding + self._options.group_header)
                    )


def _barycenter(node_id: str, neighbors: dict[str, list[str]], slot: dict[str, int]) -> float:
    linked = neighbors.get(node_id)
    if not linked:
        return float(slot[node_id])
    return sum(slot[other] for other in linked) / len(linked)


__all__ = ['DIRECTIONS', 'LayoutOptions', 'estimate_label_size', 'layout_diagram', 'route_connections', 'wrap_label']
