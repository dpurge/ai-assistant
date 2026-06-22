"""Split unstructured text into retrieval-sized windows."""

from __future__ import annotations

import re

_WS = re.compile(r"\s+")


def chunk_text_basic(
    text: str,
    *,
    chunk_chars: int = 750,
    overlap_chars: int = 150,
) -> list[str]:
    """Character-window chunker with overlap."""
    stripped = text.strip()
    if not stripped:
        return []
    normalized = _WS.sub(" ", stripped)
    if chunk_chars < 48:
        msg = "chunk_chars must be at least 48"
        raise ValueError(msg)
    if overlap_chars < 0 or overlap_chars >= chunk_chars:
        msg = "overlap_chars must be in [0, chunk_chars)"
        raise ValueError(msg)

    chunks: list[str] = []
    start = 0
    limit = len(normalized)
    while start < limit:
        end = min(start + chunk_chars, limit)
        piece = normalized[start:end].strip()
        if piece:
            chunks.append(piece)
        if end == limit:
            break
        start = max(end - overlap_chars, start + 1)
    return chunks
