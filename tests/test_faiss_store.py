from __future__ import annotations

import numpy as np
import pytest

from app.rag.faiss_store import FaissFlatIndex


def test_add_and_search_round_trip():
    idx = FaissFlatIndex(dimension=8)
    vectors = np.eye(3, 8, dtype=np.float32)
    idx.add_vectors(vectors, payloads=["a", "b", "c"])
    assert len(idx) == 3

    query = np.zeros(8, dtype=np.float32)
    query[0] = 1.0
    hits = idx.search(query, k=2)
    assert len(hits) == 2
    assert hits[0][1] == "a"
    assert hits[0][0].distance == pytest.approx(0.0)


def test_dimension_mismatch_raises():
    idx = FaissFlatIndex(dimension=8)
    with pytest.raises(ValueError):
        idx.add_vectors(np.zeros((1, 9), dtype=np.float32), payloads=["x"])


def test_k_clamps_to_stored_count():
    idx = FaissFlatIndex(dimension=8)
    idx.add_vectors(np.eye(2, 8, dtype=np.float32), payloads=["a", "b"])
    query = np.zeros(8, dtype=np.float32)
    query[0] = 1.0
    hits = idx.search(query, k=10)
    assert len(hits) == 2


def test_rejects_invalid_construction():
    with pytest.raises(ValueError):
        FaissFlatIndex(dimension=2)


def test_rejects_invalid_query_shape():
    idx = FaissFlatIndex(dimension=8)
    idx.add_vectors(np.eye(1, 8, dtype=np.float32), payloads=["a"])
    with pytest.raises(ValueError):
        idx.search(np.zeros(7, dtype=np.float32), k=1)
    with pytest.raises(ValueError):
        idx.search(np.zeros(8, dtype=np.float32), k=0)


def test_payload_count_must_match_rows():
    idx = FaissFlatIndex(dimension=8)
    with pytest.raises(ValueError):
        idx.add_vectors(np.eye(2, 8, dtype=np.float32), payloads=["a"])
