"""Command-line interface for diacea diagram converter."""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path
from typing import Any, Optional

from .generators import (
    C4PlantUMLGenerator,
    D2Config,
    D2Generator,
    GraphVizConfig,
    GraphVizGenerator,
    MermaidGenerator,
    PlantUMLGenerator,
)
from .ir.elements import Diagram
from .parsers import (
    ExcalidrawParser,
    MermaidParser,
    PlantUMLParser,
    SVGParser,
    TLDrawParser,
    extract_excalidraw_json,
    is_mermaid,
    is_obsidian_excalidraw,
    is_plantuml,
    is_tldraw_v2,
)

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_EMPTY_DIAGRAM = 2

_INPUT_FORMAT_CHOICES = ["auto", "excalidraw", "mermaid", "obsidian", "plantuml", "tldraw", "svg"]

_INPUT_FORMATS = [
    {
        "name": "excalidraw",
        "description": "Excalidraw JSON scene",
        "detection": "JSON with an 'elements' key or type 'excalidraw/clipboard'",
    },
    {
        "name": "mermaid",
        "description": "Mermaid text (flowchart/graph and sequence diagrams)",
        "detection": "text starting with 'flowchart' or 'graph'",
    },
    {
        "name": "obsidian",
        "description": "Obsidian Excalidraw plugin markdown (.excalidraw.md); compressed-json Drawing blocks require the diacea[obsidian] extra",
        "detection": "markdown with 'excalidraw-plugin' frontmatter or a '# Drawing' code block",
    },
    {
        "name": "plantuml",
        "description": "PlantUML deployment/component text, including the C4-PlantUML macro dialect",
        "detection": "text containing '@startuml'",
    },
    {
        "name": "svg",
        "description": "SVG with basic shapes, text, and groups (curves are sampled for accurate bounding boxes)",
        "detection": "content starting with '<?xml' or '<svg'",
    },
    {
        "name": "tldraw",
        "description": "TLDraw JSON (legacy v1 documents and v2 .tldr files)",
        "detection": "JSON with 'tldrawFileFormatVersion'/'records' (v2) or 'document.pages' (legacy)",
    },
]

_OUTPUT_FORMATS = [
    {"name": "c4", "description": "C4-PlantUML", "options": []},
    {
        "name": "d2",
        "description": "D2",
        "options": ["--d2-direction {up,down,left,right}", "--d2-sketch"],
    },
    {
        "name": "graphviz",
        "description": "GraphViz DOT",
        "options": ["--graphviz-direction {LR,TB,RL,BT}", "--graphviz-type {digraph,graph}"],
    },
    {
        "name": "mermaid",
        "description": "Mermaid (flowchart, c4, or sequence; auto-detected by default)",
        "options": ["--mermaid-type {flowchart,c4,sequence}"],
    },
    {"name": "plantuml", "description": "PlantUML", "options": []},
]


class _CLIError(Exception):
    """CLI failure with an associated exit code."""

    def __init__(self, message: str, exit_code: int = EXIT_ERROR):
        super().__init__(message)
        self.exit_code = exit_code


def detect_input_format(data: dict | str) -> str:
    """Detect input format from data structure.

    Args:
        data: JSON data dictionary or string content

    Returns:
        Format name ('svg', 'obsidian', 'tldraw', or 'excalidraw')

    Raises:
        ValueError: If format cannot be detected
    """
    # Check if it's string content (SVG, Obsidian Excalidraw markdown, PlantUML, or Mermaid)
    if isinstance(data, str):
        if data.strip().startswith("<?xml") or data.strip().startswith("<svg"):
            return "svg"
        if is_obsidian_excalidraw(data):
            return "obsidian"
        if is_plantuml(data):
            return "plantuml"
        if is_mermaid(data):
            return "mermaid"
        raise ValueError(
            "Unknown string format - expected SVG XML, Obsidian Excalidraw markdown, "
            "PlantUML, or Mermaid"
        )

    # Modern TLDraw v2 .tldr files have "tldrawFileFormatVersion" + flat "records"
    if is_tldraw_v2(data):
        return "tldraw"

    # Legacy TLDraw has "document" -> "pages" structure
    if "document" in data and "pages" in data.get("document", {}):
        return "tldraw"

    # Excalidraw has "elements" or "type": "excalidraw/clipboard"
    if "elements" in data or data.get("type") == "excalidraw/clipboard":
        return "excalidraw"

    raise ValueError("Unknown input format - expected SVG, TLDraw, or Excalidraw")


