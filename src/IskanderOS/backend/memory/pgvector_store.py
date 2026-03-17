"""
pgvector_store — Vector store integration for democratic precedent memory.

Uses PostgreSQL + pgvector extension via LangChain's PGVector class.
All democratic decisions (HITL votes, meeting consensus, AJD approvals)
are embedded and stored here so agents can query binding precedent.

Agents do NOT call this module directly — routers call ``store_precedent()``
after HITL decisions complete, maintaining the agents-don't-write-to-DB rule.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from langchain_core.documents import Document

from backend.config import settings

logger = logging.getLogger(__name__)

# ── Lazy singletons (avoid import-time DB connections) ────────────────────────

_embeddings = None
_vector_store = None


def get_embeddings():
    """Return a configured OllamaEmbeddings instance (singleton)."""
    global _embeddings
    if _embeddings is None:
        try:
            from langchain_ollama import OllamaEmbeddings

            _embeddings = OllamaEmbeddings(
                base_url=settings.ollama_base_url,
                model=settings.embedding_model,
            )
        except Exception as exc:
            logger.warning(
                "OllamaEmbeddings unavailable (%s). "
                "RAG precedent retrieval will be disabled.",
                exc,
            )
            _embeddings = None
    return _embeddings


def get_vector_store():
    """Return a configured PGVector instance (singleton).

    Uses the existing Iskander PostgreSQL database with the pgvector
    extension enabled.  The ``democratic_precedents`` table and ivfflat
    index are created by ``infra/init.sql``.
    """
    global _vector_store
    if _vector_store is None:
        embeddings = get_embeddings()
        if embeddings is None:
            return None
        try:
            from langchain_postgres import PGVector

            # Convert async URL to sync for langchain-postgres.
            sync_url = settings.database_url.replace(
                "postgresql+asyncpg://", "postgresql+psycopg://"
            )
            _vector_store = PGVector(
                embeddings=embeddings,
                collection_name="democratic_precedents",
                connection=sync_url,
                use_jsonb=True,
            )
        except Exception as exc:
            logger.warning(
                "PGVector store unavailable (%s). "
                "RAG precedent retrieval will be disabled.",
                exc,
            )
            _vector_store = None
    return _vector_store


# ── Public API ────────────────────────────────────────────────────────────────


def store_precedent(
    source_agent: str,
    decision_type: str,
    original_text: str,
    vote_result: str,
    metadata: dict[str, Any] | None = None,
) -> UUID | None:
    """Embed and store a democratic decision as binding precedent.

    Parameters
    ----------
    source_agent:
        Agent that produced the decision context (e.g. ``"governance-agent-v1"``).
    decision_type:
        Category: ``"governance_vote"``, ``"meeting_consensus"``, ``"ajd_approval"``.
    original_text:
        Human-readable description of the decision.
    vote_result:
        Outcome: ``"approved"``, ``"rejected"``, ``"passed"``, ``"failed"``.
    metadata:
        Additional structured data (vote tallies, thread IDs, etc.).

    Returns
    -------
    UUID | None
        Row ID on success, or ``None`` if the vector store is unavailable.
    """
    store = get_vector_store()
    if store is None:
        logger.warning("Cannot store precedent — vector store unavailable.")
        return None

    doc_id = uuid4()
    meta = {
        "id": str(doc_id),
        "source_agent": source_agent,
        "decision_type": decision_type,
        "vote_result": vote_result,
        "created_at": datetime.now(timezone.utc).isoformat(),
        **(metadata or {}),
    }

    doc = Document(
        page_content=original_text,
        metadata=meta,
    )

    try:
        store.add_documents([doc], ids=[str(doc_id)])
        logger.info(
            "Precedent stored: %s [%s] %s",
            decision_type,
            vote_result,
            original_text[:80],
        )
        return doc_id
    except Exception as exc:
        logger.error("Failed to store precedent: %s", exc)
        return None


def search_precedents(
    query: str,
    k: int | None = None,
) -> list[Document]:
    """Similarity-search for relevant past democratic decisions.

    Parameters
    ----------
    query:
        Natural-language description of the current decision context.
    k:
        Number of results to return (defaults to ``settings.rag_top_k``).

    Returns
    -------
    list[Document]
        Matching precedent documents, each with ``.page_content`` (the
        original decision text) and ``.metadata`` (structured fields).
    """
    store = get_vector_store()
    if store is None:
        return []

    top_k = k if k is not None else settings.rag_top_k

    try:
        return store.similarity_search(query, k=top_k)
    except Exception as exc:
        logger.warning("Precedent search failed: %s", exc)
        return []
