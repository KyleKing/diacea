r"""Format registry and the conversion pipeline built on it.

This is the one place that knows which formats exist. Each input format
declares how to recognize, load, and parse itself; each output format
declares its file suffix, options, and generator. The CLI, workspace
ingestion, the MkDocs plugin, and library callers all go through
`parse_diagram`, `render_diagram`, or `convert`, so adding a format means
adding one registry entry.

Example:
    >>> from diacea import convert
    >>> result = convert('flowchart LR\n    A[Web] --> B[(DB)]', to='d2')
    >>> print(result.output)
    direction: right
    <BLANKLINE>
    A: Web
    B: DB {
      shape: cylinder
    }
    <BLANKLINE>
    A -> B
"""

from __future__ import annotations

import json
import warnings as _warnings
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .generators import (
    C4PlantUMLGenerator,
    D2Config,
    D2Generator,
    ExcalidrawConfig,
    ExcalidrawGenerator,
    GraphVizConfig,
    GraphVizGenerator,
    MermaidGenerator,
    PlantUMLGenerator,
)
from .ir.base import Generator, Parser
from .ir.elements import Diagram, Shape
from .ir.semantic import SemanticType, split_stereotype
from .parsers import (
    D2Parser,
    ExcalidrawParser,
    GraphVizParser,
    MermaidParser,
    PlantUMLParser,
    SVGParser,
    TLDrawParser,
    extract_excalidraw_json,
    is_d2,
    is_dot,
    is_mermaid,
    is_obsidian_excalidraw,
    is_plantuml,
    is_tldraw_v2,
)


class FormatError(ValueError):
    """The input could not be recognized or parsed, or the output format is unknown."""


@dataclass(frozen=True)
class InputFormat:
    """A diagram format diacea can read."""

    name: str
    description: str
    detection: str
    suffixes: tuple[str, ...]
    parser: Callable[[], Parser]
    sniff_text: Callable[[str], bool] | None = None
    sniff_json: Callable[[dict[str, Any]], bool] | None = None
    load: Callable[[str], Any] = str


@dataclass(frozen=True)
class FormatOption:
    """A generator option exposed as a command-line flag."""

    flag: str
    help: str
    choices: tuple[str, ...] | None = None
    is_flag: bool = False
    default: Any = None

    @property
    def dest(self) -> str:
        """Keyword name for `render_diagram` and argparse (`--d2-sketch` -> `d2_sketch`)."""
        return self.flag.lstrip('-').replace('-', '_')

    @property
    def usage(self) -> str:
        """Flag with its choices, as shown by `diacea formats`."""
        return f'{self.flag} {{{",".join(self.choices)}}}' if self.choices else self.flag


@dataclass(frozen=True)
class OutputFormat:
    """A diagram format diacea can write."""

    name: str
    description: str
    suffix: str
    build: Callable[[Mapping[str, Any]], Generator]
    options: tuple[FormatOption, ...] = ()
    extra_suffixes: tuple[str, ...] = ()


@dataclass
class ParseResult:
    """A parsed diagram with the format it was read as and any conversion-loss warnings."""

    diagram: Diagram
    input_format: str
    warnings: list[str] = field(default_factory=list)


@dataclass
class ConversionResult:
    """Generated output plus everything known about how it was produced."""

    output: str
    input_format: str | None
    output_format: str
    diagram: Diagram
    diagram_type: str | None = None
    warnings: list[str] = field(default_factory=list)


def _is_svg(content: str) -> bool:
    return content.lstrip().startswith(('<?xml', '<svg'))


def _is_legacy_tldraw(data: dict[str, Any]) -> bool:
    document = data.get('document')
    return isinstance(document, dict) and 'pages' in document


def _is_excalidraw(data: dict[str, Any]) -> bool:
    return 'elements' in data or data.get('type') == 'excalidraw/clipboard'


