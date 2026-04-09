"""
DisCO Ledger page — Contributory accounting & REA inventory dashboard.

Displays:
  - Contribution log by stream (livelihood / care / commons)
  - Valueflows REA treasury inventory
  - Contribution submission form → Steward Agent
"""

from __future__ import annotations

import streamlit as st
from frontend.api_client import get_inventory

STREAM_COLORS = {
    "livelihood": "🟦",
    "care":       "🟩",
    "commons":    "🟧",
}

STREAM_DESCRIPTIONS = {
    "livelihood": "Paid, market-facing work that generates cooperative revenue.",
    "care":       "Unpaid reproductive or community work sustaining the cooperative.",
    "commons":    "Open-source, knowledge commons, or public-good contributions.",
}


def _identity_guard() -> bool:
    if not st.session_state.identity:
        st.warning("Connect your identity on the **🪪 Identity** page.")
        return False
    return True


def render() -> None:
    st.title("📊 DisCO Ledger")
    st.caption(
        "Contributory accounting dashboard. All work is valued across three DisCO streams. "
        "Treasury inventory is formatted per the **Valueflows REA** standard."
    )

    if not _identity_guard():
        return

    identity = st.session_state.identity
    tab_inventory, tab_contributions, tab_log = st.tabs(
        ["💰 Treasury Inventory", "➕ Log Contribution", "📋 Contribution Log"]
    )

    # ── REA Treasury Inventory ─────────────────────────────────────────────────
    with tab_inventory:
        st.subheader("Valueflows REA Inventory Report")

        if st.button("🔄 Refresh Inventory"):
            st.session_state.pop("inventory_cache", None)

        if "inventory_cache" not in st.session_state:
            with st.spinner("Fetching on-chain resources..."):
                st.session_state.inventory_cache = get_inventory()

        inv = st.session_state.inventory_cache
        summary = inv.get("iskander:summary", "")
        resources = inv.get("vf:inventoryReport", [])

        if summary:
            st.markdown(summary)

        if resources:
            st.divider()
            for r in resources:
                name = r.get("vf:name", "Unknown Resource")
                qty  = r.get("vf:quantity", {})
                note = r.get("vf:note", "")
                col1, col2 = st.columns([3, 1])
                col1.markdown(f"**{name}**")
                if isinstance(qty, dict):
                    col2.metric(
                        qty.get("om2:hasUnit", ""),
                        qty.get("om2:hasNumericalValue", "N/A"),
                    )
                elif note:
                    col2.caption(note)

        with st.expander("Raw REA JSON"):
            st.json(inv)

    # ── Log Contribution ───────────────────────────────────────────────────────
    with tab_contributions:
        st.subheader("Log a Contribution")
        st.markdown("The **Steward Agent** will classify your contribution and record it in the cooperative ledger.")

        with st.form("contribution_form"):
            stream_hint = st.selectbox(
                "Suggested stream (agent may reclassify)",
                ["livelihood", "care", "commons"],
                format_func=lambda s: f"{STREAM_COLORS[s]} {s.capitalize()} — {STREAM_DESCRIPTIONS[s]}",
            )
            description = st.text_area(
                "Description *",
                placeholder="e.g. Wrote API documentation for the federation module (3 hours)",
            )
            hours       = st.number_input("Hours", min_value=0.0, step=0.25, value=0.0)
            ipfs_cid    = st.text_input("Evidence IPFS CID (optional)", placeholder="bafybei...")
            submitted   = st.form_submit_button("Submit Contribution")

        if submitted:
            if not description:
                st.error("Description is required.")
            else:
                # TODO: call POST /contributions once backend endpoint is wired.
                # For now display the payload that would be sent.
                payload = {
                    "member_did":     identity["did"],
                    "member_address": identity["address"],
                    "description":    description,
                    "stream_hint":    stream_hint,
                    "hours":          hours if hours > 0 else None,
                    "ipfs_cid":       ipfs_cid or None,
                }
                st.success("Contribution received — Steward Agent will classify and record.")
                st.json(payload)
                st.info("_Backend `POST /contributions` endpoint to be wired in a future sprint._")

    # ── Contribution Log ───────────────────────────────────────────────────────
    with tab_log:
        st.subheader("Contribution History")
        st.caption("Fetched from the cooperative's Postgres ledger (`contributions` table).")

        # TODO: call GET /contributions?member_did=... once backend endpoint exists
        st.info("Contribution history endpoint not yet wired. Data will appear here once the backend `GET /contributions` route is implemented.")

        st.divider()
        st.markdown("**Stream Legend**")
        for stream, emoji in STREAM_COLORS.items():
            st.markdown(f"{emoji} **{stream.capitalize()}** — {STREAM_DESCRIPTIONS[stream]}")
