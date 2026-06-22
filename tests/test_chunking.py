from __future__ import annotations

import pytest

from app.knowledge.chunking import chunk_text_basic


def test_empty_text_returns_no_chunks():
    assert chunk_text_basic("") == []
    assert chunk_text_basic("   \n\t  ") == []


def test_short_text_fits_in_one_chunk():
    chunks = chunk_text_basic("hello world", chunk_chars=750, overlap_chars=150)
    assert chunks == ["hello world"]


def test_whitespace_is_normalized():
    chunks = chunk_text_basic("a\n\nb\t  c", chunk_chars=750, overlap_chars=0)
    assert chunks == ["a b c"]


def test_long_text_is_split_with_overlap():
    text = ("abcdefgh" * 200).strip()  # 1600 chars
    chunks = chunk_text_basic(text, chunk_chars=500, overlap_chars=100)
    assert len(chunks) >= 3
    # Each non-last chunk should be at most chunk_chars long.
    for piece in chunks[:-1]:
        assert len(piece) <= 500
    # Adjacent chunks should share a 100-char tail/head when overlap is configured.
    for i in range(len(chunks) - 1):
        tail = chunks[i][-100:]
        head = chunks[i + 1][:100]
        assert tail == head


def test_rejects_too_small_chunk_size():
    with pytest.raises(ValueError):
        chunk_text_basic("text", chunk_chars=10)


def test_rejects_overlap_at_or_above_chunk_size():
    with pytest.raises(ValueError):
        chunk_text_basic("text", chunk_chars=100, overlap_chars=100)
    with pytest.raises(ValueError):
        chunk_text_basic("text", chunk_chars=100, overlap_chars=-1)
