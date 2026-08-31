"""Obsidian Excalidraw plugin (.excalidraw.md) support.

Format reference: https://github.com/zsviczian/obsidian-excalidraw-plugin
The drawing JSON lives in a ``# Drawing`` section inside a ```json or
```compressed-json fenced code block. Compressed blocks are LZ-String
``compressToBase64`` output split into 256-character chunks separated by
blank lines.
"""

from __future__ import annotations

import json
import re
from typing import Any

lzstring: Any = None
_HAS_LZSTRING = False

try:
    import lzstring as _lzstring  # type: ignore[import-untyped]  # lzstring ships no type stubs
except ImportError:
    pass
else:
    lzstring = _lzstring
    _HAS_LZSTRING = True

_DRAWING_JSON_RE = re.compile(r'\n##? Drawing\n[^`]*```json\n([\s\S]*?)```')
_DRAWING_COMPRESSED_RE = re.compile(r'\n##? Drawing\n[^`]*```compressed-json\n([\s\S]*?)```')
_FRONTMATTER_PLUGIN_RE = re.compile(r'^excalidraw-plugin:', re.MULTILINE)


def is_obsidian_excalidraw(content: str) -> bool:
    """Check whether text looks like an Obsidian Excalidraw markdown note."""
    return bool(
        _FRONTMATTER_PLUGIN_RE.search(content)
        or _DRAWING_JSON_RE.search(content)
        or _DRAWING_COMPRESSED_RE.search(content)
    )


def extract_excalidraw_json(content: str) -> dict[str, Any]:
    """Extract the Excalidraw scene dict from an Obsidian .excalidraw.md note.

    Raises:
        ValueError: If no Drawing section is found, decompression fails, or
            the note uses compressed-json and lzstring is not installed.
    """
    if match := _DRAWING_JSON_RE.search(content):
        return json.loads(match.group(1))

    if match := _DRAWING_COMPRESSED_RE.search(content):
        if lzstring is None or not _HAS_LZSTRING:
            raise ValueError(
                'This Obsidian Excalidraw file uses a compressed-json Drawing block. '
                "Install the optional dependency to decompress it: pip install 'diacea[obsidian]'"
            )
        compressed = re.sub(r'\s+', '', match.group(1))
        decompressed = lzstring.LZString().decompressFromBase64(compressed)
        if not decompressed:
            raise ValueError('Failed to decompress the compressed-json Drawing block')
        return json.loads(decompressed)

    raise ValueError("No '# Drawing' section with a json or compressed-json code block was found")
