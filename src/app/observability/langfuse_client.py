"""Langfuse helper - lazy import; offline-safe when LANGFUSE_* is unset."""

from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings


class LangfuseUnavailable(RuntimeError):
    """Raised when callers require Langfuse but env is incomplete."""


def _credentials_ok(settings: Settings) -> bool:
    return bool(
        settings.langfuse_host
        and settings.langfuse_public_key
        and settings.langfuse_secret_key
    )


def langfuse_enabled(settings: Settings | None = None) -> bool:
    return _credentials_ok(settings or get_settings())


def get_langfuse(settings: Settings | None = None, *, strict: bool = False) -> Any | None:
    cfg = settings or get_settings()
    if not _credentials_ok(cfg):
        if strict:
            raise LangfuseUnavailable(
                "Set LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY for Langfuse."
            )
        return None
    from langfuse import Langfuse  # noqa: PLC0415

    return Langfuse(
        host=str(cfg.langfuse_host).rstrip("/"),
        public_key=cfg.langfuse_public_key,
        secret_key=cfg.langfuse_secret_key,
    )


def start_optional_span(
    *,
    name: str,
    input: Any | None = None,
    settings: Settings | None = None,
) -> Any | None:
    """Open a Langfuse span when configured; callers should call ``span.end()`` when done."""
    client = get_langfuse(settings)
    if client is None:
        return None
    return client.start_span(name=name, input=input)
