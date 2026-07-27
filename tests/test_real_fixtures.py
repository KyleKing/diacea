"""Regression tests over real-world diagram fixtures in tests/data/real.

Provenance for each file is recorded in tests/data/real/README.md. Files that
diacea cannot currently parse are xfail-marked with the observed defect.
"""

import json

import pytest

from diacea.parsers import (
    ExcalidrawParser,
    MermaidParser,
    PlantUMLParser,
    SVGParser,
    TLDrawParser,
)

from .configuration import TEST_DATA_DIR

REAL_DATA_DIR = TEST_DATA_DIR / 'real'

_XFAIL_REASONS = {
    'fineract_release_process.puml': 'PlantUML activity diagrams are explicitly rejected with ValueError',
}


def _parse(path):
    content = path.read_text()
    match path.suffix:
        case '.mmd':
            return MermaidParser().parse(content)
        case '.puml':
            return PlantUMLParser().parse(content)
        case '.svg':
            return SVGParser().parse(content)
        case '.tldr':
            return TLDrawParser().parse(json.loads(content))
        case '.excalidraw':
            return ExcalidrawParser().parse(json.loads(content))
    msg = f'Unhandled fixture suffix: {path}'
    raise ValueError(msg)


def _params():
    for path in sorted(REAL_DATA_DIR.iterdir()):
        if path.name == 'README.md':
            continue
        marks = []
        if (reason := _XFAIL_REASONS.get(path.name)) is not None:
            marks = [pytest.mark.xfail(reason=reason, strict=True)]
        yield pytest.param(path, id=path.name, marks=marks)


@pytest.mark.parametrize('fixture_path', _params())
def test_real_fixture_parses(fixture_path):
    diagram = _parse(fixture_path)

    assert len(diagram.elements) > 0
