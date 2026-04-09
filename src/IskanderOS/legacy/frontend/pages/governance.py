"""
Governance page — Treasury & HITL proposal dashboard.

Displays pending Safe multi-sig transactions awaiting human signatures.
Members vote approve/reject; the governance agent graph resumes on vote.
"""

from __future__ import annotations

import streamlit as st
from frontend.api_client import cast_vote, get_proposal, submit_proposal


def _identity_guard() -> bool:
    if not st.session_state.identity:
        st.warning("Connect your identity on the **🪪 Identity** page.")
        return False
    return True


def render() -> None:
    st.title("🏛 Governance & Treasury")
    st.caption(
        "Pending Safe multi-sig transaction proposals. "
        "No treasury action executes without M-of-N human approval. "
        "AI agents draft proposals — **humans sign.**"
    )

    if not _identity_guard():
        return

    identity = st.session_state.identity
    tab_pending, tab_propose = st.tabs(["📋 Pending Proposals", "➕ New Proposal"])

    # ── Pending proposals ─────────────────────────────────────────────────────
    with tab_pending:
        st.subheader("Lookup Proposal by Thread ID")
        thread_input = st.text_input("Thread ID", placeholder="Paste thread_id from Agentic Chat")

        if thread_input:
            with st.spinner("Fetching proposal state..."):
                try:
                    proposal = get_proposal(thread_input)
                except Exception as exc:
                    st.error(f"Proposal not found: {exc}")
                    return

            status = proposal.get("status", "unknown")
            color  = {"pending_human_review": "🟡", "approved": "🟢", "rejected": "🔴"}.get(status, "⚪")
            st.markdown(f"**Status:** {color} `{status}`")

            tx = proposal.get("safe_tx_draft") or {}
            if tx:
                st.subheader("Unsigned Safe Transaction")
                col1, col2 = st.columns(2)
                col1.metric("To",    tx.get("to", "N/A"))
                col2.metric("Value", f"{tx.get('value', '0')} wei")
                col1.metric("Chain", str(tx.get("chainId", "N/A")))
                col2.metric("Nonce", str(tx.get("nonce", "N/A")))

                if tx.get("data") and tx["data"] != "0x":
                    st.code(tx["data"], language="text")

                st.caption(tx.get("_iskander_note", ""))

            # Vote controls — only show if pending
            if status == "pending_human_review":
                st.divider()
                st.subheader("Cast Your Vote")
                st.warning("This action will be recorded on the Glass Box audit log.")

                col_approve, col_reject = st.columns(2)

                with col_approve:
                    if st.button("✅ Approve", use_container_width=True):
                        with st.spinner("Submitting vote..."):
                            try:
                                result = cast_vote({
                                    "thread_id":  thread_input,
                                    "approved":   True,
                                    "voter_did":  identity["did"],
                                })
                                st.success("Vote cast: **Approved**. Unsigned tx queued for steward signatures.")
                                st.json(result.get("safe_tx_draft", {}))
                            except Exception as exc:
                                st.error(f"Vote error: {exc}")

                with col_reject:
                    with st.expander("❌ Reject"):
                        reason = st.text_area("Rejection reason (required)", key="reject_reason")
                        if st.button("Confirm Rejection", use_container_width=True):
                            if not reason:
                                st.error("Rejection reason is required.")
                            else:
                                with st.spinner("Submitting vote..."):
                                    try:
                                        cast_vote({
                                            "thread_id":        thread_input,
                                            "approved":         False,
                                            "rejection_reason": reason,
                                            "voter_did":        identity["did"],
                                        })
                                        st.success("Vote cast: **Rejected**.")
                                    except Exception as exc:
                                        st.error(f"Vote error: {exc}")

            # Glass Box action log
            action_log = proposal.get("action_log", [])
            if action_log:
                with st.expander(f"Glass Box Audit Log ({len(action_log)} entries)"):
                    for entry in action_log:
                        st.json(entry)

    # ── New proposal form ─────────────────────────────────────────────────────
    with tab_propose:
        st.subheader("Submit a Governance Proposal")
        st.caption("The Governance Agent will parse your description and draft an unsigned Safe transaction.")

        with st.form("proposal_form"):
            description = st.text_area(
                "Proposal Description *",
                placeholder="Propose paying 0xAbc... 500 USDC for server infrastructure costs.",
            )
            to_address  = st.text_input("Recipient Address (optional — agent will extract from description)")
            value_wei   = st.number_input("Value in Wei", min_value=0, value=0)
            nonce       = st.number_input("Safe Nonce", min_value=0, value=0)
            submitted   = st.form_submit_button("Submit Proposal")

        if submitted:
            if not description:
                st.error("Description is required.")
            else:
                with st.spinner("Governance agent drafting Safe transaction..."):
                    try:
                        result = submit_proposal({
                            "description": description,
                            "to":          to_address or None,
                            "value_wei":   int(value_wei),
                            "nonce":       int(nonce),
                            "proposed_by": identity["did"],
                        })
                        st.success(f"Proposal submitted. Thread ID: `{result['thread_id']}`")
                        st.info("Copy the Thread ID and paste it in the **Pending Proposals** tab to vote.")
                        st.json(result.get("safe_tx_draft", {}))
                    except Exception as exc:
                        st.error(f"Error: {exc}")
