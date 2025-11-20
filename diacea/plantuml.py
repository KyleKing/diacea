"""Generate PlantUML from relative format."""

from __future__ import annotations


def generate_c4_plantuml(excalidraw_elements: list[dict]) -> str:
    """Generate C4-PlantUML from Excalidraw elements.

    Args:
        excalidraw_elements: Raw Excalidraw elements with absolute positions

    Returns:
        C4-PlantUML diagram as a string
    """
    lines = [
        '@startuml',
        '!include https://raw.githubusercontent.com/plantuml-stdlib/C4-PlantUML/master/C4_Component.puml',
        '',
        'LAYOUT_WITH_LEGEND()',
        '',
    ]

    # Build element map for quick lookup
    elements_map = {elem['id']: elem for elem in excalidraw_elements}

    # Categorize elements
    rectangles = [elem for elem in excalidraw_elements if elem.get('type') == 'rectangle']
    diamonds = [elem for elem in excalidraw_elements if elem.get('type') == 'diamond']
    ellipses = [elem for elem in excalidraw_elements if elem.get('type') == 'ellipse']
    arrows = [elem for elem in excalidraw_elements if elem.get('type') == 'arrow']

    # Classify rectangles as system boundaries or containers
    system_boundaries = []
    containers = []

    for rect in rectangles:
        text = _get_element_text(rect, elements_map)
        is_boundary = (
            rect.get('width', 0) > 500
            or rect.get('height', 0) > 500
            or 'cloud' in text.lower()
            or 'eks' in text.lower()
        )
        if is_boundary:
            system_boundaries.append(rect)
        else:
            containers.append(rect)

    # Sort system boundaries by size (largest first)
    system_boundaries.sort(key=lambda r: r.get('width', 0) * r.get('height', 0), reverse=True)

    # Define people (diamonds)
    for person in diamonds:
        text = _get_element_text(person, elements_map) or 'User'
        sanitized_id = _sanitize_id(person['id'])
        lines.append(f'Person({sanitized_id}, "{text}")')

    # Define system boundaries and their contents
    processed_containers: set[str] = set()
    processed_boundaries: set[str] = set()

    for boundary in system_boundaries:
        if boundary['id'] in processed_boundaries:
            continue

        boundary_text = _get_element_text(boundary, elements_map) or 'System'
        sanitized_id = _sanitize_id(boundary['id'])
        lines.append(f'System_Boundary({sanitized_id}, "{boundary_text}") {{')

        # Find nested system boundaries
        for nested in system_boundaries:
            if (
                nested['id'] != boundary['id']
                and nested['id'] not in processed_boundaries
                and _is_inside(boundary, nested)
            ):
                nested_text = _get_element_text(nested, elements_map) or 'Nested System'
                nested_id = _sanitize_id(nested['id'])
                lines.append(f'    System_Boundary({nested_id}, "{nested_text}") {{')

                # Find containers within nested boundary
                for container in containers:
                    if container['id'] not in processed_containers and _is_inside(nested, container):
                        lines.append('        ' + _convert_container(container, elements_map))
                        processed_containers.add(container['id'])

                # Add ellipses (databases) within nested boundary
                for ellipse in ellipses:
                    if ellipse['id'] not in processed_containers and _is_inside(nested, ellipse):
                        lines.append('        ' + _convert_container(ellipse, elements_map))
                        processed_containers.add(ellipse['id'])

                lines.append('    }')
                processed_boundaries.add(nested['id'])

        # Find containers directly within this boundary
        for container in containers:
            if container['id'] not in processed_containers and _is_inside(boundary, container):
                lines.append('    ' + _convert_container(container, elements_map))
                processed_containers.add(container['id'])

        # Add ellipses (databases) directly within this boundary
        for ellipse in ellipses:
            if ellipse['id'] not in processed_containers and _is_inside(boundary, ellipse):
                lines.append('    ' + _convert_container(ellipse, elements_map))
                processed_containers.add(ellipse['id'])

        lines.append('}')
        lines.append('')
        processed_boundaries.add(boundary['id'])

    # Define standalone containers and databases
    for container in containers:
        if container['id'] not in processed_containers:
            lines.append(_convert_container(container, elements_map))

    for ellipse in ellipses:
        if ellipse['id'] not in processed_containers:
            lines.append(_convert_container(ellipse, elements_map))

    # Define relationships
    for arrow in arrows:
        start_binding = arrow.get('startBinding', {})
        end_binding = arrow.get('endBinding', {})

        if not start_binding or not end_binding:
            continue

        start_id = start_binding.get('elementId')
        end_id = end_binding.get('elementId')

        if not start_id or not end_id or start_id == end_id:
            continue

        start_elem = elements_map.get(start_id)
        end_elem = elements_map.get(end_id)

        # Skip relationships to/from text elements
        if (
            not start_elem
            or not end_elem
            or start_elem.get('type') == 'text'
            or end_elem.get('type') == 'text'
        ):
            continue

        # Find label for relationship
        label = _get_arrow_label(arrow, elements_map)

        sanitized_start = _sanitize_id(start_id)
        sanitized_end = _sanitize_id(end_id)
        lines.append(f'Rel({sanitized_start}, {sanitized_end}, "{label}")')

    lines.append('')
    lines.append('@enduml')

    return '\n'.join(lines)


def _is_inside(outer: dict, inner: dict) -> bool:
    """Check if inner element is inside outer element."""
    return (
        outer['x'] <= inner['x']
        and outer['y'] <= inner['y']
        and outer['x'] + outer.get('width', 0) >= inner['x'] + inner.get('width', 0)
        and outer['y'] + outer.get('height', 0) >= inner['y'] + inner.get('height', 0)
    )


