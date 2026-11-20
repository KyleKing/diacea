"""Command-line interface for diacea diagram converter."""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path
from typing import Any

from .formats import (
    INPUT_FORMATS,
    OUTPUT_FORMATS,
    ConversionResult,
    FormatError,
    ParseResult,
    detect_input_format,
    output_format_for_path,
    parse_diagram,
    render_diagram,
)
from .generators._text import DECLARED_CONFIDENCE
from .ir.elements import Diagram, Shape
from .ir.semantic import SemanticType

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_EMPTY_DIAGRAM = 2

_EMPTY_DIAGRAM_MESSAGE = 'parsed 0 elements; the file may use an unsupported schema'

_HINT_HELP = (
    "Set an element's semantic type by id or label, e.g. --hint 'Orders DB=database' "
    '(repeatable; see `diacea formats` for the types)'
)

__all__ = ['EXIT_EMPTY_DIAGRAM', 'EXIT_ERROR', 'EXIT_OK', 'create_parser', 'detect_input_format', 'main']


class _CLIError(Exception):
    """CLI failure with an associated exit code."""

    def __init__(self, message: str, exit_code: int = EXIT_ERROR) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def main(argv: list[str] | None = None) -> int:
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
        case ['convert', *rest]:
            return _run_convert(rest)
        case ['formats', *rest]:
            return _run_formats(rest)
        case ['inspect', *rest]:
            return _run_inspect(rest)
        case ['sync', *rest]:
            return _run_sync(rest)
        case _:
            return _run_convert(args_list)


def _read_content(input_arg: str) -> str:
    if input_arg == '-':
        return sys.stdin.read()
    input_path = Path(input_arg)
    if not input_path.exists():
        msg = f'Input file not found: {input_arg}'
        raise _CLIError(msg)
    try:
        return input_path.read_text(encoding='utf-8')
    except UnicodeDecodeError as err:
        msg = f'Input file is not UTF-8 text: {input_arg}'
        raise _CLIError(msg) from err


def _parse_hints(raw_hints: list[str] | None) -> dict[str, str]:
    hints: dict[str, str] = {}
    for raw in raw_hints or []:
        key, separator, type_name = raw.rpartition('=')
        if not separator or not key.strip() or not type_name.strip():
            msg = f"Invalid --hint {raw!r}: expected 'ID_OR_LABEL=TYPE', e.g. --hint 'Orders DB=database'"
            raise _CLIError(msg)
        hints[key.strip()] = type_name.strip()
    return hints


def _parse_input(input_arg: str, input_format: str, raw_hints: list[str] | None = None) -> ParseResult:
    """Read and parse an input file (or stdin) into the IR."""
    content = _read_content(input_arg)
    filename = None if input_arg == '-' else input_arg
    try:
        return parse_diagram(content, input_format, filename=filename, hints=_parse_hints(raw_hints))
    except json.JSONDecodeError as err:
        msg = f'Failed to parse {input_format} input: invalid JSON ({err})'
        raise _CLIError(msg) from err
    except FormatError as err:
        raise _CLIError(str(err)) from err


def _render(diagram: Diagram, output_format: str, args: argparse.Namespace) -> ConversionResult:
    options = {option.dest: getattr(args, option.dest, None) for option in OUTPUT_FORMATS[output_format].options}
    return render_diagram(diagram, output_format, **options)


def _semantic_type_name(semantic_type: Any) -> str | None:
    if semantic_type is None:
        return None
    return getattr(semantic_type, 'value', semantic_type)


def _element_summaries(diagram: Diagram) -> list[dict[str, Any]]:
    summaries = []
    for element in diagram.elements:
        label = getattr(element, 'label', '') or getattr(element, 'content', '')
        summary = {
            'id': element.id,
            'type': element.element_type,
            'label': label,
            'semantic_type': _semantic_type_name(element.semantic_type),
            'confidence': round(element.semantic_confidence, 3),
        }
        if isinstance(element, Shape):
            summary['shape'] = element.shape_type
        if 'source_id' in element.metadata:
            summary['source_id'] = element.metadata['source_id']
        summaries.append(summary)
    return summaries


