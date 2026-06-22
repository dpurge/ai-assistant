"""Lazy module-level ``KnowledgeCorpus`` so agent and endpoints share one index.

Built from ``Settings`` on first call. Restores from
``settings.corpus_persist_dir`` when that directory contains a saved index.
"""

from __future__ import annotations

import logging
from threading import Lock

from app.config import Settings, get_settings
from app.knowledge.embeddings import build_embedder_from_settings
from app.knowledge.store import KnowledgeCorpus

logger = logging.getLogger(__name__)

_corpus: KnowledgeCorpus | None = None
_lock = Lock()


def get_corpus(settings: Settings | None = None) -> KnowledgeCorpus:
    """Return the process-wide corpus, building it on first call."""
    global _corpus
    if _corpus is not None:
        return _corpus
    with _lock:
        if _corpus is not None:
            return _corpus
        cfg = settings or get_settings()
        embedder = build_embedder_from_settings(cfg)
        corpus = KnowledgeCorpus(embedder=embedder)
        persist_dir = cfg.corpus_persist_dir
        if persist_dir is not None and persist_dir.exists():
            restored = corpus.load_from_disk(persist_dir)
            if restored:
                logger.info(
                    "Restored corpus from %s (%d chunks).",
                    persist_dir,
                    corpus.chunk_count,
                )
        _corpus = corpus
        return _corpus


def clear_corpus_cache() -> None:
    """Drop the cached corpus (tests)."""
    global _corpus
    with _lock:
        _corpus = None


def persist_if_configured(
    corpus: KnowledgeCorpus, settings: Settings | None = None
) -> None:
    cfg = settings or get_settings()
    if cfg.corpus_persist_dir is None:
        return
    corpus.save_to_disk(cfg.corpus_persist_dir)
