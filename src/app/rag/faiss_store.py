"""Lightweight FAISS L2 wrapper for deterministic in-process RAG."""

from __future__ import annotations

import threading
from dataclasses import dataclass

import faiss  # type: ignore[import-untyped]
import numpy as np


@dataclass(frozen=True, slots=True)
class SearchHit:
    index: int
    distance: float


class FaissFlatIndex:
    """Thread-safe incremental index storing float32 embeddings with L2 distance."""

    __slots__ = ("_dimension", "_index", "_lock", "_stored")

    def __init__(self, dimension: int) -> None:
        if dimension < 8:
            msg = "dimension must be >= 8"
            raise ValueError(msg)
        self._dimension = dimension
        self._index = faiss.IndexFlatL2(dimension)
        self._lock = threading.Lock()
        self._stored: list[str | None] = []

    @property
    def dimension(self) -> int:
        return self._dimension

    def __len__(self) -> int:
        return int(self._index.ntotal)

    def add_vectors(self, vectors: np.ndarray, payloads: list[str] | tuple[str, ...]) -> None:
        """Add row-wise vectors shaped (n, dimension) paired with payloads (chunk ids)."""
        if vectors.ndim != 2:
            raise ValueError("vectors must be 2D")
        rows, cols = vectors.shape
        if cols != self._dimension:
            msg = f"expected dimension {self._dimension}, got {cols}"
            raise ValueError(msg)
        if len(payloads) != rows:
            msg = "payloads length must equal number of rows"
            raise ValueError(msg)
        arr = vectors.astype(np.float32, copy=False)
        texts = list(payloads)
        with self._lock:
            self._index.add(arr)
            self._stored.extend(texts)

    def search(self, vector: np.ndarray, k: int = 5) -> list[tuple[SearchHit, str]]:
        """Return up to ``k`` closest payloads by ascending distance."""
        if k < 1:
            raise ValueError("k must be >= 1")
        if vector.shape != (self._dimension,):
            raise ValueError("vector shape must equal (dimension,)")
        q = vector.astype(np.float32, copy=False).reshape(1, -1)
        with self._lock:
            distances, indexes = self._index.search(q, min(k, max(len(self._stored), 1)))
            stored = tuple(self._stored)
        hits: list[tuple[SearchHit, str]] = []
        for dist, idx in zip(distances[0], indexes[0], strict=False):
            if idx < 0 or idx >= len(stored):
                continue
            payload = stored[idx]
            if payload is None:
                continue
            hits.append((SearchHit(index=int(idx), distance=float(dist)), payload))
        return hits[:k]
