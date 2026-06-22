"""Flush Langfuse buffered events at the end of a request/process."""

from __future__ import annotations

from app.config import Settings
from app.observability.langfuse_client import get_langfuse


def flush_langfuse(settings: Settings | None = None) -> None:
    client = get_langfuse(settings)
    if client is None:
        return
    flush = getattr(client, "flush", None)
    if callable(flush):
        flush()