def main(argv: Optional[list[str]] = None) -> int:
    """Main CLI entry point.

    Dispatches to the `formats`, `inspect`, or `convert` subcommands. For
    backward compatibility, bare conversion invocations without a subcommand
    (`diacea -i file -f mermaid`) are treated as `convert`.

    Args:
        argv: Command-line arguments (None = sys.argv)

    Returns:
        Exit code (0 = success, 1 = error, 2 = parsed 0 elements)
    """
    args_list = list(sys.argv[1:] if argv is None else argv)
    match args_list:
        case ["convert", *rest]:
            return _run_convert(rest)
        case ["formats", *rest]:
            return _run_formats(rest)
        case ["inspect", *rest]:
            return _run_inspect(rest)
        case ["sync", *rest]:
            return _run_sync(rest)
        case _:
            return _run_convert(args_list)


def _read_content(input_arg: str) -> str:
    if input_arg == "-":
        return sys.stdin.read()
    input_path = Path(input_arg)
    if not input_path.exists():
        raise _CLIError(f"Input file not found: {input_arg}")
    return input_path.read_text()


def _resolve_input_format(content: str, requested: str) -> tuple[str, Any]:
    """Resolve the input format name and parser-ready data for content."""
    if requested in ("svg", "mermaid", "plantuml"):
        return (requested, content)
    if requested == "obsidian":
        return ("obsidian", extract_excalidraw_json(content))
    if requested != "auto":
        return (requested, json.loads(content))

    stripped = content.strip()
    if stripped.startswith(("<?xml", "<svg")):
        return ("svg", content)
    if is_obsidian_excalidraw(content):
        return ("obsidian", extract_excalidraw_json(content))
    if is_plantuml(content):
        return ("plantuml", content)
    if is_mermaid(content):
        return ("mermaid", content)
    try:
        data = json.loads(content)
    except json.JSONDecodeError as err:
        raise _CLIError(
            "Could not detect input format: not SVG, Obsidian Excalidraw markdown, "
            "PlantUML, Mermaid, or valid JSON"
        ) from err
    try:
        return (detect_input_format(data), data)
    except ValueError as err:
        raise _CLIError(f"Unrecognized input format: {err}") from err


def _parse_to_diagram(input_format: str, input_data: Any) -> tuple[Diagram, list[str]]:
    """Parse input data to IR and collect parser conversion-loss warnings."""
    match input_format:
        case "svg":
            input_parser = SVGParser()
        case "tldraw":
            input_parser = TLDrawParser()
        case "excalidraw" | "obsidian":
            input_parser = ExcalidrawParser()
        case "mermaid":
            input_parser = MermaidParser()
        case "plantuml":
            input_parser = PlantUMLParser()
        case _:
            raise _CLIError(f"Unsupported input format: {input_format}")

    try:
        diagram = input_parser.parse(input_data)
    except ValueError as err:
        raise _CLIError(f"Failed to parse {input_format} input: {err}") from err
    return diagram, list(getattr(input_parser, "warnings", []))


def _generate_output(diagram: Diagram, args: argparse.Namespace) -> tuple[str, Optional[str]]:
    """Generate output text; returns (output, mermaid diagram type when applicable)."""
    match args.format:
        case "plantuml":
            return (PlantUMLGenerator().generate(diagram), None)
        case "c4":
            return (C4PlantUMLGenerator().generate(diagram), None)
        case "mermaid":
            mermaid_gen = MermaidGenerator(diagram_type=args.mermaid_type)
            output = mermaid_gen.generate(diagram)
            return (output, mermaid_gen.detected_type)
        case "graphviz":
            config = GraphVizConfig(
                direction=args.graphviz_direction,
                graph_type=args.graphviz_type,
            )
            return (GraphVizGenerator(config=config).generate(diagram), None)
        case "d2":
            d2_config = D2Config(
                direction=args.d2_direction,
                sketch=args.d2_sketch,
            )
            return (D2Generator(config=d2_config).generate(diagram), None)
        case _:
            raise _CLIError(f"Unknown format: {args.format}")


def _semantic_type_name(semantic_type: Any) -> Optional[str]:
    if semantic_type is None:
        return None
    return getattr(semantic_type, "value", semantic_type)


def _element_summaries(diagram: Diagram) -> list[dict[str, Any]]:
    summaries = []
    for element in diagram.elements:
        label = getattr(element, "label", "") or getattr(element, "content", "")
        summaries.append(
            {
                "id": element.id,
                "label": label,
                "semantic_type": _semantic_type_name(element.semantic_type),
                "confidence": round(element.semantic_confidence, 3),
            }
        )
    return summaries


def _emit_error(message: str, exit_code: int, as_json: bool) -> int:
    if as_json:
        print(json.dumps({"error": message, "exit_code": exit_code}), file=sys.stderr)
    else:
        print(f"Error: {message}", file=sys.stderr)
    return exit_code


