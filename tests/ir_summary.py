"""A compact, exact view of a parsed diagram, for comparing whole structures in one assertion."""

from diacea.ir import Diagram


def summarize(diagram: Diagram) -> dict[str, object]:
    """Nodes, groups, edges, and set styles, in source order; empty sections are left out."""
    summary: dict[str, object] = {
        'nodes': [
            (shape.id, shape.label, shape.shape_type, getattr(shape.semantic_type, 'value', shape.semantic_type))
            for shape in diagram.get_shapes()
        ],
        'groups': [(group.id, group.label, list(group.children)) for group in diagram.get_groups()],
        'edges': [(conn.from_id, conn.to_id, conn.label) for conn in diagram.get_connections()],
        'styles': {
            element.id: (element.style.fill_color, element.style.stroke_color, element.style.stroke_width)
            for element in diagram.elements
            if element.style.fill_color or element.style.stroke_color or element.style.stroke_width
        },
    }
    return {key: value for key, value in summary.items() if value}
