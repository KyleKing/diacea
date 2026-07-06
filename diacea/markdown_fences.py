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

from .generators import (
    C4PlantUMLGenerator,
    D2Generator,
    GraphVizGenerator,
    MermaidGenerator,
    PlantUMLGenerator,
)
from .ingestion import DiagramIngestionError, parse_diagram_file
from .ir.elements import Diagram

_FENCE_RE = re.compile(
    r"^(?P<indent>[ \t]*)```[ \t]*diacea[ \t]*\n(?P<body>.*?)\n(?P=indent)```[ \t]*$",
    re.MULTILINE | re.DOTALL,
)

_FENCE_LANGUAGES = {
    "c4": "plantuml",
    "d2": "d2",
    "graphviz": "dot",
    "mermaid": "mermaid",
    "plantuml": "plantuml",
}

_MERMAID_TYPES = ("c4", "flowchart", "sequence")


class DiaceaFenceError(ValueError):
    """A ```diacea fence is malformed or its source cannot be converted."""


def replace_diacea_fences(markdown: str, base_dirs: Sequence[str | Path]) -> str:
    """Replace every ```diacea fence with a generated diagram code block."""

    def _render(match: re.Match[str]) -> str:
        indent = match.group("indent")
        options = _parse_fence_body(match.group("body"))
        source = _resolve_source(options["source"], base_dirs)
        try:
            diagram = parse_diagram_file(source)
        except DiagramIngestionError as err:
            raise DiaceaFenceError(str(err)) from err
        output = _generate(diagram, options["format"], options.get("mermaid-type"))
        language = _FENCE_LANGUAGES[options["format"]]
        lines = [f"{indent}```{language}"]
        lines.extend(f"{indent}{line}".rstrip() for line in output.splitlines())
        lines.append(f"{indent}```")
        return "\n".join(lines)

    return _FENCE_RE.sub(_render, markdown)


def _parse_fence_body(body: str) -> dict[str, str]:
    options = {"format": "mermaid"}
    for raw in body.splitlines():
        line = raw.strip()
        if not line:
            continue
        key, separator, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if not separator or not value:
            raise DiaceaFenceError(f"diacea fence lines must be 'key: value', got {line!r}")
        if key not in {"format", "mermaid-type", "source"}:
            raise DiaceaFenceError(f"unknown diacea fence option {key!r}")
        options[key] = value
    if "source" not in options:
        raise DiaceaFenceError("diacea fence is missing the required 'source' option")
    if options["format"] not in _FENCE_LANGUAGES:
        raise DiaceaFenceError(
            f"unknown diacea fence format {options['format']!r}; "
            f"expected one of {sorted(_FENCE_LANGUAGES)}"
        )
    if (mermaid_type := options.get("mermaid-type")) is not None and mermaid_type not in _MERMAID_TYPES:
        raise DiaceaFenceError(
            f"unknown mermaid-type {mermaid_type!r}; expected one of {sorted(_MERMAID_TYPES)}"
        )
    return options


def _resolve_source(source: str, base_dirs: Sequence[str | Path]) -> Path:
    candidates = [Path(base_dir) / source for base_dir in base_dirs]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    searched = ", ".join(str(c) for c in candidates)
    raise DiaceaFenceError(f"diacea fence source {source!r} not found (searched: {searched})")


def _generate(diagram: Diagram, output_format: str, mermaid_type: str | None) -> str:
    match output_format:
        case "c4":
            return C4PlantUMLGenerator().generate(diagram)
        case "d2":
            return D2Generator().generate(diagram)
        case "graphviz":
            return GraphVizGenerator().generate(diagram)
        case "mermaid":
            return MermaidGenerator(diagram_type=mermaid_type).generate(diagram)
        case "plantuml":
            return PlantUMLGenerator().generate(diagram)
    raise DiaceaFenceError(f"unknown diacea fence format {output_format!r}")
