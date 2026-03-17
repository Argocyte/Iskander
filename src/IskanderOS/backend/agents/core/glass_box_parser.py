"""
glass_box_parser — Strict PydanticOutputParser for the Glass Box Protocol.

Forces local LLM responses into the canonical Glass Box JSON schema.
Retries up to ``MAX_RETRIES`` times with corrective prompts; after exhaustion
the parser yields control to a human operator and logs the failure as a HIGH-
impact AgentAction in the audit ledger.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from langchain.output_parsers import PydanticOutputParser
from langchain_ollama import ChatOllama
from pydantic import BaseModel, Field

from backend.schemas.glass_box import AgentAction, EthicalImpactLevel

logger = logging.getLogger(__name__)

MAX_RETRIES: int = 3

# ── Canonical output schema ──────────────────────────────────────────────────


class GlassBoxOutput(BaseModel):
    """Validated output envelope that every Iskander agent must produce.

    This schema is enforced by the ``GlassBoxParser`` at the boundary between
    the LLM and the application layer.  Any response that does not conform is
    retried with a corrective prompt.
    """

    action: str = Field(
        ...,
        description="Short imperative description of the action to take.",
    )
    rationale: str = Field(
        ...,
        description=(
            "Why the agent chose this action — citing bylaws, precedent, "
            "or cooperative principles where applicable."
        ),
    )
    ethical_impact_score: int = Field(
        ...,
        ge=1,
        le=10,
        description="Ethical impact severity (1 = read-only … 10 = constitutional).",
    )
    requires_human_token: bool = Field(
        ...,
        description=(
            "True if the action requires cryptographic human-in-the-loop "
            "approval before execution."
        ),
    )


# ── Corrective prompt sent on parse failure ───────────────────────────────────

_CORRECTION_TEMPLATE: str = (
    "Your previous response was NOT valid Glass Box JSON.  "
    "Error: {error}\n\n"
    "Respond ONLY with a single JSON object — no markdown fences, no "
    "commentary — matching this exact schema:\n\n"
    "{format_instructions}\n\n"
    "Original request context (do NOT change the substance of your answer, "
    "only fix the format):\n{original_input}"
)

# ── Parser class ──────────────────────────────────────────────────────────────


class GlassBoxParser:
    """Parse & validate LLM output against the Glass Box Protocol.

    Wraps LangChain's ``PydanticOutputParser`` and adds:
    * Up to ``MAX_RETRIES`` corrective re-prompts on schema violation.
    * A human-yield ``AgentAction`` after exhaustion, suitable for logging to
      the ``agent_actions`` audit table.

    Usage::

        parser = GlassBoxParser()

        # Append format instructions to your system/human prompt:
        prompt += "\\n" + parser.get_format_instructions()

        # After LLM call:
        result = parser.parse_with_retry(
            llm_response=response.content,
            llm=llm_instance,
            original_input="summarize today's meeting notes",
        )
        if result is None:
            # 3 retries exhausted — route to human
            failure_action = parser.last_failure_action
            ...
    """

    def __init__(self) -> None:
        self._pydantic_parser = PydanticOutputParser(
            pydantic_object=GlassBoxOutput,  # type: ignore[arg-type]
        )
        self.last_failure_action: AgentAction | None = None

    # ── Public helpers ────────────────────────────────────────────────────

    def get_format_instructions(self) -> str:
        """Return the format instructions string to append to prompts."""
        return self._pydantic_parser.get_format_instructions()

    # ── Core retry loop ───────────────────────────────────────────────────

    def parse_with_retry(
        self,
        llm_response: str,
        llm: ChatOllama,
        original_input: str,
        agent_id: str = "unknown-agent",
        max_retries: int = MAX_RETRIES,
    ) -> GlassBoxOutput | None:
        """Attempt to parse *llm_response*; retry with corrections on failure.

        Parameters
        ----------
        llm_response:
            Raw string content from the LLM's response message.
        llm:
            The ``ChatOllama`` instance to use for correction re-prompts.
        original_input:
            The user/system input that triggered the LLM call (used in
            corrective context so the LLM can fix format without changing
            substance).
        agent_id:
            Identifier of the calling agent (for audit logging on failure).
        max_retries:
            Maximum number of corrective re-prompts before yielding.

        Returns
        -------
        GlassBoxOutput | None
            Parsed output on success, or ``None`` if all retries exhausted
            (check ``self.last_failure_action`` for the audit record).
        """
        self.last_failure_action = None
        last_error: str = ""
        current_response: str = llm_response

        for attempt in range(1, max_retries + 1):
            try:
                # Try direct Pydantic parse first.
                parsed = self._pydantic_parser.parse(current_response)
                logger.debug(
                    "Glass Box parse OK on attempt %d/%d", attempt, max_retries
                )
                return parsed  # type: ignore[return-value]
            except Exception as exc:  # noqa: BLE001 — catch broad parse errors
                last_error = str(exc)
                logger.warning(
                    "Glass Box parse attempt %d/%d failed: %s",
                    attempt,
                    max_retries,
                    last_error[:200],
                )

                # Try salvaging JSON from markdown-fenced or prefixed output.
                salvaged = self._try_extract_json(current_response)
                if salvaged is not None:
                    try:
                        parsed = self._pydantic_parser.parse(
                            json.dumps(salvaged)
                        )
                        logger.info("Salvaged valid Glass Box JSON from raw output.")
                        return parsed  # type: ignore[return-value]
                    except Exception:  # noqa: BLE001
                        pass  # Fall through to corrective re-prompt.

                if attempt < max_retries:
                    # Send corrective re-prompt.
                    correction = _CORRECTION_TEMPLATE.format(
                        error=last_error[:500],
                        format_instructions=self.get_format_instructions(),
                        original_input=original_input[:1000],
                    )
                    try:
                        correction_resp = llm.invoke(correction)
                        current_response = correction_resp.content
                    except Exception as llm_exc:  # noqa: BLE001
                        logger.error(
                            "LLM unreachable during correction attempt: %s",
                            llm_exc,
                        )
                        break  # No point retrying if LLM is down.

        # ── All retries exhausted — yield to human ────────────────────────
        logger.error(
            "Glass Box parser exhausted %d retries for agent '%s'. "
            "Yielding to human operator.",
            max_retries,
            agent_id,
        )
        self.last_failure_action = _build_failure_action(
            agent_id=agent_id,
            original_input=original_input,
            attempts=max_retries,
            last_error=last_error,
        )
        return None

    # ── JSON salvage heuristic ────────────────────────────────────────────

    @staticmethod
    def _try_extract_json(text: str) -> dict[str, Any] | None:
        """Best-effort extraction of a JSON object from noisy LLM output.

        Handles common failure modes:
        * Markdown ```json ... ``` fences.
        * Leading prose before the opening brace.
        * Trailing commentary after the closing brace.
        """
        # Strip markdown fences.
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            # Remove first and last fence lines.
            lines = [
                ln for ln in lines if not ln.strip().startswith("```")
            ]
            cleaned = "\n".join(lines).strip()

        # Find first '{' and last '}'.
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            return json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError:
            return None


# ── Failure action builder ────────────────────────────────────────────────────


def _build_failure_action(
    agent_id: str,
    original_input: str,
    attempts: int,
    last_error: str,
) -> AgentAction:
    """Construct an audit-ready ``AgentAction`` for a parse-failure yield."""
    return AgentAction(
        agent_id=agent_id,
        action="LLM_PARSE_FAILURE_YIELD_TO_HUMAN",
        rationale=(
            f"Local LLM failed to produce valid Glass Box JSON after "
            f"{attempts} attempts.  Last error: {last_error[:300]}. "
            f"Yielding to human operator per protocol."
        ),
        ethical_impact=EthicalImpactLevel.HIGH,
        payload={
            "original_input": original_input[:2000],
            "attempts": attempts,
            "last_error": last_error[:500],
        },
    )
