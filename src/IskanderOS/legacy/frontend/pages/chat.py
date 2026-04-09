"""
Agentic Chat page — natural language UI to trigger LangGraph workflows.

Interprets member intent and routes to:
  - Steward Agent  : contribution logging
  - Governance Agent: treasury proposals
  - Inventory Agent : resource queries
"""

from __future__ import annotations

import streamlit as st
from frontend.api_client import submit_proposal

ROUTE_KEYWORDS = {
    "proposal":     ["propose", "vote", "treasury", "spend", "payment", "transfer", "fund"],
    "contribution": ["contributed", "contribution", "worked", "hours", "care", "commons", "livelihood"],
    "inventory":    ["balance", "treasury", "assets", "inventory", "resources", "how much"],
}


def _detect_intent(text: str) -> str:
    lower = text.lower()
    for intent, keywords in ROUTE_KEYWORDS.items():
        if any(k in lower for k in keywords):
            return intent
    return "unknown"


def _identity_guard() -> bool:
    if not st.session_state.identity:
        st.warning("Connect your identity on the **🪪 Identity** page before using the chat.")
        return False
    return True


def render() -> None:
    st.title("💬 Agentic Chat")
    st.caption(
        "Natural language interface to your cooperative's AI agents. "
        "Agents operate under the **Glass Box Protocol** — every action is logged with a rationale."
    )

    if not _identity_guard():
        return

    # ── Chat history ──────────────────────────────────────────────────────────
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # ── Input ─────────────────────────────────────────────────────────────────
    user_input = st.chat_input("e.g. 'Log 3 hours of documentation work' or 'Propose paying Alice 500 USDC'")

    if not user_input:
        if not st.session_state.chat_history:
            st.info("Try: _'Propose sending 100 USDC to 0xAbc... for server costs'_ or _'I worked 4 hours on client project X'_")
        return

    # Display user message
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    intent = _detect_intent(user_input)
    identity = st.session_state.identity

    with st.chat_message("assistant"):
        with st.spinner("Agent thinking..."):

            if intent == "proposal":
                try:
                    result = submit_proposal({
                        "description": user_input,
                        "proposed_by": identity["did"],
                    })
                    thread_id = result["thread_id"]
                    tx = result.get("safe_tx_draft", {})
                    reply = (
                        f"**Governance proposal created.**\n\n"
                        f"Thread ID: `{thread_id}`\n\n"
                        f"Draft Safe transaction:\n"
                        f"- **To:** `{tx.get('to', 'N/A')}`\n"
                        f"- **Value:** `{tx.get('value', '0')} wei`\n\n"
                        f"Go to **🏛 Governance** to review and vote on this proposal."
                    )
                except Exception as exc:
                    reply = f"Error submitting proposal: `{exc}`"

            elif intent == "contribution":
                # Route to steward agent via a future /contributions endpoint
                # For now: acknowledge and show Glass Box info
                reply = (
                    f"**Contribution noted.**\n\n"
                    f"The Steward Agent will classify this as Livelihood, Care, or Commons work.\n\n"
                    f"> _{user_input}_\n\n"
                    f"_Full ledger write via `POST /contributions` — wiring complete in Phase 5 backend extension._"
                )

            elif intent == "inventory":
                reply = (
                    "**Inventory query received.**\n\n"
                    "The Web3 Inventory Agent will fetch on-chain balances and format them "
                    "as a Valueflows REA report.\n\n"
                    "Go to **📊 DisCO Ledger** to view the full inventory."
                )

            else:
                reply = (
                    "I can help with:\n"
                    "- **Governance proposals** — _'Propose paying X for Y'_\n"
                    "- **Contribution logging** — _'I worked 3 hours on docs'_\n"
                    "- **Inventory queries** — _'What's our treasury balance?'_\n\n"
                    "Could you rephrase with one of those intents?"
                )

        st.markdown(reply)
        st.session_state.chat_history.append({"role": "assistant", "content": reply})
