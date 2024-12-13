"""Experiment with different approaches."""
from __future__ import annotations

import networkx as nx
from constraint import Problem

# ==============================================================================
# Shared
# ==============================================================================


def is_rectangle_inside(outer, inner):
    return (
        outer['x'] < inner['x']
        and outer['y'] < inner['y']
        and outer['x'] + outer['width'] > inner['x'] + inner['width']
        and outer['y'] + outer['height'] > inner['y'] + inner['height']
    )


def _dist(rect: dict, arrow: tuple[int | float, int | float]) -> float:
    return sum(
        ((rect[center] + rect[side] / 2 - arrow) ** 2)
        for center, side, arrow in (
            ('x', 'width', arrow[0]),
            ('y', 'height', arrow[1]),
        )
    )


def find_nearest_rectangle(point, rectangles):
    candidates = [
        r
        for r in rectangles
        if (
            r['x'] <= point[0] <= r['x'] + r['width']
            and r['y'] <= point[1] <= r['y'] + r['height']
        )
    ]
    if not candidates:
        return min(rectangles, key=lambda r: _dist(r, point))
    return min(candidates, key=lambda r: r['width'] * r['height'])


# ==============================================================================
# Imperative Approach
# ==============================================================================


def convert_to_relative(absolute_data):
    # elements = {item["id"]: item for item in absolute_data}
    relative_data = []

    for item in absolute_data:
        if item['type'] in {'rectangle', 'text'}:
            relative_item = {
                'id': item['id'],
                'type': item['type'],
                'label': '',
                'parent': '',
            }

            # Find text within rectangle
            if item['type'] == 'rectangle':
                for text in absolute_data:
                    if text['type'] == 'text' and (
                        item['x'] < text['x'] < item['x'] + item['width']
                        and item['y'] < text['y'] < item['y'] + item['height']
                    ):
                        relative_item['label'] = text['text']
                        break
                relative_data.append(relative_item)
            # Don't store text

        elif item['type'] == 'arrow':
            arrow_start, arrow_end = item['points']

            from_element = min(
                (elem for elem in absolute_data if elem['type'] == 'rectangle'),
                key=lambda r: _dist(r, tuple(arrow_start)),
            )
            to_element = min(
                (elem for elem in absolute_data if elem['type'] == 'rectangle'),
                key=lambda r: _dist(r, tuple(arrow_end)),
            )

            relative_data.append(
                {
                    'id': item['id'],
                    'type': 'arrow',
                    # PLANNED: closest text that isn't within a rectangle. Maybe secondary step to look for free text (and other floating items?
                    'label': '',
                    'from': from_element['id'],
                    'to': to_element['id'],
                },
            )

    return relative_data


# ==============================================================================
# Rules Based Approach
# ==============================================================================


def rule_based_approach(data):
    rectangles = [item for item in data if item['type'] == 'rectangle']
    texts = [item for item in data if item['type'] == 'text']
    arrows = [item for item in data if item['type'] == 'arrow']

    output = []

    # Sort rectangles by area (largest to smallest)
    rectangles.sort(key=lambda r: r['width'] * r['height'], reverse=True)

    for rect in rectangles:
        # Find the smallest containing rectangle
        parent = None
        for potential_parent in rectangles:
            if potential_parent['id'] != rect['id'] and is_rectangle_inside(
                potential_parent, rect,
            ) and (parent is None or is_rectangle_inside(parent, potential_parent)):
                parent = potential_parent

        # Find text within this rectangle
        label = ''
        for text in texts:
            if (
                rect['x'] < text['x'] < rect['x'] + rect['width']
                and rect['y'] < text['y'] < rect['y'] + rect['height']
            ):
                label = text['text']
                break

        output_item = {'id': rect['id'], 'type': 'rectangle', 'label': label}
        if parent:
            output_item['parent'] = parent['id']

        output.append(output_item)

    # Process arrows
    for arrow in arrows:
        start, end = arrow['points']
        from_rect = find_nearest_rectangle(start, rectangles)
        to_rect = find_nearest_rectangle(end, rectangles)

        output.append(
            {
                'id': arrow['id'],
                'type': 'arrow',
                'label': '',
                'from': from_rect['id'],
                'to': to_rect['id'],
            },
        )

    return output


