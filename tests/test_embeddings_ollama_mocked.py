from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from app.knowledge.embeddings import OllamaEmbeddingBackend


class _FakeResponse:
    def __init__(self, payload: dict[str, Any], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeClient:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload
        self.last_url: str | None = None
        self.last_json: dict[str, Any] | None = None

    def __enter__(self) -> _FakeClient:
        return self

    def __exit__(self, *exc: Any) -> None:
        return None

    def post(self, url: str, json: dict[str, Any]) -> _FakeResponse:
        self.last_url = url
        self.last_json = json
        return _FakeResponse(self._payload)


def test_ollama_backend_request_and_parse(monkeypatch: pytest.MonkeyPatch):
    fake_client = _FakeClient({"embeddings": [[1.0] * 8, [0.5] * 8]})
    monkeypatch.setattr("app.knowledge.embeddings.httpx.Client", lambda **_: fake_client)

    backend = OllamaEmbeddingBackend(
        base_url="http://localhost:11434",
        model_name="nomic-embed-text",
        embedding_dim=8,
    )
    out = backend.embed_texts(["hello", "world"])

    assert out.shape == (2, 8)
    assert out.dtype == np.float32
    assert fake_client.last_url == "http://localhost:11434/api/embed"
    assert fake_client.last_json == {"model": "nomic-embed-text", "input": ["hello", "world"]}


def test_ollama_backend_empty_input_short_circuits(monkeypatch: pytest.MonkeyPatch):
    def _explode(**_: Any):
        raise AssertionError("httpx.Client should not be constructed for empty input")

    monkeypatch.setattr("app.knowledge.embeddings.httpx.Client", _explode)
    backend = OllamaEmbeddingBackend(
        base_url="http://localhost:11434",
        model_name="nomic-embed-text",
        embedding_dim=8,
    )
    out = backend.embed_texts([])
    assert out.shape == (0, 8)


def test_ollama_backend_raises_when_embedding_count_mismatch(monkeypatch: pytest.MonkeyPatch):
    fake_client = _FakeClient({"embeddings": [[1.0] * 8]})
    monkeypatch.setattr("app.knowledge.embeddings.httpx.Client", lambda **_: fake_client)

    backend = OllamaEmbeddingBackend(
        base_url="http://localhost:11434",
        model_name="nomic-embed-text",
        embedding_dim=8,
    )
    with pytest.raises(RuntimeError, match="ollama pull nomic-embed-text"):
        backend.embed_texts(["a", "b"])


def test_ollama_backend_raises_on_dim_mismatch(monkeypatch: pytest.MonkeyPatch):
    fake_client = _FakeClient({"embeddings": [[1.0] * 16]})
    monkeypatch.setattr("app.knowledge.embeddings.httpx.Client", lambda **_: fake_client)

    backend = OllamaEmbeddingBackend(
        base_url="http://localhost:11434",
        model_name="nomic-embed-text",
        embedding_dim=8,
    )
    with pytest.raises(ValueError, match="EMBEDDING_DIMENSION"):
        backend.embed_texts(["a"])
