"""diacea."""

from ._runtime_type_check_setup import configure_runtime_type_checking_mode

__version__ = '0.0.1'
__pkg_name__ = 'diacea'

configure_runtime_type_checking_mode()


# == Above code must always be first ==

from .formats import (  # noqa: E402
    INPUT_FORMATS,
    OUTPUT_FORMATS,
    ConversionResult,
    FormatError,
    ParseResult,
    convert,
    detect_input_format,
    parse_diagram,
    parse_file,
    render_diagram,
)

__all__ = [
    'INPUT_FORMATS',
    'OUTPUT_FORMATS',
    'ConversionResult',
    'FormatError',
    'ParseResult',
    'convert',
    'detect_input_format',
    'parse_diagram',
    'parse_file',
    'render_diagram',
]
