from __future__ import annotations

import json

from app.knowledge.embeddings import FakeEmbeddingBackend
from app.knowledge.store import KnowledgeCorpus
from app.tools.document_search_tool import make_document_search_tool


def _corpus_with_one_doc() -> KnowledgeCorpus:
    corpus = KnowledgeCorpus(embedder=FakeEmbeddingBackend(embedding_dim=16))
    corpus.ingest_text(
        doc_id="lesson-aspect",
        raw_text="Polish verbs use perfective and imperfective aspect. " * 40,
        chunk_chars=200,
        overlap_chars=40,
    )
    return corpus


def test_empty_query_short_circuits():
    tool = make_document_search_tool(_corpus_with_one_doc())
    payload = json.loads(tool("   "))
    assert payload == {"hits": [], "reason": "empty_query"}


def test_returns_hits_for_real_query():
    tool = make_document_search_tool(_corpus_with_one_doc())
    payload = json.loads(tool("aspect"))
    assert "hits" in payload
    assert payload["hits"]
    assert all(hit["document_id"] == "lesson-aspect" for hit in payload["hits"])


def test_top_k_is_bounded():
    tool = make_document_search_tool(_corpus_with_one_doc())
    payload = json.loads(tool("aspect", top_k=1000))
    assert len(payload["hits"]) <= 32


def test_top_k_floor_at_one():
    tool = make_document_search_tool(_corpus_with_one_doc())
    payload = json.loads(tool("aspect", top_k=0))
    assert len(payload["hits"]) >= 1
