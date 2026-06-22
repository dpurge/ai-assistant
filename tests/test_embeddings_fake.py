from __future__ import annotations

import numpy as np
import pytest

from app.knowledge.embeddings import FakeEmbeddingBackend


def test_fake_backend_is_deterministic():
    backend = FakeEmbeddingBackend(embedding_dim=16)
    a = backend.embed_texts(["hello"])
    b = backend.embed_texts(["hello"])
    assert np.array_equal(a, b)


def test_fake_backend_dim_shape():
    backend = FakeEmbeddingBackend(embedding_dim=32)
    out = backend.embed_texts(["one", "two", "three"])
    assert out.shape == (3, 32)
    assert out.dtype == np.float32


def test_fake_backend_unit_vectors():
    backend = FakeEmbeddingBackend(embedding_dim=16)
    out = backend.embed_texts(["text"])
    norm = float(np.linalg.norm(out[0]))
    assert norm == pytest.approx(1.0, abs=1e-5)


def test_fake_backend_empty_input():
    backend = FakeEmbeddingBackend(embedding_dim=16)
    out = backend.embed_texts([])
    assert out.shape == (0, 16)


def test_fake_backend_rejects_tiny_dim():
    with pytest.raises(ValueError):
        FakeEmbeddingBackend(embedding_dim=4)
