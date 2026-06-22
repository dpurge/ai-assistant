"""Text embedding backends.

Two production-shaped implementations:

- ``FakeEmbeddingBackend`` — deterministic hash-seeded vectors. Useless for
  retrieval quality, but enables unit tests and CI without network calls.
- ``OllamaEmbeddingBackend`` — POSTs to Ollama's ``/api/embed`` endpoint
  (batched). Requires the embedding model to be pulled with
  ``ollama pull <model_name>`` ahead of time.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Protocol

import httpx
import numpy as np

from app.config import Settings

logger = logging.getLogger(__name__)


class EmbeddingBackend(Protocol):
    """Embeds batches of trimmed strings."""

    embedding_dim: int

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        """Return float32 ndarray shaped (batch, embedding_dim)."""
        ...


class FakeEmbeddingBackend:
    """Deterministic, offline-friendly embeddings for CI (not semantically faithful)."""

    def __init__(self, embedding_dim: int = 32) -> None:
        if embedding_dim < 8:
            msg = "embedding_dim must be >= 8"
            raise ValueError(msg)
        self.embedding_dim = embedding_dim

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.embedding_dim), dtype=np.float32)
        vectors = np.zeros((len(texts), self.embedding_dim), dtype=np.float32)
        for i, txt in enumerate(texts):
            seed = int(hashlib.sha256(txt.encode()).hexdigest(), 16) % (2**32)
            rng = np.random.default_rng(seed)
            v = rng.standard_normal(self.embedding_dim, dtype=np.float32)
            norm = np.linalg.norm(v)
            vectors[i] = v / norm if norm > 1e-6 else v
        return vectors


class OllamaEmbeddingBackend:
    """Embeddings via Ollama's ``/api/embed`` (batched).

    Requires the model to be pulled locally first, e.g.::

        ollama pull nomic-embed-text
    """

    def __init__(
        self,
        *,
        base_url: str,
        model_name: str,
        embedding_dim: int,
        timeout_seconds: float = 30.0,
    ) -> None:
        if embedding_dim < 8:
            raise ValueError("embedding_dim must be >= 8")
        self._base_url = base_url.rstrip("/")
        self._model = model_name
        self.embedding_dim = embedding_dim
        self._timeout = timeout_seconds

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.embedding_dim), dtype=np.float32)
        url = f"{self._base_url}/api/embed"
        payload = {"model": self._model, "input": list(texts)}
        with httpx.Client(timeout=self._timeout) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

        raw = data.get("embeddings")
        if not isinstance(raw, list) or len(raw) != len(texts):
            msg = (
                f"Ollama returned {len(raw) if isinstance(raw, list) else 'no'} embeddings "
                f"for {len(texts)} inputs (model={self._model!r}). "
                f"Run `ollama pull {self._model}` and confirm the server is reachable at "
                f"{self._base_url}."
            )
            raise RuntimeError(msg)

        matrix = np.asarray(raw, dtype=np.float32)
        if matrix.ndim != 2 or matrix.shape[1] != self.embedding_dim:
            msg = (
                f"Ollama embedding dim {matrix.shape[-1]} != configured {self.embedding_dim}. "
                f"Adjust EMBEDDING_DIMENSION or change EMBEDDING_MODEL (current: {self._model!r})."
            )
            raise ValueError(msg)
        return matrix


def build_embedder_from_settings(
    settings: Settings,
    *,
    offline: bool | None = None,
) -> EmbeddingBackend:
    """Construct the embedding backend chosen by settings.

    ``offline`` overrides ``settings.embedding_use_fake`` when provided; ``None`` lets
    the setting decide.
    """
    use_fake = settings.embedding_use_fake if offline is None else offline
    if use_fake:
        return FakeEmbeddingBackend(settings.embedding_dimension)
    return OllamaEmbeddingBackend(
        base_url=settings.ollama_api_base,
        model_name=settings.embedding_model,
        embedding_dim=settings.embedding_dimension,
    )