def _emit_error(message: str, exit_code: int, as_json: bool) -> int:
    if as_json:
        print(json.dumps({'error': message, 'exit_code': exit_code}), file=sys.stderr)
    else:
        print(f'Error: {message}', file=sys.stderr)
    return exit_code


def _write_output_file(output: str, output_arg: str) -> None:
    output_path = Path(output_arg)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(output, encoding='utf-8')


def _resolve_convert_args(args: argparse.Namespace) -> tuple[str, str]:
    """Settle the input path and output format from flags, positionals, and the output suffix."""
    if args.input and args.input_file and args.input != args.input_file:
        msg = f'Two inputs given ({args.input_file!r} and -i {args.input!r}); pass only one'
        raise _CLIError(msg)
    input_arg = args.input or args.input_file
    if not input_arg:
        raise _CLIError(
            'No input given: pass a diagram file (or - for stdin), e.g. diacea diagram.excalidraw -f mermaid'
        )

    output_format = args.format
    if output_format is None and args.output != '-':
        output_format = output_format_for_path(args.output)
    if output_format is None:
        known = ', '.join(OUTPUT_FORMATS)
        msg = f'No output format given: pass -f FORMAT ({known}) or an -o file with a known extension'
        raise _CLIError(msg)
    return input_arg, output_format


def _run_convert(argv: list[str]) -> int:
    parser = create_parser()
    args = parser.parse_args(argv)

    try:
        input_arg, output_format = _resolve_convert_args(args)
        parsed = _parse_input(input_arg, args.input_format, args.hint)
        if not parsed.diagram.elements:
            raise _CLIError(_EMPTY_DIAGRAM_MESSAGE, EXIT_EMPTY_DIAGRAM)
        result = _render(parsed.diagram, output_format, args)
    except _CLIError as err:
        return _emit_error(str(err), err.exit_code, args.json)
    except Exception as err:
        if args.verbose:
            traceback.print_exc()
        return _emit_error(str(err), EXIT_ERROR, args.json)

    warnings = [*parsed.warnings, *result.warnings]
    if args.output != '-':
        _write_output_file(result.output, args.output)

    if args.json:
        envelope = {
            'output': result.output,
            'input_format': parsed.input_format,
            'output_format': output_format,
            'diagram_type': result.diagram_type,
            'elements': _element_summaries(parsed.diagram),
            'warnings': warnings,
        }
        print(json.dumps(envelope, indent=2))
        return EXIT_OK

    for warning in warnings:
        print(f'Warning: {warning}', file=sys.stderr)

    if args.output == '-':
        print(result.output)
    else:
        print(f'Generated {output_format} diagram: {args.output}', file=sys.stderr)

    return EXIT_OK