def _write_output_file(output: str, output_arg: str) -> None:
    output_path = Path(output_arg)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(output)


def _run_convert(argv: list[str]) -> int:
    parser = create_parser()
    args = parser.parse_args(argv)

    try:
        content = _read_content(args.input)
        input_format, input_data = _resolve_input_format(content, args.input_format)
        diagram, warnings = _parse_to_diagram(input_format, input_data)
        if not diagram.elements:
            raise _CLIError(
                "parsed 0 elements; the file may use an unsupported schema",
                EXIT_EMPTY_DIAGRAM,
            )
        output, diagram_type = _generate_output(diagram, args)
    except _CLIError as err:
        return _emit_error(str(err), err.exit_code, args.json)
    except Exception as err:
        if args.verbose:
            traceback.print_exc()
        return _emit_error(str(err), EXIT_ERROR, args.json)

    if args.output != "-":
        _write_output_file(output, args.output)

    if args.json:
        envelope = {
            "output": output,
            "input_format": input_format,
            "output_format": args.format,
            "diagram_type": diagram_type,
            "elements": _element_summaries(diagram),
            "warnings": warnings,
        }
        print(json.dumps(envelope, indent=2))
        return EXIT_OK

    for warning in warnings:
        print(f"Warning: {warning}", file=sys.stderr)

    if args.output == "-":
        print(output)
    else:
        print(f"Generated {args.format} diagram: {args.output}", file=sys.stderr)

    return EXIT_OK


def _run_inspect(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="diacea inspect",
        description="Parse a diagram file and report detected format, element count, and semantic inference without converting",
    )
    parser.add_argument("input", help="Input file or - for stdin")
    parser.add_argument(
        "--input-format",
        default="auto",
        choices=_INPUT_FORMAT_CHOICES,
        help="Input format (default: auto-detect)",
    )
    parser.add_argument("--json", action="store_true", help="Emit the report as JSON to stdout")
    args = parser.parse_args(argv)

    try:
        content = _read_content(args.input)
        input_format, input_data = _resolve_input_format(content, args.input_format)
        diagram, warnings = _parse_to_diagram(input_format, input_data)
    except _CLIError as err:
        return _emit_error(str(err), err.exit_code, args.json)
    except Exception as err:
        return _emit_error(str(err), EXIT_ERROR, args.json)

    elements = _element_summaries(diagram)
    if not elements:
        warnings.append("parsed 0 elements; the file may use an unsupported schema")

    if args.json:
        report = {
            "input_format": input_format,
            "element_count": len(elements),
            "elements": elements,
            "warnings": warnings,
        }
        print(json.dumps(report, indent=2))
        return EXIT_OK

    print(f"Format: {input_format}")
    print(f"Elements: {len(elements)}")
    for summary in elements:
        semantic = summary["semantic_type"] or "-"
        print(
            f"  {summary['id']}: label={summary['label']!r}"
            f" semantic={semantic} confidence={summary['confidence']:.2f}"
        )
    for warning in warnings:
        print(f"Warning: {warning}", file=sys.stderr)
    return EXIT_OK


def _run_formats(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="diacea formats",
        description="List supported input and output formats",
    )
    parser.add_argument("--json", action="store_true", help="Emit the listing as JSON to stdout")
    args = parser.parse_args(argv)

    if args.json:
        print(
            json.dumps(
                {"input_formats": _INPUT_FORMATS, "output_formats": _OUTPUT_FORMATS},
                indent=2,
            )
        )
        return EXIT_OK

    print("Input formats:")
    for input_format in _INPUT_FORMATS:
        print(f"  {input_format['name']:<12}{input_format['description']}")
        print(f"  {'':<12}detection: {input_format['detection']}")
    print()
    print("Output formats:")
    for output_format in _OUTPUT_FORMATS:
        options = ", ".join(output_format["options"]) or "-"
        print(f"  {output_format['name']:<12}{output_format['description']}")
        print(f"  {'':<12}options: {options}")
    return EXIT_OK


_SYNC_SUFFIXES = {"c4": ".puml", "d2": ".d2", "graphviz": ".dot", "mermaid": ".mmd", "plantuml": ".puml"}


def _sync_output_path(source: Path, output_format: str, output_dir: Optional[str]) -> Path:
    name = source.name
    if name.endswith(".excalidraw.md"):
        stem = name.removesuffix(".excalidraw.md")
    else:
        stem = source.stem
    directory = Path(output_dir) if output_dir else source.parent
    return directory / f"{stem}{_SYNC_SUFFIXES[output_format]}"


