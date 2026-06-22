from __future__ import annotations

from pathlib import Path

from app.knowledge.embeddings import FakeEmbeddingBackend
from app.knowledge.store import KnowledgeCorpus


def _make_corpus() -> KnowledgeCorpus:
    return KnowledgeCorpus(embedder=FakeEmbeddingBackend(embedding_dim=16))


def test_ingest_text_round_trip():
    corpus = _make_corpus()
    added = corpus.ingest_text(
        doc_id="lesson-1",
        raw_text=("Polish verbs have perfective and imperfective aspects. " * 20),
        chunk_chars=200,
        overlap_chars=40,
    )
    assert added >= 1
    assert corpus.chunk_count == added

    hits = corpus.search_chunks(query="Polish verbs aspect", top_k=3)
    assert hits
    assert all(hit["document_id"] == "lesson-1" for hit in hits)
    assert all("relevance_approx" in hit and "distance_l2" in hit for hit in hits)


def test_empty_query_returns_no_hits():
    corpus = _make_corpus()
    corpus.ingest_text(doc_id="doc-1", raw_text="some content " * 50)
    assert corpus.search_chunks(query="   ", top_k=5) == []


def test_search_on_empty_corpus_returns_empty():
    corpus = _make_corpus()
    assert corpus.search_chunks(query="anything", top_k=3) == []


def test_ingest_many_strings():
    corpus = _make_corpus()
    total = corpus.ingest_many_strings(
        ["one " * 100, "two " * 100, "three " * 100],
        chunk_chars=200,
        overlap_chars=40,
    )
    assert total >= 3
    assert corpus.chunk_count == total


def test_persistence_round_trip(tmp_path: Path):
    corpus = _make_corpus()
    corpus.ingest_text(
        doc_id="grammar-1",
        raw_text="Aspect in Polish verbs is essential for learners. " * 30,
        chunk_chars=200,
        overlap_chars=40,
    )
    chunk_count_before = corpus.chunk_count

    target = tmp_path / "corpus"
    corpus.save_to_disk(target)
    assert (target / "index.faiss").exists()
    assert (target / "chunks.jsonl").exists()

    reloaded = _make_corpus()
    assert reloaded.load_from_disk(target) is True
    assert reloaded.chunk_count == chunk_count_before
    hits = reloaded.search_chunks(query="Polish aspect", top_k=2)
    assert hits


def test_load_from_disk_returns_false_when_missing(tmp_path: Path):
    corpus = _make_corpus()
    assert corpus.load_from_disk(tmp_path / "nope") is False
