"""MkDocs plugin rendering ```diacea fences to diagram code blocks at build time.

Register it in mkdocs.yml (requires the ``diacea[mkdocs]`` extra):

    plugins:
      - diacea

Fence sources are resolved relative to the page's directory first, then the
docs directory. Conversion errors fail the build.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mkdocs.plugins import BasePlugin

from .markdown_fences import replace_diacea_fences


class DiaceaPlugin(BasePlugin):  # type: ignore[type-arg]
    """Replace ```diacea fences with generated diagram code blocks."""

    def on_page_markdown(self, markdown: str, /, *, page: Any, config: Any, files: Any) -> str:
        base_dirs = [Path(page.file.abs_src_path).parent, Path(config["docs_dir"])]
        return replace_diacea_fences(markdown, base_dirs)
