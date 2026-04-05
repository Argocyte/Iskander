"""
Rule Extractor — Template-guided bylaw rule extraction.

STUB: The actual LLM extraction (OLMo integration) is deferred.
This module provides the graph node functions and the tagging logic.
"""
from __future__ import annotations

import logging
from typing import Any

from backend.schemas.glass_box import AgentAction, EthicalImpactLevel

logger = logging.getLogger(__name__)

AMBIGUITY_THRESHOLD = 0.6

from backend.agents.genesis.initializer_agent import _append_action, AGENT_ID  # noqa: E402


def extract_rules_from_bylaws(state: dict[str, Any]) -> dict[str, Any]:
    """STUB: passes through extracted_rules already in state."""
    if state.get("error"):
        return state

    rules = state.get("extracted_rules", [])

    return {
        **state,
        "boot_phase": "rules-extracted",
        "action_log": _append_action(
            state,
            "extract_rules_from_bylaws",
            f"Extracted {len(rules)} rule(s) from bylaws. STUB: actual LLM extraction deferred.",
            payload={"rule_count": len(rules)},
        ),
    }


def tag_ambiguous_rules(state: dict[str, Any]) -> dict[str, Any]:
    """Tag rules with confidence < 0.6 as Human-Judgment-Only."""
    if state.get("error"):
        return state

    rules = state.get("extracted_rules", [])
    ambiguous_ids: list[str] = []
    updated_rules: list[dict[str, Any]] = []

    for rule in rules:
        confidence = rule.get("confidence", 1.0)
        if confidence < AMBIGUITY_THRESHOLD:
            rule = {**rule, "is_ambiguous": True}
            ambiguous_ids.append(rule.get("rule_id", "unknown"))
        updated_rules.append(rule)

    return {
        **state,
        "extracted_rules": updated_rules,
        "ambiguous_rules": ambiguous_ids,
        "boot_phase": "ambiguity-tagged",
        "action_log": _append_action(
            state,
            "tag_ambiguous_rules",
            f"Tagged {len(ambiguous_ids)} rule(s) as Human-Judgment-Only "
            f"(confidence < {AMBIGUITY_THRESHOLD}).",
            payload={
                "ambiguous_count": len(ambiguous_ids),
                "ambiguous_rule_ids": ambiguous_ids,
                "threshold": AMBIGUITY_THRESHOLD,
            },
        ),
    }
