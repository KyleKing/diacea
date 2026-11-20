"""Replace ```diacea fenced blocks in markdown with generated diagram code blocks.

A fence names a diagram source file and an output format:

    ```diacea
    source: diagrams/architecture.excalidraw
    format: mermaid
    ```

and is replaced by a code block in the target language (```mermaid, ```d2, ...)
containing the converted diagram, so renderers like mkdocs-material's Mermaid
support pick it up. `source` is resolved against the provided base directories
(first match wins). `format` defaults to mermaid; `mermaid-type` optionally
forces the Mermaid diagram type.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path

from .formats import render_diagram
from .ingestion import DiagramIngestionError, parse_diagram_file

_FENCE_RE = re.compile(
    r'^(?P<indent>[ \t]*)```[ \t]*diacea[ \t]*\n(?P<body>.*?)\n(?P=indent)```[ \t]*$',
    re.MULTILINE | re.DOTALL,
)

_FENCE_LANGUAGES = {
    'c4': 'plantuml',
    'd2': 'd2',
    'graphviz': 'dot',
    'mermaid': 'mermaid',
    'plantuml': 'plantuml',
}

_MERMAID_TYPES = ('c4', 'flowchart', 'sequence')


class DiaceaFenceError(ValueError):
    """A ```diacea fence is malformed or its source cannot be converted."""


def replace_diacea_fences(markdown: str, base_dirs: Sequence[str | Path]) -> str:
    """Replace every ```diacea fence with a generated diagram code block."""

    def _render(match: re.Match[str]) -> str:
        indent = match.group('indent')
        options = _parse_fence_body(match.group('body'))
        source = _resolve_source(options['source'], base_dirs)
        try:
            diagram = parse_diagram_file(source)
        except DiagramIngestionError as err:
            raise DiaceaFenceError(str(err)) from err
        output = render_diagram(diagram, options['format'], mermaid_type=options.get('mermaid-type')).output
        language = _FENCE_LANGUAGES[options['format']]
        lines = [f'{indent}```{language}']
        lines.extend(f'{indent}{line}'.rstrip() for line in output.splitlines())
        lines.append(f'{indent}```')
        return '\n'.join(lines)

    return _FENCE_RE.sub(_render, markdown)


def _parse_fence_body(body: str) -> dict[str, str]:
    options = {'format': 'mermaid'}
    for raw in body.splitlines():
        line = raw.strip()
        if not line:
            continue
        key, separator, value = line.partition(':')
        key, value = key.strip(), value.strip()
        if not separator or not value:
            msg = f"diacea fence lines must be 'key: value', got {line!r}"
            raise DiaceaFenceError(msg)
        if key not in {'format', 'mermaid-type', 'source'}:
            msg = f'unknown diacea fence option {key!r}'
            raise DiaceaFenceError(msg)
        options[key] = value
    if 'source' not in options:
        raise DiaceaFenceError("diacea fence is missing the required 'source' option")
    if options['format'] not in _FENCE_LANGUAGES:
        msg = f'unknown diacea fence format {options["format"]!r}; expected one of {sorted(_FENCE_LANGUAGES)}'
        raise DiaceaFenceError(msg)
    if (mermaid_type := options.get('mermaid-type')) is not None and mermaid_type not in _MERMAID_TYPES:
        msg = f'unknown mermaid-type {mermaid_type!r}; expected one of {sorted(_MERMAID_TYPES)}'
        raise DiaceaFenceError(msg)
    return options


def _resolve_source(source: str, base_dirs: Sequence[str | Path]) -> Path:
    candidates = [Path(base_dir) / source for base_dir in base_dirs]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    searched = ', '.join(str(c) for c in candidates)
    msg = f'diacea fence source {source!r} not found (searched: {searched})'
    raise DiaceaFenceError(msg)
