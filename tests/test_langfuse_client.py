from __future__ import annotations

import pytest

from app.config import Settings
from app.observability.langfuse_client import (
    LangfuseUnavailable,
    get_langfuse,
    langfuse_enabled,
)
from app.observability.langfuse_flush import flush_langfuse


def _settings_without_langfuse() -> Settings:
    return Settings(
        langfuse_host=None,
        langfuse_public_key=None,
        langfuse_secret_key=None,
    )


def test_langfuse_disabled_when_env_unset(monkeypatch: pytest.MonkeyPatch):
    settings = _settings_without_langfuse()
    assert langfuse_enabled(settings) is False
    assert get_langfuse(settings) is None


def test_langfuse_disabled_when_only_some_keys_set():
    settings = Settings(
        langfuse_host="https://example.com",
        langfuse_public_key="pk",
        langfuse_secret_key=None,
    )
    assert langfuse_enabled(settings) is False
    assert get_langfuse(settings) is None


def test_strict_mode_raises_when_env_unset():
    settings = _settings_without_langfuse()
    with pytest.raises(LangfuseUnavailable):
        get_langfuse(settings, strict=True)


def test_flush_is_a_noop_when_langfuse_off():
    settings = _settings_without_langfuse()
    flush_langfuse(settings)  # must not raise
