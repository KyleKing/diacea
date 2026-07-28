"""Shared text helpers for generators."""

from __future__ import annotations

from ..ir import Group


def sanitize_alnum_id(id_str: str) -> str:
    """Sanitize an ID to alphanumeric and underscore characters."""
    return ''.join(c if c.isalnum() or c == '_' else '_' for c in id_str)


def top_level_groups(groups: list[Group]) -> list[Group]:
    """Groups not referenced as a child of any other group."""
    child_ids = {child_id for group in groups for child_id in group.children}
    return [group for group in groups if group.id not in child_ids]
