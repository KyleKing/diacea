# ruff:file-ignore[unused-import]
"""nox configuration file."""

from calcipy.noxfile import tests
from nox import Session as NoxSession
from nox import session as nox_session


@nox_session(venv_backend='uv', reuse_venv=True)
def render_gate(session: NoxSession) -> None:
    """Run render-gated curated fixture checks; requires mmdc, plantuml, dot, and d2 on PATH."""
    session.run_install(
        'uv',
        'sync',
        '--all-extras',
        env={'UV_PROJECT_ENVIRONMENT': session.virtualenv.location},
    )
    session.run('pytest', 'tests/test_curated_fixtures.py', env={'DIACEA_RENDER': '1'})