# ==============================================================================
# CSP Solver
# ==============================================================================


def csp_solver(data):
    problem = Problem()
    rectangles = [item for item in data if item['type'] == 'rectangle']
    texts = [item for item in data if item['type'] == 'text']
    arrows = [item for item in data if item['type'] == 'arrow']

    # Sort rectangles by area (largest to smallest)
    rectangles.sort(key=lambda r: r['width'] * r['height'], reverse=True)

    # Add variables
    for rect in rectangles:
        problem.addVariable(rect['id'], [text['text'] for text in texts] + [''])
        problem.addVariable(
            f"{rect['id']}_parent",
            [r['id'] for r in rectangles if r['id'] != rect['id']] + [None],
        )

    # Add constraints
    for rect in rectangles:

        def text_in_rectangle(label, rect=rect):
            return (
                any(
                    label == text['text']
                    and rect['x'] < text['x'] < rect['x'] + rect['width']
                    and rect['y'] < text['y'] < rect['y'] + rect['height']
                    for text in texts
                )
                or label == ''
            )

        problem.addConstraint(text_in_rectangle, [rect['id']])

        def valid_parent(parent, rect=rect):
            return parent is None or any(
                r['id'] == parent and is_rectangle_inside(r, rect)
                for r in rectangles
                if r['id'] != rect['id']
            )

        problem.addConstraint(valid_parent, [f"{rect['id']}_parent"])

    # Solve the problem
    solutions = problem.getSolutions()

    if not solutions:
        return None

    # Convert solution to output format
    output = []
    for rect in rectangles:
        output_item = {
            'id': rect['id'],
            'type': 'rectangle',
            'label': solutions[0][rect['id']],
        }
        parent = solutions[0][f"{rect['id']}_parent"]
        if parent is not None:
            output_item['parent'] = parent
        output.append(output_item)

    for arrow in arrows:
        start, end = arrow['points']
        from_rect = find_nearest_rectangle(start, rectangles)
        to_rect = find_nearest_rectangle(end, rectangles)

        output.append(
            {
                'id': arrow['id'],
                'type': 'arrow',
                'label': '',
                'from': from_rect['id'],
                'to': to_rect['id'],
            },
        )

    return output


# ==============================================================================
# QuadTree Solver
# ==============================================================================


class Rectangle:
    def __init__(self, x, y, w, h) -> None:
        self.x = x
        self.y = y
        self.w = w
        self.h = h

    def contains(self, item):
        return (
            self.x <= item['x'] < self.x + self.w
            and self.y <= item['y'] < self.y + self.h
        )

    def intersects(self, other) -> bool:
        return not (
            self.x + self.w <= other.x
            or other.x + other.w <= self.x
            or self.y + self.h <= other.y
            or other.y + other.h <= self.y
        )


class QuadTree:
    def __init__(self, boundary, capacity) -> None:
        self.boundary = boundary
        self.capacity = capacity
        self.items = []
        self.divided = False

    def insert(self, item):
        if not self.boundary.contains(item):
            return False

        if len(self.items) < self.capacity:
            self.items.append(item)
            return True

        if not self.divided:
            self.subdivide()

        return (
            self.northeast.insert(item)
            or self.northwest.insert(item)
            or self.southeast.insert(item)
            or self.southwest.insert(item)
        )

    def subdivide(self) -> None:
        x = self.boundary.x
        y = self.boundary.y
        w = self.boundary.w / 2
        h = self.boundary.h / 2

        ne = Rectangle(x + w, y, w, h)
        nw = Rectangle(x, y, w, h)
        se = Rectangle(x + w, y + h, w, h)
        sw = Rectangle(x, y + h, w, h)

        self.northeast = QuadTree(ne, self.capacity)
        self.northwest = QuadTree(nw, self.capacity)
        self.southeast = QuadTree(se, self.capacity)
        self.southwest = QuadTree(sw, self.capacity)

        self.divided = True

    def query(self, range):
        found = []
        if not self.boundary.intersects(range):
            return found

        found.extend(item for item in self.items if range.contains(item))

        if self.divided:
            found.extend(self.northeast.query(range))
            found.extend(self.northwest.query(range))
            found.extend(self.southeast.query(range))
            found.extend(self.southwest.query(range))

        return found


