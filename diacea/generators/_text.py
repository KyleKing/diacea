"""Shared text helpers for generators."""

from __future__ import annotations

from ..ir import Connection, Diagram, Group, SemanticType, Shape

# Confidence at or above which a semantic type was declared by the source rather than guessed
DECLARED_CONFIDENCE = 0.9

_SHAPE_ALIASES = {
    'actor': 'person',
    'database': 'cylinder',
    'oval': 'ellipse',
    'box': 'rectangle',
    'square': 'rectangle',
    'rounded': 'rounded_rectangle',
}


def sanitize_alnum_id(id_str: str) -> str:
    """Sanitize an ID to alphanumeric and underscore characters."""
    return ''.join(c if c.isalnum() or c == '_' else '_' for c in id_str)


def top_level_groups(groups: list[Group]) -> list[Group]:
    """Groups not referenced as a child of any other group."""
    child_ids = {child_id for group in groups for child_id in group.children}
    return [group for group in groups if group.id not in child_ids]


def canonical_shape(shape_type: str) -> str:
    """Normalize parser spellings of a shape type (database -> cylinder, actor -> person)."""
    return _SHAPE_ALIASES.get(shape_type, shape_type)


def visual_semantic(shape: Shape, diagram: Diagram) -> SemanticType | str | None:
    """Semantic type a generator may use to choose the node's visual.

    For drawings, a semantic type guessed from the label is what turns a
    plain box into a cylinder or an actor. For sources whose author picked
    every shape explicitly, a guess must not override that choice, so only
    declared semantic types are returned.
    """
    if diagram.has_explicit_shapes and shape.semantic_confidence < DECLARED_CONFIDENCE:
        return None
    return shape.semantic_type


class Containers:
    """Resolve connection endpoints that are containers rather than plain nodes.

    A connection may start or end at a group, named either by the group id
    or by the id of the container shape the group was derived from. Text
    formats declare a container under its group id only, so emitting the raw
    endpoint id would conjure an unlabeled phantom node.
    """

    def __init__(self, diagram: Diagram) -> None:
        groups = diagram.get_groups()
        self._groups: dict[str, Group] = {group.id: group for group in groups}
        self._by_endpoint: dict[str, Group] = dict(self._groups)
        for group in groups:
            self._by_endpoint.setdefault(group.source_shape_id, group)
        self._shape_ids = {shape.id for shape in diagram.get_shapes()} - {g.source_shape_id for g in groups}

    def group_for(self, endpoint_id: str) -> Group | None:
        """The group a connection endpoint refers to, or None for a plain node."""
        return self._by_endpoint.get(endpoint_id)

    def leaves(self, group: Group) -> list[str]:
        """Ids of the plain nodes nested anywhere inside the group, in declaration order."""
        found: list[str] = []
        seen = {group.id}
        pending = list(reversed(group.children))
        while pending:
            child_id = pending.pop()
            if child_id in seen:
                continue
            seen.add(child_id)
            if (child_group := self._groups.get(child_id)) is not None:
                pending.extend(reversed(child_group.children))
            elif child_id in self._shape_ids:
                found.append(child_id)
        return found

    def contains(self, group: Group, element_id: str) -> bool:
        """Whether the element (node or group) is nested anywhere inside the group."""
        target_group = self._by_endpoint.get(element_id)
        target_ids = {element_id, target_group.id} if target_group else {element_id}
        seen = {group.id}
        pending = list(group.children)
        while pending:
            child_id = pending.pop()
            if child_id in target_ids:
                return True
            if child_id not in seen and (child_group := self._groups.get(child_id)) is not None:
                seen.add(child_id)
                pending.extend(child_group.children)
        return False

    def links_container_to_own_content(self, conn: Connection) -> bool:
        """Whether the connection joins a container to itself or to something inside it."""
        source = self.group_for(conn.from_id)
        target = self.group_for(conn.to_id)
        if source is not None and (source is target or self.contains(source, conn.to_id)):
            return True
        return target is not None and self.contains(target, conn.from_id)