def _run_inspect(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog='diacea inspect',
        description=(
            'Parse a diagram file and report detected format, element count, and semantic inference without converting'
        ),
    )
    parser.add_argument('input', help='Input file or - for stdin')
    parser.add_argument(
        '--input-format',
        default='auto',
        choices=['auto', *sorted(INPUT_FORMATS)],
        help='Input format (default: auto-detect)',
    )
    parser.add_argument('--hint', action='append', metavar='ID_OR_LABEL=TYPE', help=_HINT_HELP)
    parser.add_argument('--json', action='store_true', help='Emit the report as JSON to stdout')
    args = parser.parse_args(argv)

    try:
        parsed = _parse_input(args.input, args.input_format, args.hint)
    except _CLIError as err:
        return _emit_error(str(err), err.exit_code, args.json)
    except Exception as err:
        return _emit_error(str(err), EXIT_ERROR, args.json)

    diagram = parsed.diagram
    warnings = parsed.warnings
    elements = _element_summaries(diagram)
    if not elements:
        warnings.append(_EMPTY_DIAGRAM_MESSAGE)

    if args.json:
        report = {
            'input_format': parsed.input_format,
            'element_count': len(elements),
            'elements': elements,
            'warnings': warnings,
        }
        print(json.dumps(report, indent=2))
        return EXIT_OK

    print(f'Format: {parsed.input_format}')
    print(f'Elements: {len(elements)}')
    for summary in elements:
        semantic = summary['semantic_type'] or '-'
        print(
            f'  {summary["id"]}: label={summary["label"]!r} semantic={semantic} confidence={summary["confidence"]:.2f}'
        )
    for warning in warnings:
        print(f'Warning: {warning}', file=sys.stderr)
    if any(shape.semantic_confidence < DECLARED_CONFIDENCE for shape in diagram.get_shapes()):
        print(
            "Tip: types with confidence below 0.90 are guesses. To correct one, add a stereotype to the element's "
            "label in the source (e.g. 'Orders <<database>>') or pass --hint 'Orders=database'.",
            file=sys.stderr,
        )
    return EXIT_OK


def _run_formats(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog='diacea formats',
        description='List supported input and output formats',
    )
    parser.add_argument('--json', action='store_true', help='Emit the listing as JSON to stdout')
    args = parser.parse_args(argv)

    input_formats = [
        {'name': fmt.name, 'description': fmt.description, 'detection': fmt.detection, 'extensions': list(fmt.suffixes)}
        for fmt in sorted(INPUT_FORMATS.values(), key=lambda fmt: fmt.name)
    ]
    output_formats = [
        {
            'name': fmt.name,
            'description': fmt.description,
            'extension': fmt.suffix,
            'options': [option.usage for option in fmt.options],
        }
        for fmt in OUTPUT_FORMATS.values()
    ]
    semantic_types = sorted(member.value for member in SemanticType)

    if args.json:
        print(
            json.dumps(
                {'input_formats': input_formats, 'output_formats': output_formats, 'semantic_types': semantic_types},
                indent=2,
            )
        )
        return EXIT_OK

    print('Input formats:')
    for input_format in input_formats:
        print(f'  {input_format["name"]:<12}{input_format["description"]}')
        print(f'  {"":<12}detection: {input_format["detection"]}')
    print()
    print('Output formats:')
    for output_format in output_formats:
        options = ', '.join(output_format['options']) or '-'
        print(f'  {output_format["name"]:<12}{output_format["description"]}')
        print(f'  {"":<12}options: {options}')
    print()
    print('Semantic types (for <<type>> label stereotypes and --hint):')
    print(f'  {", ".join(semantic_types)}')
    return EXIT_OK


def _sync_output_path(source: Path, output_format: str, output_dir: str | None) -> Path:
    name = source.name
    stem = name.removesuffix('.excalidraw.md') if name.endswith('.excalidraw.md') else source.stem
    directory = Path(output_dir) if output_dir else source.parent
    return directory / f'{stem}{OUTPUT_FORMATS[output_format].suffix}'