def quadtree_approach(data):
    # Find the bounding box
    min_x = min(item['x'] for item in data if 'x' in item)
    min_y = min(item['y'] for item in data if 'y' in item)
    max_x = max(item['x'] + item.get('width', 0) for item in data if 'x' in item)
    max_y = max(item['y'] + item.get('height', 0) for item in data if 'y' in item)

    # Create the quadtree
    boundary = Rectangle(min_x, min_y, max_x - min_x, max_y - min_y)
    qt = QuadTree(boundary, 4)

    # Insert all items into the quadtree
    for item in data:
        if 'x' in item and 'y' in item:
            qt.insert(item)

    rectangles = [item for item in data if item['type'] == 'rectangle']
    rectangles.sort(key=lambda r: r['width'] * r['height'], reverse=True)

    output = []
    for rect in rectangles:
        # Find text within this rectangle
        range = Rectangle(rect['x'], rect['y'], rect['width'], rect['height'])
        contained_items = qt.query(range)
        label = next(
            (text['text'] for text in contained_items if text['type'] == 'text'), '',
        )

        # Find parent rectangle
        parent = None
        for potential_parent in rectangles:
            if potential_parent['id'] != rect['id'] and is_rectangle_inside(
                potential_parent, rect,
            ) and (parent is None or is_rectangle_inside(parent, potential_parent)):
                parent = potential_parent

        output_item = {'id': rect['id'], 'type': 'rectangle', 'label': label}
        if parent:
            output_item['parent'] = parent['id']

        output.append(output_item)

    arrows = [item for item in data if item['type'] == 'arrow']
    for arrow in arrows:
        start, end = arrow['points']
        from_rect = find_nearest_rectangle(start, rectangles)
        to_rect = find_nearest_rectangle(end, rectangles)

        output.append(
            {
                'id': arrow['id'],
                'type': 'arrow',
                'label': '',
                'from': from_rect['id'],
                'to': to_rect['id'],
            },
        )

    return output


# ==============================================================================
# Graph-Based Solver
# ==============================================================================


def graph_based_approach(data):
    G = nx.DiGraph()  # Use directed graph to represent containment

    # Add nodes to the graph
    for item in data:
        G.add_node(item['id'], **item)

    # Add edges based on spatial relationships
    rectangles = [item for item in data if item['type'] == 'rectangle']
    texts = [item for item in data if item['type'] == 'text']

    # Sort rectangles by area (largest to smallest)
    rectangles.sort(key=lambda r: r['width'] * r['height'], reverse=True)

    for i, outer in enumerate(rectangles):
        for inner in rectangles[i + 1 :]:
            if is_rectangle_inside(outer, inner):
                G.add_edge(outer['id'], inner['id'], type='contains')

    # Add text containment
    for rect in rectangles:
        for text in texts:
            if (
                rect['x'] < text['x'] < rect['x'] + rect['width']
                and rect['y'] < text['y'] < rect['y'] + rect['height']
            ):
                G.add_edge(rect['id'], text['id'], type='contains')

    # Process arrows (unchanged)
    for item in data:
        if item['type'] == 'arrow':
            start, end = item['points']
            from_rect = find_nearest_rectangle(start, rectangles)
            to_rect = find_nearest_rectangle(end, rectangles)

            G.add_edge(
                from_rect['id'], to_rect['id'], type='arrow', arrow_id=item['id'],
            )

    return generate_output(G)


def generate_output(G):
    output = []
    for node in G.nodes():
        item = G.nodes[node]
        if item['type'] == 'rectangle':
            label = next(
                (
                    G.nodes[n]['text']
                    for n in G.successors(node)
                    if G.nodes[n]['type'] == 'text'
                ),
                '',
            )
            output_item = {'id': item['id'], 'type': 'rectangle', 'label': label}
            # Find the parent (if any)
            parents = [
                p for p in G.predecessors(node) if G.nodes[p]['type'] == 'rectangle'
            ]
            if parents:
                output_item['parent'] = parents[0]  # Assume only one parent
            output.append(output_item)

    for u, v, data in G.edges(data=True):
        if data['type'] == 'arrow':
            output.append(
                {
                    'id': data['arrow_id'],
                    'type': 'arrow',
                    'label': '',
                    'from': u,
                    'to': v,
                },
            )

    return output
