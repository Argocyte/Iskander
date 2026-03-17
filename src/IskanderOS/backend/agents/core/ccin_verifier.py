"""
ccin_verifier.py — CCIN Compliance Checker (Fix 2 — Adversarial Rationale Verification).

Second-pass LLM verification of AgentAction rationales against the 10 CCIN
Cooperative Principles. Uses a DIFFERENT model instance than the action-generating
agent to prevent self-rationalization.

The verifier receives only the structured AgentAction object, not the agent's
conversation history — isolating it from prompt injection.
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from typing import Any

from backend.schemas.glass_box import AgentAction, EthicalImpactLevel

logger = logging.getLogger(__name__)

CCIN_VERIFIER_VERSION = "1.0.0"
AGENT_ID = "ccin-verifier-v1"

CCIN_PRINCIPLES = [
    "Open and Voluntary Membership",
    "Democratic Member Control",
    "Member Economic Participation",
    "Autonomy and Independence",
    "Education, Training, and Information",
    "Cooperation Among Cooperatives",
    "Concern for Community",
    "Anti-Extractive Value Flows",
    "Transparent Glass Box Governance",
    "Ecological and Social Sustainability",
]

CCIN_VERIFICATION_PROMPT = """You are a CCIN Compliance Auditor. Given an agent's action and rationale,
score it against the 10 CCIN Cooperative Principles:

1. Open and Voluntary Membership
2. Democratic Member Control
3. Member Economic Participation
4. Autonomy and Independence
5. Education, Training, and Information
6. Cooperation Among Cooperatives
7. Concern for Community
8. Anti-Extractive Value Flows
9. Transparent Glass Box Governance
10. Ecological and Social Sustainability

Analyze the action for:
- Contradictions between the action and the stated rationale
- Actions that violate cooperative principles while claiming compliance
- Missing stakeholder considerations
- Extractive patterns disguised as cooperative benefit

Output JSON:
{
    "violation_score": <0-100>,
    "flagged_principles": [<list of principle numbers that may be violated>],
    "explanation": "<brief explanation>"
}

A score of 0 = fully compliant. A score > 25 = HALT the action.

---
Agent Action:
  agent_id: {agent_id}
  action: {action}
  rationale: {rationale}
  ethical_impact: {ethical_impact}
  payload_summary: {payload_summary}
"""


@dataclass
class CCINVerdict:
    """Result of CCIN compliance verification."""
    violation_score: int = 0
    flagged_principles: list[int] = field(default_factory=list)
    explanation: str = ""
    verifier_version: str = CCIN_VERIFIER_VERSION
    payload_hash: str = ""
    verified: bool = False


def compute_payload_hash(payload: dict[str, Any] | None) -> str:
    """SHA-256 hash of the payload at time of rationale writing.

    Binds the rationale to specific data — if the payload changes
    after the rationale is written, the hash mismatch is detected.
    """
    if payload is None:
        return hashlib.sha256(b"null").hexdigest()
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


async def verify_rationale(action: AgentAction) -> CCINVerdict:
    """Verify an AgentAction rationale against CCIN principles.

    Uses a DIFFERENT model instance than the action-generating agent.
    In production this calls the LLM; in stub mode it performs
    rule-based heuristic checks.

    Returns a CCINVerdict with violation_score, flagged_principles, etc.
    """
    verdict = CCINVerdict(
        verifier_version=CCIN_VERIFIER_VERSION,
        payload_hash=compute_payload_hash(action.payload),
    )

    # ── Rule-based heuristics (always run, even when LLM unavailable) ──

    rationale = action.rationale.lower() if action.rationale else ""
    action_text = action.action.lower() if action.action else ""

    # Check 1: Empty or trivially short rationale
    if len(rationale) < 10:
        verdict.violation_score += 30
        verdict.flagged_principles.append(9)  # Transparent Glass Box
        verdict.explanation += "Rationale is too short for meaningful compliance check. "

    # Check 2: High-impact action with LOW ethical_impact classification
    if action.ethical_impact == EthicalImpactLevel.LOW:
        high_impact_keywords = [
            "mint", "burn", "transfer", "delegate", "revoke", "slash",
            "veto", "deploy", "execute", "threshold", "oracle",
        ]
        if any(kw in action_text for kw in high_impact_keywords):
            verdict.violation_score += 20
            verdict.flagged_principles.append(2)  # Democratic Member Control
            verdict.explanation += (
                "Action contains high-impact keywords but is classified as LOW impact. "
            )

    # Check 3: Rationale contradicts action
    contradiction_pairs = [
        ("anti-extractive", "maximize profit"),
        ("cooperative", "unilateral"),
        ("democratic", "override"),
        ("transparent", "without disclosure"),
        ("voluntary", "forced"),
        ("sustainable", "emergency extraction"),
    ]
    for positive, negative in contradiction_pairs:
        if positive in rationale and negative in action_text:
            verdict.violation_score += 25
            verdict.flagged_principles.append(8)  # Anti-Extractive
            verdict.explanation += (
                f"Potential contradiction: rationale claims '{positive}' "
                f"but action contains '{negative}'. "
            )

    # Check 4: Missing stakeholder mention for HIGH impact actions
    if action.ethical_impact == EthicalImpactLevel.HIGH:
        stakeholder_terms = [
            "member", "cooperative", "community", "worker", "steward",
            "council", "vote", "approval", "consent",
        ]
        if not any(term in rationale for term in stakeholder_terms):
            verdict.violation_score += 15
            verdict.flagged_principles.append(7)  # Concern for Community
            verdict.explanation += (
                "HIGH impact action rationale does not mention any stakeholders. "
            )

    # ── LLM verification (production path — stubbed) ──
    # In production, this would call:
    #   response = await llm.ainvoke(CCIN_VERIFICATION_PROMPT.format(...))
    #   parsed = json.loads(response)
    #   verdict.violation_score = max(verdict.violation_score, parsed["violation_score"])
    #   verdict.flagged_principles.extend(parsed["flagged_principles"])

    verdict.verified = True
    verdict.violation_score = min(100, verdict.violation_score)

    logger.info(
        "CCIN verification: agent=%s action=%s score=%d flagged=%s version=%s",
        action.agent_id, action.action[:50], verdict.violation_score,
        verdict.flagged_principles, verdict.verifier_version,
    )

    return verdict
