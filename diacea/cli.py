"""Command-line interface for diacea diagram converter."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from .generators import (
    C4PlantUMLGenerator,
    D2Config,
    D2Generator,
    GraphVizConfig,
    GraphVizGenerator,
    MermaidGenerator,
    PlantUMLGenerator,
)
from .parsers import ExcalidrawParser, TLDrawParser


def detect_input_format(data: dict) -> str:
    """Detect input format from JSON structure.

    Args:
        data: JSON data dictionary

    Returns:
        Format name ('tldraw' or 'excalidraw')

    Raises:
        ValueError: If format cannot be detected
    """
    # TLDraw has "document" -> "pages" structure
    if "document" in data and "pages" in data.get("document", {}):
        return "tldraw"

    # Excalidraw has "elements" or "type": "excalidraw/clipboard"
    if "elements" in data or data.get("type") == "excalidraw/clipboard":
        return "excalidraw"

    raise ValueError("Unknown input format - expected TLDraw or Excalidraw JSON")


def main(argv: Optional[list[str]] = None) -> int:
    """Main CLI entry point.

    Args:
        argv: Command-line arguments (None = sys.argv)

    Returns:
        Exit code (0 = success)
    """
    parser = create_parser()
    args = parser.parse_args(argv)

    try:
        # Read input file
        if args.input == "-":
            input_data = json.load(sys.stdin)
        else:
            input_path = Path(args.input)
            if not input_path.exists():
                print(f"Error: Input file not found: {args.input}", file=sys.stderr)
                return 1

            with open(input_path) as f:
                input_data = json.load(f)

        # Detect or use specified input format
        if args.input_format == "auto":
            input_format = detect_input_format(input_data)
        else:
            input_format = args.input_format

        # Parse input to IR based on format
        if input_format == "tldraw":
            input_parser = TLDrawParser()
            diagram = input_parser.parse(input_data)
        elif input_format == "excalidraw":
            input_parser = ExcalidrawParser()
            diagram = input_parser.parse(input_data)
        else:
            print(f"Error: Unsupported input format: {input_format}", file=sys.stderr)
            return 1

        # Generate output based on format
        if args.format == "plantuml":
            generator = PlantUMLGenerator()
            output = generator.generate(diagram)
        elif args.format == "c4":
            generator = C4PlantUMLGenerator()
            output = generator.generate(diagram)
        elif args.format == "mermaid":
            mermaid_gen = MermaidGenerator(diagram_type=args.mermaid_type)
            output = mermaid_gen.generate(diagram)
        elif args.format == "graphviz":
            config = GraphVizConfig(
                direction=args.graphviz_direction,
                graph_type=args.graphviz_type,
            )
            graphviz_gen = GraphVizGenerator(config=config)
            output = graphviz_gen.generate(diagram)
        elif args.format == "d2":
            d2_config = D2Config(
                direction=args.d2_direction,
                sketch=args.d2_sketch,
            )
            d2_gen = D2Generator(config=d2_config)
            output = d2_gen.generate(diagram)
        else:
            print(f"Error: Unknown format: {args.format}", file=sys.stderr)
            return 1

        # Write output
        if args.output == "-":
            print(output)
        else:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(output)
            print(f"Generated {args.format} diagram: {args.output}", file=sys.stderr)

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for CLI.

    Returns:
        Configured ArgumentParser
    """
    parser = argparse.ArgumentParser(
        prog="diacea",
        description="Universal diagram converter - the pandoc for diagrams",
        epilog="Examples:\n"
        "  diacea -i diagram.json -f mermaid -o output.mmd\n"
        "  diacea -i diagram.json -f graphviz --graphviz-direction TB\n"
        "  cat diagram.json | diacea -i - -f c4",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Input/Output
    parser.add_argument(
        "-i",
        "--input",
        required=True,
        help="Input file (Excalidraw or TLDraw JSON) or - for stdin",
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
        choices=["auto", "excalidraw", "tldraw"],
        help="Input format (default: auto-detect)",
    )

    parser.add_argument(
        "-f",
        "--format",
        required=True,
        choices=["plantuml", "c4", "mermaid", "graphviz", "d2"],
        help="Output format",
    )

    # Format-specific options
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
