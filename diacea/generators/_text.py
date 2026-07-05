"""Shared text helpers for generators."""

from __future__ import annotations


def sanitize_alnum_id(id_str: str) -> str:
    """Sanitize an ID to alphanumeric and underscore characters."""
    return ''.join(c if c.isalnum() or c == '_' else '_' for c in id_str)
