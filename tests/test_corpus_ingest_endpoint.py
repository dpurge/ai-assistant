from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("CORPUS_PERSIST_DIR", str(tmp_path / "corpus"))
    # main is imported lazily so the env var above wins; cache fixtures in
    # conftest already cleared get_settings + corpus singleton before the test.
    import main

    return TestClient(main.app)


def test_ingest_adds_chunks(client: TestClient):
    response = client.post(
        "/corpus/ingest",
        json={
            "doc_id": "grammar-1",
            "text": "Polish verbs have perfective and imperfective aspects. " * 30,
            "chunk_chars": 200,
            "overlap_chars": 40,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["doc_id"] == "grammar-1"
    assert body["chunks_added"] >= 1
    assert body["total_chunks"] == body["chunks_added"]


def test_second_ingest_accumulates(client: TestClient):
    first = client.post(
        "/corpus/ingest",
        json={"doc_id": "a", "text": "alpha " * 200, "chunk_chars": 200, "overlap_chars": 40},
    ).json()
    second = client.post(
        "/corpus/ingest",
        json={"doc_id": "b", "text": "beta " * 200, "chunk_chars": 200, "overlap_chars": 40},
    ).json()
    assert second["total_chunks"] == first["total_chunks"] + second["chunks_added"]


def test_persistence_dir_is_written(client: TestClient, tmp_path: Path):
    client.post(
        "/corpus/ingest",
        json={"doc_id": "p", "text": "persist " * 200, "chunk_chars": 200, "overlap_chars": 40},
    )
    persist_dir = tmp_path / "corpus"
    assert (persist_dir / "index.faiss").exists()
    assert (persist_dir / "chunks.jsonl").exists()


def test_blank_text_is_rejected(client: TestClient):
    response = client.post("/corpus/ingest", json={"doc_id": None, "text": ""})
    assert response.status_code == 422  # Pydantic min_length=1


def test_invalid_chunk_size_returns_400(client: TestClient):
    response = client.post(
        "/corpus/ingest",
        json={"doc_id": "x", "text": "some text", "chunk_chars": 10},
    )
    assert response.status_code == 422