def _run_sync(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="diacea sync",
        description="Regenerate text diagrams from their sources, writing outputs next to each source",
    )
    parser.add_argument("sources", nargs="+", help="Diagram source files")
    parser.add_argument(
        "-f",
        "--format",
        default="mermaid",
        choices=["plantuml", "c4", "mermaid", "graphviz", "d2"],
        help="Output format (default: mermaid)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Report stale outputs and exit 1 instead of writing",
    )
    parser.add_argument(
        "--output-dir",
        help="Directory for generated files (default: next to each source)",
    )
    _add_format_options(parser)
    args = parser.parse_args(argv)

    failed = False
    for source in args.sources:
        source_path = Path(source)
        target = _sync_output_path(source_path, args.format, args.output_dir)
        if target == source_path:
            print(f"Error: {source}: output path equals the source; skipping", file=sys.stderr)
            failed = True
            continue
        try:
            content = _read_content(source)
            input_format, input_data = _resolve_input_format(content, "auto")
            diagram, _warnings = _parse_to_diagram(input_format, input_data)
            if not diagram.elements:
                raise _CLIError("parsed 0 elements; the file may use an unsupported schema")
            output, _diagram_type = _generate_output(diagram, args)
        except (_CLIError, ValueError, json.JSONDecodeError) as err:
            print(f"Error: {source}: {err}", file=sys.stderr)
            failed = True
            continue
        text = output if output.endswith("\n") else output + "\n"
        if target.exists() and target.read_text() == text:
            continue
        if args.check:
            print(f"stale: {target}", file=sys.stderr)
            failed = True
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)
            print(f"wrote {target}", file=sys.stderr)

    return EXIT_ERROR if failed else EXIT_OK


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for the convert command.

    Returns:
        Configured ArgumentParser
    """
    parser = argparse.ArgumentParser(
        prog="diacea",
        description="Universal diagram converter - the pandoc for diagrams",
        epilog="Examples:\n"
        "  diacea -i diagram.json -f mermaid -o output.mmd\n"
        "  diacea -i diagram.json -f mermaid --json\n"
        "  diacea -i diagram.json -f graphviz --graphviz-direction TB\n"
        "  cat diagram.json | diacea -i - -f c4\n"
        "  diacea inspect diagram.json --json\n"
        "  diacea formats --json\n"
        "  diacea sync docs/arch.excalidraw -f mermaid",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Input/Output
    parser.add_argument(
        "-i",
        "--input",
        required=True,
        help="Input file (Excalidraw/TLDraw JSON, Obsidian .excalidraw.md, SVG) or - for stdin",
    )

    parser.add_argument(
        "-o",
        "--output",
        default="-",
        help="Output file or - for stdout (default: stdout)",
    )

    parser.add_argument(
        "--input-format",
        default="auto",
        choices=_INPUT_FORMAT_CHOICES,
        help="Input format (default: auto-detect)",
    )

    parser.add_argument(
        "-f",
        "--format",
        required=True,
        choices=["plantuml", "c4", "mermaid", "graphviz", "d2"],
        help="Output format",
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a JSON envelope (output, formats, elements, warnings) to stdout; errors go to stderr as JSON",
    )

    _add_format_options(parser)

    # General options
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose output (show stack traces)",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {_get_version()}",
    )

    return parser


def _add_format_options(parser: argparse.ArgumentParser) -> None:
    mermaid_group = parser.add_argument_group("mermaid options")
    mermaid_group.add_argument(
        "--mermaid-type",
        choices=["flowchart", "c4", "sequence"],
        help="Mermaid diagram type (default: auto-detect)",
    )

    graphviz_group = parser.add_argument_group("graphviz options")
    graphviz_group.add_argument(
        "--graphviz-direction",
        choices=["LR", "TB", "RL", "BT"],
        help="GraphViz layout direction (default: auto-detect)",
    )

    graphviz_group.add_argument(
        "--graphviz-type",
        default="digraph",
        choices=["digraph", "graph"],
        help="GraphViz graph type: digraph=directed, graph=undirected (default: digraph)",
    )

    d2_group = parser.add_argument_group("d2 options")
    d2_group.add_argument(
        "--d2-direction",
        choices=["up", "down", "left", "right"],
        help="D2 layout direction (default: auto-detect)",
    )

    d2_group.add_argument(
        "--d2-sketch",
        action="store_true",
        help="Use D2 sketch mode (hand-drawn look)",
    )


def _get_version() -> str:
    """Get package version.

    Returns:
        Version string
    """
    try:
        from . import __version__

        return __version__
    except ImportError:
        return "unknown"


if __name__ == "__main__":
    sys.exit(main())
