"""ADK-compatible document search closure backed by ``KnowledgeCorpus``."""

from __future__ import annotations

import json

from app.knowledge.store import KnowledgeCorpus


def make_document_search_tool(corpus: KnowledgeCorpus):
    """Return a plain callable ADK wraps as ``FunctionTool``."""

    def search_private_knowledge(retrieval_question: str, top_k: int = 6) -> str:
        """Search the user's private corpus and return compact JSON snippets."""
        trimmed = retrieval_question.strip()
        if not trimmed:
            return json.dumps({"hits": [], "reason": "empty_query"}, ensure_ascii=False)
        bounded = max(1, min(int(top_k), 32))
        hits = corpus.search_chunks(query=trimmed, top_k=bounded)
        return json.dumps({"hits": hits}, ensure_ascii=False)

    return search_private_knowledge
