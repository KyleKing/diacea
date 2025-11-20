"""Generate PlantUML from relative format."""

from __future__ import annotations


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

        # Sanitize ID for PlantUML (use only first 8 chars to match golang style)
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
    # Take first 8 characters to match golang implementation
    short_id = element_id[:8] if len(element_id) >= 8 else element_id
    return f'Element_{short_id}'