def _convert_container(elem: dict, elements_map: dict) -> str:
    """Convert element to C4 container or database."""
    text = _get_element_text(elem, elements_map) or 'Box'
    sanitized_id = _sanitize_id(elem['id'])

    # Check if this is a database
    if elem.get('type') == 'ellipse' or 'database' in text.lower():
        return f'ComponentDb({sanitized_id}, "{text}")\n'

    return f'Container({sanitized_id}, "{text}")\n'


def _get_element_text(elem: dict, elements_map: dict) -> str:
    """Get text label for an element."""
    # Check element's own text
    if elem.get('text'):
        return elem['text'].replace('\n', ' ').strip()

    # Check bound text elements
    bound_elements = elem.get('boundElements') or []
    for bound in bound_elements:
        if isinstance(bound, dict):
            bound_id = bound.get('id')
            if bound_id and bound_id in elements_map:
                bound_elem = elements_map[bound_id]
                if bound_elem.get('type') == 'text' and bound_elem.get('text'):
                    return bound_elem['text'].replace('\n', ' ').strip()

    # For rectangles, look for text positioned within
    if elem.get('type') == 'rectangle':
        for other_elem in elements_map.values():
            if other_elem.get('type') == 'text' and other_elem.get('text'):
                # Check if text is inside rectangle
                if _is_text_in_rect(elem, other_elem):
                    return other_elem['text'].replace('\n', ' ').strip()

    return ''


def _is_text_in_rect(rect: dict, text_elem: dict) -> bool:
    """Check if text element is positioned within rectangle."""
    return (
        rect['x'] <= text_elem['x']
        and rect['y'] <= text_elem['y']
        and rect['x'] + rect.get('width', 0) >= text_elem['x'] + text_elem.get('width', 0)
        and rect['y'] + rect.get('height', 0) >= text_elem['y'] + text_elem.get('height', 0)
    )


def _get_arrow_label(arrow: dict, elements_map: dict) -> str:
    """Get label for an arrow relationship."""
    # Check for bound text elements
    bound_elements = arrow.get('boundElements') or []
    for bound in bound_elements:
        if isinstance(bound, dict):
            bound_id = bound.get('id')
            if bound_id and bound_id in elements_map:
                bound_elem = elements_map[bound_id]
                if bound_elem.get('type') == 'text' and bound_elem.get('text'):
                    return bound_elem['text'].replace('\n', ' ').strip()

    return ''


def generate_plantuml(relative_data: list[dict]) -> str:
    """Generate basic PlantUML from relative format data.

    Args:
        relative_data: List of dictionaries containing relative format elements.
            Each element should have:
            - type: 'rectangle' or 'arrow'
            - id: unique identifier
            - label: display label
            For rectangles:
            - parent: parent rectangle ID (empty string if none)
            For arrows:
            - from: source rectangle ID
            - to: target rectangle ID

    Returns:
        PlantUML diagram as a string

    Example:
        >>> relative_data = [
        ...     {'id': 'rect1', 'type': 'rectangle', 'label': 'Box A', 'parent': ''},
        ...     {'id': 'rect2', 'type': 'rectangle', 'label': 'Box B', 'parent': ''},
        ...     {'id': 'arrow1', 'type': 'arrow', 'label': 'connects', 'from': 'rect1', 'to': 'rect2'},
        ... ]
        >>> print(generate_plantuml(relative_data))
        @startuml
        <BLANKLINE>
        component "Box A" as rect1
        component "Box B" as rect2
        <BLANKLINE>
        rect1 --> rect2 : connects
        <BLANKLINE>
        @enduml
    """
    lines = ['@startuml', '']

    # First pass: Define all rectangles as components
    rectangles = [item for item in relative_data if item['type'] == 'rectangle']
    arrows = [item for item in relative_data if item['type'] == 'arrow']

    # Sort rectangles to process parents before children
    rectangles_sorted = sorted(rectangles, key=lambda r: len(r.get('parent', '')))

    # Track which rectangles have been processed
    processed = set()

    # Process rectangles with parents (nested components)
    # For now, we'll use simple components without explicit nesting in basic PlantUML
    for rect in rectangles_sorted:
        label = rect.get('label', 'Box')
        rect_id = rect['id']

        # Sanitize ID for PlantUML (use only first 8 chars)
        sanitized_id = _sanitize_id(rect_id)

        # For basic PlantUML, we use 'component' or 'rectangle'
        # Use 'component' for regular elements
        lines.append(f'component "{label}" as {sanitized_id}')
        processed.add(rect_id)

    # Add blank line before relationships
    if arrows:
        lines.append('')

    # Second pass: Define all arrows as relationships
    for arrow in arrows:
        from_id = _sanitize_id(arrow['from'])
        to_id = _sanitize_id(arrow['to'])
        label = arrow.get('label', '')

        # Generate relationship with optional label
        if label:
            lines.append(f'{from_id} --> {to_id} : {label}')
        else:
            lines.append(f'{from_id} --> {to_id}')

    # Close PlantUML diagram
    lines.append('')
    lines.append('@enduml')

    return '\n'.join(lines)


def _sanitize_id(element_id: str) -> str:
    """Sanitize element ID for PlantUML.

    Args:
        element_id: Raw element ID from Excalidraw

    Returns:
        Sanitized ID suitable for PlantUML (first 8 chars, prefixed with Element_)
    """
    # Take first 8 characters for consistent ID format
    short_id = element_id[:8] if len(element_id) >= 8 else element_id
    return f'Element_{short_id}'
