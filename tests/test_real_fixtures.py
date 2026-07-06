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

_EXCALIDRAW_INT_DIMENSIONS = (
    'ExcalidrawParser passes raw JSON ints to float-typed IR fields '
    '(Dimensions.width/height); fails under beartype runtime checks'
)

_XFAIL_REASONS = {
    'ai_patent_check_app.mmd': 'Mermaid YAML frontmatter (---/title/---) breaks format detection and parsing',
    'dynamic_loading_mechanism.mmd': 'Mermaid YAML frontmatter (---/title/---) breaks format detection and parsing',
    'fineract_release_process.puml': 'PlantUML activity diagram syntax unsupported; parses 0 elements',
    'intertwin_c4_qa_pipeline.excalidraw': _EXCALIDRAW_INT_DIMENSIONS,
    'intertwin_dte_infra_containers.excalidraw': _EXCALIDRAW_INT_DIMENSIONS,
    'intertwin_system_context.excalidraw': _EXCALIDRAW_INT_DIMENSIONS,
    'llm_proxy_component.svg': "SVG path curve commands desync the tokenizer: ValueError could not convert string to float: 'l'",
    'mcp_playwright_architecture.mmd': 'Mermaid YAML frontmatter (---/title/---) breaks format detection and parsing',
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
    raise ValueError(f'Unhandled fixture suffix: {path}')


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
