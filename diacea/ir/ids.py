"""Readable element ids for diagrams whose source assigns random ones.

Drawing tools identify elements with opaque ids (``vapRpvna4Qio1_zgMc5D3``).
Carried into generated text they make it unreadable and uneditable, so they
are replaced with ids derived from each element's label
(``api_gateway --> orders_db``). The original id is kept in
``metadata['source_id']``.
"""

from __future__ import annotations

import re

from .elements import GROUP_ID_PREFIX, Diagram, Group

_GENERATED_ID_MIN_LENGTH = 16
_MAX_SLUG_LENGTH = 40


def looks_generated(element_id: str) -> bool:
    """Whether an id reads as tool-generated rather than written by a person."""
    return ':' in element_id or (len(element_id) >= _GENERATED_ID_MIN_LENGTH and ' ' not in element_id)


def _slug(label: str) -> str:
    slug = re.sub(r'[^0-9a-zA-Z]+', '_', label).strip('_').lower()
    return slug[:_MAX_SLUG_LENGTH].rstrip('_')


def assign_readable_ids(diagram: Diagram) -> dict[str, str]:
    """Rename tool-generated shape and group ids in place; returns {old id: new id}.

    A labelled element is named after its label, an unlabeled one
    ``node_N`` or ``group_N``. Ids a person wrote are left alone.
    """
    groups = diagram.get_groups()
    shapes = diagram.get_shapes()
    taken = {shape.id for shape in shapes if not looks_generated(shape.id)}
    taken |= {group.source_shape_id for group in groups if not looks_generated(group.source_shape_id)}

    def claim(base: str) -> str:
        candidate, counter = base, 1
        while candidate in taken:
            counter += 1
            candidate = f'{base}_{counter}'
        taken.add(candidate)
        return candidate

    renames: dict[str, str] = {}
    unlabeled = 0
    for shape in shapes:
        if not looks_generated(shape.id):
            continue
        slug = _slug(shape.label)
        if not slug:
            unlabeled += 1
            slug = f'node_{unlabeled}'
        renames[shape.id] = claim(slug)

    unlabeled = 0
    for group in groups:
        source_id = group.source_shape_id
        if source_id in renames:
            renames[group.id] = GROUP_ID_PREFIX + renames[source_id]
        elif looks_generated(source_id):
            slug = _slug(group.label)
            if not slug:
                unlabeled += 1
                slug = f'group_{unlabeled}'
            renames[group.id] = GROUP_ID_PREFIX + claim(slug)

    for element in diagram.elements:
        if element.id in renames:
            element.metadata.setdefault('source_id', element.id)
            element.id = renames[element.id]
        if isinstance(element, Group):
            element.children = [renames.get(child_id, child_id) for child_id in element.children]
    for connection in diagram.get_connections():
        connection.from_id = renames.get(connection.from_id, connection.from_id)
        connection.to_id = renames.get(connection.to_id, connection.to_id)
    return renames


__all__ = ['assign_readable_ids', 'looks_generated']
