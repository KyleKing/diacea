"""Command-line interface for diacea."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from diacea import __version__, generate_c4_plantuml, generate_plantuml
from diacea.experiments import (
    convert_to_relative,
    csp_solver,
    graph_based_approach,
    quadtree_approach,
    rule_based_approach,
)

# Map of algorithm names to functions
ALGORITHMS = {
    'convert_to_relative': convert_to_relative,
    'rule_based_approach': rule_based_approach,
    'csp_solver': csp_solver,
    'quadtree_approach': quadtree_approach,
    'graph_based_approach': graph_based_approach,
}


def main(argv: list[str] | None = None) -> int:
    """Main CLI entry point.

    Args:
        argv: Command-line arguments (defaults to sys.argv)

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    parser = argparse.ArgumentParser(
        description='Convert Excalidraw diagrams to PlantUML',
        prog='diacea',
    )
    parser.add_argument(
        '-i',
        '--input',
        required=True,
        type=Path,
        help='Input Excalidraw JSON file',
    )
    parser.add_argument(
        '-o',
        '--output',
        type=Path,
        help='Output PlantUML file (defaults to input filename with .puml extension)',
    )
    parser.add_argument(
        '-a',
        '--algorithm',
        default='graph_based_approach',
        choices=list(ALGORITHMS.keys()),
        help='Conversion algorithm to use (default: graph_based_approach)',
    )
    parser.add_argument(
        '-f',
        '--format',
        default='c4',
        choices=['basic', 'c4'],
        help='Output format: basic PlantUML or C4-PlantUML (default: c4)',
    )
    parser.add_argument(
        '--version',
        action='version',
        version=f'%(prog)s {__version__}',
    )

    args = parser.parse_args(argv)

    # Determine output file path
    output_path = args.output
    if output_path is None:
        output_path = args.input.with_suffix('.puml')

    # Load input file
    try:
        with args.input.open() as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f'Error: Input file not found: {args.input}', file=sys.stderr)
        return 1
    except json.JSONDecodeError as e:
        print(f'Error: Invalid JSON in {args.input}: {e}', file=sys.stderr)
        return 1
    except Exception as e:
        print(f'Error: Failed to read {args.input}: {e}', file=sys.stderr)
        return 1

    # Extract elements
    if 'elements' not in data:
        print(f'Error: No "elements" key found in {args.input}', file=sys.stderr)
        return 1

    elements = data['elements']
    if not elements:
        print(f'Warning: No elements found in {args.input}', file=sys.stderr)

    # Generate PlantUML based on format
    try:
        if args.format == 'c4':
            # C4 format works directly with Excalidraw elements
            plantuml = generate_c4_plantuml(elements)
        else:
            # Basic format uses relative conversion first
            algorithm_func = ALGORITHMS[args.algorithm]
            relative_data = algorithm_func(elements)
            plantuml = generate_plantuml(relative_data)
    except Exception as e:
        print(f'Error: PlantUML generation failed: {e}', file=sys.stderr)
        return 1

    # Write output file
    try:
        output_path.write_text(plantuml)
    except Exception as e:
        print(f'Error: Failed to write to {output_path}: {e}', file=sys.stderr)
        return 1

    print(f'Successfully converted {args.input} to {output_path}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
