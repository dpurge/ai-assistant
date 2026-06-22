from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config import Settings, clear_settings_cache, get_settings


def test_default_settings_values(monkeypatch: pytest.MonkeyPatch):
    for var in ("OLLAMA_HOST", "OLLAMA_PORT", "OLLAMA_MODEL"):
        monkeypatch.delenv(var, raising=False)
    clear_settings_cache()

    settings = get_settings()

    assert settings.ollama_host == "localhost"
    assert settings.ollama_port == 11434
    assert settings.ollama_model == "ollama_chat/gemma4:31b"
    assert settings.fetch_timeout_seconds == 10.0
    assert settings.max_file_text_chars == 100_000
    assert settings.max_page_text_chars == 100_000
    assert settings.verify_ssl_certificates is False
    assert settings.ollama_api_base == "http://localhost:11434"


def test_env_overrides_apply(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OLLAMA_HOST", "ollama.internal")
    monkeypatch.setenv("OLLAMA_PORT", "9999")
    monkeypatch.setenv("OLLAMA_MODEL", "ollama_chat/llama3:8b")
    monkeypatch.setenv("FETCH_TIMEOUT_SECONDS", "30")
    clear_settings_cache()

    settings = get_settings()

    assert settings.ollama_host == "ollama.internal"
    assert settings.ollama_port == 9999
    assert settings.ollama_model == "ollama_chat/llama3:8b"
    assert settings.fetch_timeout_seconds == 30.0
    assert settings.ollama_api_base == "http://ollama.internal:9999"


def test_settings_validation_rejects_out_of_range_timeout():
    with pytest.raises(ValidationError):
        Settings(fetch_timeout_seconds=0.0)
    with pytest.raises(ValidationError):
        Settings(fetch_timeout_seconds=999.0)


def test_get_settings_is_cached():
    first = get_settings()
    second = get_settings()
    assert first is second
    clear_settings_cache()
    third = get_settings()
    assert third is not first
