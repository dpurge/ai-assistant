"""FAISS-backed corpus with chunk metadata and optional disk persistence."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import faiss  # type: ignore[import-untyped]
import numpy as np

from app.knowledge.chunking import chunk_text_basic
from app.knowledge.embeddings import EmbeddingBackend, FakeEmbeddingBackend
from app.rag.faiss_store import FaissFlatIndex


@dataclass(frozen=True, slots=True)
class ChunkRecord:
    chunk_id: str
    doc_id: str
    text: str


_INDEX_FILE = "index.faiss"
_CHUNKS_FILE = "chunks.jsonl"
_ORDER_FILE = "chunk_order.json"


class KnowledgeCorpus:
    """Ingest raw documents → chunks → embeddings → FAISS (thread-safe index)."""

    __slots__ = ("_chunk_order", "_chunks", "_embedder", "_index")

    def __init__(self, embedder: EmbeddingBackend | None = None) -> None:
        self._embedder: EmbeddingBackend = embedder or FakeEmbeddingBackend()
        self._index: FaissFlatIndex | None = None
        self._chunks: dict[str, ChunkRecord] = {}
        self._chunk_order: list[str] = []

    def _ensure_index_dim(self, dim: int) -> None:
        if self._index is None:
            self._index = FaissFlatIndex(dim)

    @staticmethod
    def _l2_normalize_rows(matrix: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms = np.clip(norms, 1e-12, None)
        out = matrix / norms.astype(np.float32)
        return out.astype(np.float32)

    @staticmethod
    def _l2_normalize_vector(vector: np.ndarray) -> np.ndarray:
        norm = np.linalg.norm(vector)
        if norm <= 1e-12:
            return vector.astype(np.float32)
        return (vector / norm).astype(np.float32)

    @property
    def chunk_count(self) -> int:
        return len(self._chunks)

    @property
    def embedding_dim(self) -> int:
        return self._embedder.embedding_dim

    def ingest_text(
        self,
        *,
        doc_id: str | None,
        raw_text: str,
        chunk_chars: int = 750,
        overlap_chars: int = 150,
    ) -> int:
        """Chunk + embed ``raw_text``. Returns the number of chunks added."""
        did = doc_id or f"doc-{uuid4()}"
        parts = chunk_text_basic(raw_text, chunk_chars=chunk_chars, overlap_chars=overlap_chars)
        if not parts:
            return 0
        matrix = self._embedder.embed_texts(parts)
        rows, cols = matrix.shape
        self._ensure_index_dim(cols)
        if rows != len(parts):
            raise RuntimeError("embedder rows mismatch")

        payloads: list[str] = []
        for offset, snippet in enumerate(parts):
            cid = f"{did}::chunk-{offset}"
            self._chunks[cid] = ChunkRecord(chunk_id=cid, doc_id=did, text=snippet)
            self._chunk_order.append(cid)
            payloads.append(cid)

        assert self._index is not None
        matrix = self._l2_normalize_rows(matrix)
        self._index.add_vectors(matrix, payloads=payloads)
        return rows

    def ingest_many_strings(
        self,
        payloads: list[str],
        *,
        doc_prefix: str = "memo",
        chunk_chars: int = 750,
        overlap_chars: int = 150,
    ) -> int:
        total = 0
        for i, blob in enumerate(payloads):
            total += self.ingest_text(
                doc_id=f"{doc_prefix}-{i}",
                raw_text=blob,
                chunk_chars=chunk_chars,
                overlap_chars=overlap_chars,
            )
        return total

    def search_chunks(
        self,
        *,
        query: str,
        top_k: int = 6,
    ) -> list[dict[str, str | float]]:
        """Retrieve chunks with heuristic relevance derived from Euclidean distance."""
        if self._index is None:
            return []
        trimmed = query.strip()
        if not trimmed:
            return []
        vectors = self._embedder.embed_texts([trimmed])
        if vectors.size == 0:
            return []

        vector = self._l2_normalize_vector(vectors[0])
        usable = len(self._index)
        hits = self._index.search(vector, k=min(top_k, max(usable, 1)))

        formatted: list[dict[str, str | float]] = []
        for hit, cid in hits:
            rec = self._chunks.get(cid)
            if rec is None:
                continue
            distance = hit.distance
            score = float(1.0 / (1.0 + distance))
            formatted.append(
                {
                    "chunk_id": rec.chunk_id,
                    "document_id": rec.doc_id,
                    "snippet": rec.text[:2000],
                    "relevance_approx": score,
                    "distance_l2": float(distance),
                },
            )
        return formatted[:top_k]

    def save_to_disk(self, target_dir: Path) -> None:
        """Atomically write the FAISS index and chunk metadata to ``target_dir``."""
        if self._index is None or not self._chunks:
            return
        target_dir = Path(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        index_path = target_dir / _INDEX_FILE
        tmp_index = target_dir / f"{_INDEX_FILE}.tmp"
        faiss.write_index(self._index._index, str(tmp_index))  # noqa: SLF001
        os.replace(tmp_index, index_path)

        chunks_tmp = target_dir / f"{_CHUNKS_FILE}.tmp"
        with chunks_tmp.open("w", encoding="utf-8") as fh:
            for rec in self._chunks.values():
                fh.write(
                    json.dumps(
                        {"chunk_id": rec.chunk_id, "doc_id": rec.doc_id, "text": rec.text},
                        ensure_ascii=False,
                    )
                    + "\n"
                )
        os.replace(chunks_tmp, target_dir / _CHUNKS_FILE)

        order_tmp = target_dir / f"{_ORDER_FILE}.tmp"
        order_tmp.write_text(json.dumps(self._chunk_order), encoding="utf-8")
        os.replace(order_tmp, target_dir / _ORDER_FILE)

    def load_from_disk(self, source_dir: Path) -> bool:
        """Load index + chunk metadata. Returns True iff state was restored."""
        source_dir = Path(source_dir)
        index_path = source_dir / _INDEX_FILE
        chunks_path = source_dir / _CHUNKS_FILE
        order_path = source_dir / _ORDER_FILE
        if not (index_path.exists() and chunks_path.exists() and order_path.exists()):
            return False

        chunks: dict[str, ChunkRecord] = {}
        with chunks_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                chunks[data["chunk_id"]] = ChunkRecord(
                    chunk_id=data["chunk_id"],
                    doc_id=data["doc_id"],
                    text=data["text"],
                )
        order = json.loads(order_path.read_text(encoding="utf-8"))

        raw_index = faiss.read_index(str(index_path))
        dim = int(raw_index.d)
        flat = FaissFlatIndex(dim)
        flat._index = raw_index  # noqa: SLF001
        flat._stored = list(order)  # noqa: SLF001

        self._index = flat
        self._chunks = chunks
        self._chunk_order = list(order)
        return True