def _run_sync(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog='diacea sync',
        description='Regenerate text diagrams from their sources, writing outputs next to each source',
    )
    parser.add_argument('sources', nargs='+', help='Diagram source files')
    parser.add_argument(
        '-f',
        '--format',
        default='mermaid',
        choices=list(OUTPUT_FORMATS),
        help='Output format (default: mermaid)',
    )
    parser.add_argument(
        '--check',
        action='store_true',
        help='Report stale outputs and exit 1 instead of writing',
    )
    parser.add_argument(
        '--output-dir',
        help='Directory for generated files (default: next to each source)',
    )
    parser.add_argument('--hint', action='append', metavar='ID_OR_LABEL=TYPE', help=_HINT_HELP)
    _add_format_options(parser)
    args = parser.parse_args(argv)

    failed = False
    for source in args.sources:
        source_path = Path(source)
        target = _sync_output_path(source_path, args.format, args.output_dir)
        if target == source_path:
            print(f'Error: {source}: output path equals the source; skipping', file=sys.stderr)
            failed = True
            continue
        try:
            parsed = _parse_input(source, 'auto', args.hint)
            if not parsed.diagram.elements:
                raise _CLIError(_EMPTY_DIAGRAM_MESSAGE)
            output = _render(parsed.diagram, args.format, args).output
        except (_CLIError, ValueError) as err:
            print(f'Error: {source}: {err}', file=sys.stderr)
            failed = True
            continue
        text = output if output.endswith('\n') else output + '\n'
        if target.exists() and target.read_text(encoding='utf-8') == text:
            continue
        if args.check:
            print(f'stale: {target}', file=sys.stderr)
            failed = True
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding='utf-8')
            print(f'wrote {target}', file=sys.stderr)

    return EXIT_ERROR if failed else EXIT_OK


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for the convert command.

    Returns:
        Configured ArgumentParser
    """
    parser = argparse.ArgumentParser(
        prog='diacea',
        description='Universal diagram converter - the pandoc for diagrams',
        epilog='Examples:\n'
        '  diacea diagram.excalidraw -f mermaid\n'
        '  diacea diagram.excalidraw -o diagram.mmd      (format from the extension)\n'
        '  diacea flow.mmd -o flow.excalidraw            (text to an editable drawing)\n'
        '  diacea graph.dot -f d2 --d2-sketch\n'
        '  cat diagram.json | diacea - -f c4\n'
        "  diacea sketch.excalidraw -f c4 --hint 'Orders=database'\n"
        '  diacea inspect diagram.excalidraw --json\n'
        '  diacea formats --json\n'
        '  diacea sync docs/arch.excalidraw -f mermaid',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument('input_file', nargs='?', metavar='INPUT', help='Input diagram file, or - for stdin')
    parser.add_argument('-i', '--input', help='Input diagram file, or - for stdin (same as the positional INPUT)')
    parser.add_argument(
        '-o',
        '--output',
        default='-',
        help='Output file or - for stdout (default: stdout)',
    )
    parser.add_argument(
        '--input-format',
        default='auto',
        choices=['auto', *sorted(INPUT_FORMATS)],
        help='Input format (default: auto-detect from content, then file extension)',
    )
    parser.add_argument(
        '-f',
        '--format',
        choices=list(OUTPUT_FORMATS),
        help='Output format (default: inferred from the -o file extension)',
    )
    parser.add_argument('--hint', action='append', metavar='ID_OR_LABEL=TYPE', help=_HINT_HELP)
    parser.add_argument(
        '--json',
        action='store_true',
        help='Emit a JSON envelope (output, formats, elements, warnings) to stdout; errors go to stderr as JSON',
    )

    _add_format_options(parser)

    parser.add_argument(
        '-v',
        '--verbose',
        action='store_true',
        help='Verbose output (show stack traces)',
    )
    parser.add_argument(
        '--version',
        action='version',
        version=f'%(prog)s {_get_version()}',
    )

    return parser


def _add_format_options(parser: argparse.ArgumentParser) -> None:
    for fmt in OUTPUT_FORMATS.values():
        if not fmt.options:
            continue
        group = parser.add_argument_group(f'{fmt.name} options')
        for option in fmt.options:
            if option.is_flag:
                group.add_argument(option.flag, action='store_true', help=option.help)
            else:
                group.add_argument(option.flag, choices=option.choices, default=option.default, help=option.help)


def _get_version() -> str:
    """Get package version.

    Returns:
        Version string
    """
    try:
        from . import __version__
    except ImportError:
        return 'unknown'
    else:
        return __version__


if __name__ == '__main__':
    sys.exit(main())
