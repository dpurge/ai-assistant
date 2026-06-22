"""Runtime configuration for the AI assistant.

Loaded once at process start from environment + optional ``.env``. All hot-path
constants (model selection, Ollama endpoint, fetch limits, optional Langfuse
credentials) flow through a single ``Settings`` instance so that tests can
override them and so that adding a new knob is one field, not a new module
constant.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    ollama_host: str = Field(
        default="localhost",
        validation_alias=AliasChoices("OLLAMA_HOST"),
    )
    ollama_port: int = Field(
        default=11434,
        ge=1,
        le=65535,
        validation_alias=AliasChoices("OLLAMA_PORT"),
    )
    ollama_model: str = Field(
        default="ollama_chat/gemma4:31b",
        validation_alias=AliasChoices("OLLAMA_MODEL"),
    )

    fetch_timeout_seconds: float = Field(
        default=10.0,
        ge=1.0,
        le=120.0,
        validation_alias=AliasChoices("FETCH_TIMEOUT_SECONDS"),
    )
    max_file_text_chars: int = Field(
        default=100_000,
        ge=1_000,
        validation_alias=AliasChoices("MAX_FILE_TEXT_CHARS"),
    )
    max_page_text_chars: int = Field(
        default=100_000,
        ge=1_000,
        validation_alias=AliasChoices("MAX_PAGE_TEXT_CHARS"),
    )
    verify_ssl_certificates: bool = Field(
        default=False,
        validation_alias=AliasChoices("VERIFY_SSL_CERTIFICATES"),
    )

    langfuse_public_key: str | None = Field(
        default=None, validation_alias=AliasChoices("LANGFUSE_PUBLIC_KEY")
    )
    langfuse_secret_key: str | None = Field(
        default=None, validation_alias=AliasChoices("LANGFUSE_SECRET_KEY")
    )
    langfuse_host: str | None = Field(
        default=None, validation_alias=AliasChoices("LANGFUSE_HOST")
    )

    embedding_model: str = Field(
        default="nomic-embed-text",
        validation_alias=AliasChoices("EMBEDDING_MODEL"),
    )
    embedding_dimension: int = Field(
        default=768,
        ge=8,
        validation_alias=AliasChoices("EMBEDDING_DIMENSION"),
    )
    corpus_persist_dir: Path | None = Field(
        default=None,
        validation_alias=AliasChoices("CORPUS_PERSIST_DIR"),
    )
    embedding_use_fake: bool = Field(
        default=False,
        validation_alias=AliasChoices("EMBEDDING_USE_FAKE"),
    )

    @property
    def ollama_api_base(self) -> str:
        return f"http://{self.ollama_host}:{self.ollama_port}"


@lru_cache
def get_settings(**overrides: Any) -> Settings:
    if not overrides:
        return Settings()
    return Settings(**overrides)


def clear_settings_cache() -> None:
    get_settings.cache_clear()
