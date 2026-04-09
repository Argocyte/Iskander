"""
persona_generator — Dynamic cooperative identity injection for agent prompts.

Takes a ``CoopProfile`` (collected during the First-Boot Constitutional
Dialogue) and produces a textual persona block that is interpolated into
``base_prompt.txt`` at the ``{PERSONA_BLOCK}`` placeholder.

This ensures every Iskander agent reflects the unique voice, jurisdiction,
and values of the cooperative it serves.
"""
from __future__ import annotations

from backend.agents.core import load_prompt
from backend.schemas.glass_box import CoopProfile

# ── Default placeholder when no profile has been set yet ──────────────────────

_DEFAULT_PERSONA: str = (
    "No cooperative profile loaded.  This node is running in development "
    "mode.  Constitutional values have not yet been ratified."
)

_DEFAULT_PRECEDENT: str = (
    "No democratic precedents available yet.  The cooperative has not "
    "recorded any binding human votes."
)


def generate_persona_block(profile: CoopProfile) -> str:
    """Render a cooperative-specific identity block from *profile*.

    Parameters
    ----------
    profile:
        The ``CoopProfile`` Pydantic model populated during the First-Boot
        Constitutional Dialogue (``POST /constitution/generate``).

    Returns
    -------
    str
        Multi-line persona description ready for prompt injection.
    """
    principles_list = "\n".join(
        f"  • {p}" for p in profile.ica_principles
    ) if profile.ica_principles else "  • (none specified)"

    members_list = ", ".join(profile.founding_members) if profile.founding_members else "(none listed)"

    return (
        f"You serve **{profile.coop_name}**, a democratic cooperative "
        f"incorporated in **{profile.jurisdiction}** under a "
        f"**{profile.legal_wrapper_type}** legal wrapper.\n\n"
        f"Mission statement:\n"
        f"  \"{profile.mission_statement}\"\n\n"
        f"Pay-ratio cap: **{profile.pay_ratio}:1** (Mondragon model).  No "
        f"internal payment may violate this ratio.\n\n"
        f"Founding members: {members_list}\n\n"
        f"Ratified ICA Cooperative Principles:\n{principles_list}"
    )


def inject_persona(
    base_prompt: str,
    profile: CoopProfile | None = None,
) -> str:
    """Replace ``{{PERSONA_BLOCK}}`` in *base_prompt* with a coop-specific block.

    Parameters
    ----------
    base_prompt:
        The raw text of ``base_prompt.txt`` (obtained via ``load_prompt()``).
    profile:
        Cooperative profile from First-Boot.  If ``None``, a neutral
        development-mode placeholder is used.

    Returns
    -------
    str
        Prompt with the persona placeholder substituted.
    """
    persona = (
        generate_persona_block(profile) if profile is not None
        else _DEFAULT_PERSONA
    )
    return base_prompt.replace("{PERSONA_BLOCK}", persona)


def inject_precedents(
    prompt: str,
    precedent_block: str | None = None,
) -> str:
    """Replace ``{{PRECEDENT_BLOCK}}`` in *prompt* with RAG-retrieved precedents.

    This is a thin helper used during Phase 11 integration.  Until the RAG
    pipeline is wired, the default placeholder text is used.

    Parameters
    ----------
    prompt:
        Prompt text (typically after ``inject_persona`` has already run).
    precedent_block:
        Formatted precedent text from ``backend.memory.precedent_retriever``.
        If ``None``, a neutral default is inserted.

    Returns
    -------
    str
        Prompt with the precedent placeholder substituted.
    """
    block = precedent_block if precedent_block is not None else _DEFAULT_PRECEDENT
    return prompt.replace("{PRECEDENT_BLOCK}", block)


def build_agent_prompt(
    profile: CoopProfile | None = None,
    precedent_block: str | None = None,
    agent_specific_suffix: str = "",
) -> str:
    """One-call convenience: load base prompt, inject persona + precedents.

    Parameters
    ----------
    profile:
        Cooperative profile (or ``None`` for dev mode).
    precedent_block:
        RAG precedent text (or ``None`` for default).
    agent_specific_suffix:
        Additional instructions appended after the base prompt (e.g. the
        agent-library-specific role prompt from ``prompt_secretary.txt``).

    Returns
    -------
    str
        Fully assembled system prompt ready to pass to ``ChatOllama``.
    """
    prompt = load_prompt("base_prompt.txt")
    prompt = inject_persona(prompt, profile)
    prompt = inject_precedents(prompt, precedent_block)
    if agent_specific_suffix:
        prompt += "\n\n" + agent_specific_suffix
    return prompt