# Order matters: earlier formats win when more than one signature matches
INPUT_FORMATS: dict[str, InputFormat] = {
    fmt.name: fmt
    for fmt in (
        InputFormat(
            name='svg',
            description='SVG with basic shapes, text, and groups (curves are sampled for accurate bounding boxes)',
            detection="content starting with '<?xml' or '<svg'",
            suffixes=('.svg',),
            parser=SVGParser,
            sniff_text=_is_svg,
        ),
        InputFormat(
            name='obsidian',
            description=(
                'Obsidian Excalidraw plugin markdown (.excalidraw.md); '
                'compressed-json Drawing blocks require the diacea[obsidian] extra'
            ),
            detection="markdown with 'excalidraw-plugin' frontmatter or a '# Drawing' code block",
            suffixes=('.excalidraw.md',),
            parser=ExcalidrawParser,
            sniff_text=is_obsidian_excalidraw,
            load=extract_excalidraw_json,
        ),
        InputFormat(
            name='plantuml',
            description='PlantUML deployment/component text, including the C4-PlantUML macro dialect',
            detection="text containing '@startuml'",
            suffixes=('.puml', '.plantuml', '.pu', '.iuml'),
            parser=PlantUMLParser,
            sniff_text=is_plantuml,
        ),
        InputFormat(
            name='graphviz',
            description='GraphViz DOT (graph/digraph with clusters, attributes, and edge chains)',
            detection="text opening a 'graph {' or 'digraph {' block",
            suffixes=('.dot', '.gv'),
            parser=GraphVizParser,
            sniff_text=is_dot,
        ),
        InputFormat(
            name='mermaid',
            description='Mermaid text (flowchart/graph, sequence, and C4 diagrams)',
            detection="text starting with 'flowchart', 'graph', 'sequenceDiagram', or a 'C4...' header",
            suffixes=('.mmd', '.mermaid'),
            parser=MermaidParser,
            sniff_text=is_mermaid,
        ),
        InputFormat(
            name='tldraw',
            description='TLDraw JSON (legacy v1 documents and v2 .tldr files)',
            detection="JSON with 'tldrawFileFormatVersion'/'records' (v2) or 'document.pages' (legacy)",
            suffixes=('.tldr',),
            parser=TLDrawParser,
            sniff_json=lambda data: is_tldraw_v2(data) or _is_legacy_tldraw(data),
            load=json.loads,
        ),
        InputFormat(
            name='excalidraw',
            description='Excalidraw JSON scene',
            detection="JSON with an 'elements' key or type 'excalidraw/clipboard'",
            suffixes=('.excalidraw',),
            parser=ExcalidrawParser,
            sniff_json=_is_excalidraw,
            load=json.loads,
        ),
        InputFormat(
            name='d2',
            description='D2 text (shapes, nested containers, connections, shape and style keywords)',
            detection="the '.d2' file extension, or text where every line is a D2 statement",
            suffixes=('.d2',),
            parser=D2Parser,
        ),
    )
}

OUTPUT_FORMATS: dict[str, OutputFormat] = {
    fmt.name: fmt
    for fmt in (
        OutputFormat(
            name='c4',
            description='C4-PlantUML',
            suffix='.puml',
            build=lambda _options: C4PlantUMLGenerator(),
        ),
        OutputFormat(
            name='d2',
            description='D2',
            suffix='.d2',
            build=lambda options: D2Generator(
                config=D2Config(direction=options.get('d2_direction'), sketch=bool(options.get('d2_sketch')))
            ),
            options=(
                FormatOption(
                    '--d2-direction',
                    'D2 layout direction (default: from the source, else auto-detect)',
                    choices=('up', 'down', 'left', 'right'),
                ),
                FormatOption('--d2-sketch', 'Use D2 sketch mode (hand-drawn look)', is_flag=True),
            ),
        ),
        OutputFormat(
            name='excalidraw',
            description='Excalidraw scene (editable; open at excalidraw.com or in the Obsidian/VS Code plugins)',
            suffix='.excalidraw',
            build=lambda options: ExcalidrawGenerator(
                config=ExcalidrawConfig(roughness=int(options.get('excalidraw_roughness') or 1))
            ),
            options=(
                FormatOption(
                    '--excalidraw-roughness',
                    'Excalidraw sloppiness: 0=architect (clean), 1=artist (default), 2=cartoonist',
                    choices=('0', '1', '2'),
                ),
            ),
        ),
        OutputFormat(
            name='graphviz',
            description='GraphViz DOT',
            suffix='.dot',
            build=lambda options: GraphVizGenerator(
                config=GraphVizConfig(
                    direction=options.get('graphviz_direction'),
                    graph_type=options.get('graphviz_type') or 'digraph',
                )
            ),
            options=(
                FormatOption(
                    '--graphviz-direction',
                    'GraphViz layout direction (default: from the source, else auto-detect)',
                    choices=('LR', 'TB', 'RL', 'BT'),
                ),
                FormatOption(
                    '--graphviz-type',
                    'GraphViz graph type: digraph=directed, graph=undirected (default: digraph)',
                    choices=('digraph', 'graph'),
                    default='digraph',
                ),
            ),
            extra_suffixes=('.gv',),
        ),
        OutputFormat(
            name='mermaid',
            description='Mermaid (flowchart, c4, or sequence; auto-detected by default)',
            suffix='.mmd',
            build=lambda options: MermaidGenerator(diagram_type=options.get('mermaid_type')),
            options=(
                FormatOption(
                    '--mermaid-type',
                    'Mermaid diagram type (default: auto-detect)',
                    choices=('flowchart', 'c4', 'sequence'),
                ),
            ),
            extra_suffixes=('.mermaid',),
        ),
        OutputFormat(
            name='plantuml',
            description='PlantUML',
            suffix='.puml',
            build=lambda _options: PlantUMLGenerator(),
            extra_suffixes=('.plantuml', '.pu'),
        ),
    )
}


