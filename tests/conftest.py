"""Pytest defaults.

- Isolate working directory so ``Settings(env_file=".env")`` does not pick up a
  developer ``.env`` during unit tests.
- Blank Langfuse env vars so shells with exported keys remain deterministic.
- Clear the ``get_settings`` lru_cache around every test so env changes take
  effect.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


@pytest.fixture(autouse=True)
def _pytest_workdir_no_dotenv(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    wd = tmp_path / "proj"
    wd.mkdir()
    monkeypatch.chdir(wd)


@pytest.fixture(autouse=True)
def _neutralize_runtime_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGFUSE_HOST", "")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "")
    # Force the deterministic fake embedding backend in tests so we never need
    # an Ollama instance to be running.
    monkeypatch.setenv("EMBEDDING_USE_FAKE", "true")


@pytest.fixture(autouse=True)
def _clear_caches():
    from app.config import clear_settings_cache
    from app.corpus_singleton import clear_corpus_cache

    clear_settings_cache()
    clear_corpus_cache()
    yield
    clear_settings_cache()
    clear_corpus_cache()


@pytest.fixture
def fake_tool_context():
    """Minimal stand-in for ``google.adk.tools.ToolContext`` with a state dict."""

    class _FakeToolContext:
        def __init__(self) -> None:
            self.state: dict = {}

    return _FakeToolContext()
