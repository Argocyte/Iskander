"""
precedent_retriever — Format RAG-retrieved democratic precedents for prompt injection.

Queries the pgvector store for the most relevant past democratic decisions
and formats them into a text block that replaces ``{PRECEDENT_BLOCK}`` in
the agent's system prompt.

Usage (from any agent's LLM-calling node)::

    from backend.memory.precedent_retriever import format_precedent_block
    from backend.agents.core.persona_generator import inject_precedents

    block = format_precedent_block("Should we fund the documentation project?")
    prompt = inject_precedents(base_prompt, block)
"""
from __future__ import annotations

import logging

from backend.memory.pgvector_store import search_precedents

logger = logging.getLogger(__name__)

_NO_PRECEDENTS = (
    "No democratic precedents available yet.  The cooperative has not "
    "recorded any binding human votes."
)


def format_precedent_block(query: str, k: int | None = None) -> str:
    """Query the vector store and format results as a prompt-injectable block.

    Parameters
    ----------
    query:
        Natural-language context for the current agent decision.
    k:
        Override for number of precedents to retrieve.

    Returns
    -------
    str
        Formatted text block ready for ``{PRECEDENT_BLOCK}`` substitution.
        If no precedents are found, returns a neutral fallback message.
    """
    docs = search_precedents(query, k=k)

    if not docs:
        return _NO_PRECEDENTS

    lines: list[str] = [
        "The following past democratic decisions are BINDING PRECEDENT.",
        "You MUST NOT recommend actions that contradict these decisions.\n",
    ]

    for i, doc in enumerate(docs, 1):
        meta = doc.metadata or {}
        date = meta.get("created_at", "unknown date")
        dtype = meta.get("decision_type", "DECISION").upper().replace("_", " ")
        result = meta.get("vote_result", "unknown").upper()
        text = doc.page_content.strip()

        lines.append(f"  {i}. [{date}] {dtype} — {result}")
        lines.append(f"     \"{text}\"")
        lines.append("")

    return "\n".join(lines)