def input_format_for_path(path: str | Path) -> str | None:
    """Input format implied by a file name, if its extension is recognized."""
    name = Path(path).name.lower()
    matches = [fmt for fmt in INPUT_FORMATS.values() if name.endswith(fmt.suffixes)]
    return max(matches, key=lambda fmt: max(len(s) for s in fmt.suffixes)).name if matches else None


def output_format_for_path(path: str | Path) -> str | None:
    """Output format implied by a file name, if its extension is recognized.

    `.puml` maps to plain PlantUML; C4-PlantUML must be requested by name.
    """
    name = Path(path).name.lower()
    for fmt in OUTPUT_FORMATS.values():
        if fmt.name != 'c4' and name.endswith((fmt.suffix, *fmt.extra_suffixes)):
            return fmt.name
    return None


def detect_input_format(data: str | dict[str, Any], filename: str | Path | None = None) -> str:
    """Identify the input format of text content (or already-parsed JSON).

    Content signatures are tried first, then the file extension, then a
    last-resort sniff for D2 (which has no header to recognize).

    Raises:
        ValueError: If no format matches.
    """
    if isinstance(data, dict):
        return _detect_json(data)

    for fmt in INPUT_FORMATS.values():
        if fmt.sniff_text is not None and fmt.sniff_text(data):
            return fmt.name
    try:
        parsed = json.loads(data)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        return _detect_json(parsed)
    if isinstance(parsed, list):
        return 'excalidraw'

    if filename is not None and (by_suffix := input_format_for_path(filename)) is not None:
        return by_suffix
    if is_d2(data):
        return 'd2'
    known = ', '.join(sorted(INPUT_FORMATS))
    msg = f'Could not detect input format (supported: {known}); pass the format explicitly if the file is valid'
    raise ValueError(msg)


def _detect_json(data: dict[str, Any]) -> str:
    for fmt in INPUT_FORMATS.values():
        if fmt.sniff_json is not None and fmt.sniff_json(data):
            return fmt.name
    raise ValueError('Unrecognized input format: JSON is neither an Excalidraw scene nor a TLDraw document')


def parse_diagram(
    content: str,
    input_format: str = 'auto',
    *,
    filename: str | Path | None = None,
    hints: Mapping[str, str] | None = None,
) -> ParseResult:
    """Parse diagram text to the IR.

    Args:
        content: Text of the diagram file
        input_format: A name from `INPUT_FORMATS`, or 'auto' to detect it
        filename: Source file name, used only as a detection fallback
        hints: Semantic type overrides keyed by element id or label
            (e.g. ``{'Orders': 'database'}``)

    Raises:
        FormatError: If the format is unknown, cannot be detected, or the
            content does not parse.
    """
    if input_format == 'auto':
        try:
            input_format = detect_input_format(content, filename)
        except ValueError as err:
            raise FormatError(str(err)) from err
    if (fmt := INPUT_FORMATS.get(input_format)) is None:
        msg = f'Unsupported input format: {input_format}'
        raise FormatError(msg)

    parser = fmt.parser()
    try:
        diagram = parser.parse(fmt.load(content))
    except ValueError as err:
        msg = f'Failed to parse {input_format} input: {err}'
        raise FormatError(msg) from err

    warnings = list(getattr(parser, 'warnings', []))
    warnings.extend(apply_hints(diagram, hints or {}))
    return ParseResult(diagram=diagram, input_format=input_format, warnings=warnings)


def parse_file(
    path: str | Path,
    input_format: str = 'auto',
    *,
    hints: Mapping[str, str] | None = None,
) -> ParseResult:
    """Read and parse a diagram file. See `parse_diagram`.

    Raises:
        FormatError: If the file is missing or does not parse.
    """
    file_path = Path(path)
    if not file_path.exists():
        msg = f'Input file not found: {path}'
        raise FormatError(msg)
    return parse_diagram(file_path.read_text(encoding='utf-8'), input_format, filename=file_path, hints=hints)


def apply_hints(diagram: Diagram, hints: Mapping[str, str]) -> list[str]:
    """Apply explicit semantic types to shapes; returns warnings for hints that did not apply.

    Two sources are honored: a ``<<type>>`` stereotype written into a
    shape's label (removed from the label once read), and `hints`, which
    maps an element id or label (case-insensitive) to a semantic type.
    """
    for element in diagram.elements:
        label = getattr(element, 'label', '')
        if '<<' in label or '«' in label:
            cleaned, semantic = split_stereotype(label)
            if semantic is not None:
                element.label = cleaned  # type: ignore[attr-defined]
                _declare_semantic(element, semantic)

    problems: list[str] = []
    for key, type_name in hints.items():
        try:
            semantic = SemanticType(type_name.strip().lower())
        except ValueError:
            valid = ', '.join(sorted(member.value for member in SemanticType))
            problems.append(f"hint '{key}={type_name}': unknown semantic type (valid: {valid})")
            continue
        wanted = key.strip().lower()
        matches = [
            shape
            for shape in diagram.get_shapes()
            if wanted in {shape.id.lower(), ' '.join(shape.label.split()).lower()}
        ]
        if not matches:
            problems.append(f"hint '{key}={type_name}': no element has that id or label")
        for shape in matches:
            _declare_semantic(shape, semantic)
    return problems


def _declare_semantic(element: Any, semantic: SemanticType) -> None:
    element.semantic_type = semantic
    element.semantic_confidence = 1.0
    if isinstance(element, Shape):
        element.metadata['semantic_type'] = semantic.value


def render_diagram(diagram: Diagram, output_format: str, **options: Any) -> ConversionResult:
    """Generate output text from an IR diagram.

    Args:
        diagram: Diagram to render
        output_format: A name from `OUTPUT_FORMATS`
        **options: Generator options named after their flags
            (e.g. ``mermaid_type='flowchart'``, ``d2_sketch=True``)

    Raises:
        FormatError: If the output format is unknown.
    """
    if (fmt := OUTPUT_FORMATS.get(output_format)) is None:
        msg = f'Unknown format: {output_format}'
        raise FormatError(msg)
    generator = fmt.build(options)
    with _warnings.catch_warnings(record=True) as caught:
        _warnings.simplefilter('always')
        output = generator.generate(diagram)
    return ConversionResult(
        output=output,
        input_format=None,
        output_format=output_format,
        diagram=diagram,
        diagram_type=getattr(generator, 'detected_type', None),
        warnings=list(dict.fromkeys(str(warning.message) for warning in caught)),
    )


def convert(
    content: str,
    to: str,
    *,
    input_format: str = 'auto',
    filename: str | Path | None = None,
    hints: Mapping[str, str] | None = None,
    **options: Any,
) -> ConversionResult:
    """Convert diagram text to another format in one call.

    Args:
        content: Text of the source diagram
        to: Output format name from `OUTPUT_FORMATS`
        input_format: Input format name, or 'auto' to detect it
        filename: Source file name, used only as a detection fallback
        hints: Semantic type overrides keyed by element id or label
        **options: Generator options (see `render_diagram`)

    Raises:
        FormatError: If the input cannot be parsed or `to` is unknown.
    """
    if to not in OUTPUT_FORMATS:
        msg = f'Unknown format: {to}'
        raise FormatError(msg)
    parsed = parse_diagram(content, input_format, filename=filename, hints=hints)
    result = render_diagram(parsed.diagram, to, **options)
    result.input_format = parsed.input_format
    result.warnings = [*parsed.warnings, *result.warnings]
    return result


__all__ = [
    'INPUT_FORMATS',
    'OUTPUT_FORMATS',
    'ConversionResult',
    'FormatError',
    'FormatOption',
    'InputFormat',
    'OutputFormat',
    'ParseResult',
    'apply_hints',
    'convert',
    'detect_input_format',
    'input_format_for_path',
    'output_format_for_path',
    'parse_diagram',
    'parse_file',
    'render_diagram',
]
