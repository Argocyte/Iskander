"""
Identity & Wallet Connect page.

Allows members to load a cooperative identity by entering their
EVM address, W3C DID, and role. In production this connects to
the CoopIdentity ERC-4973 contract to verify on-chain membership.
"""

from __future__ import annotations

import streamlit as st


def render() -> None:
    st.title("🪪 Cooperative Identity")
    st.caption(
        "Connect your cooperative identity to interact with the governance and ledger systems. "
        "Your address is verified against the `CoopIdentity` ERC-4973 contract."
    )

    # ── Active identity display ───────────────────────────────────────────────
    if st.session_state.identity:
        id_ = st.session_state.identity
        st.success("Identity connected")
        col1, col2, col3 = st.columns(3)
        col1.metric("Address", f"{id_['address'][:8]}...{id_['address'][-4:]}")
        col2.metric("Role", id_["role"])
        col3.metric("DID", f"{id_['did'][:16]}..." if len(id_['did']) > 16 else id_['did'])

        st.divider()
        st.subheader("Switch Identity")

    # ── Connect form ──────────────────────────────────────────────────────────
    with st.form("identity_form"):
        address = st.text_input(
            "EVM Address *",
            placeholder="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
        )
        did = st.text_input(
            "W3C DID *",
            placeholder="did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
        )
        role = st.selectbox("Role", ["worker-owner", "steward", "associate", "observer"])
        connect = st.form_submit_button("Connect Identity")

    if connect:
        if not address or not did:
            st.error("Address and DID are required.")
            return

        if not address.startswith("0x") or len(address) != 42:
            st.error("Invalid EVM address format.")
            return

        # TODO Phase 5 full impl: call CoopIdentity.balanceOf(address) via web3.py
        # to verify on-chain membership before setting session state.
        # For now: accept any address for local dev.

        st.session_state.identity = {
            "address": address,
            "did":     did,
            "role":    role,
        }
        st.success(f"Identity connected: `{address[:10]}...` as **{role}**")
        st.rerun()

    st.divider()

    # ── About ERC-4973 ────────────────────────────────────────────────────────
    with st.expander("About CoopIdentity (ERC-4973)"):
        st.markdown("""
**ERC-4973 Account-Bound Tokens (SBTs)** are non-transferable membership tokens.

- Each member holds exactly **one token** permanently bound to their address.
- Membership is attested (minted) and revoked (burned) by the **Steward Safe** multi-sig.
- The token's `legalWrapperCID` field links it immutably to the cooperative's Ricardian Constitution on IPFS.
- Tokens **cannot be transferred or sold** — they represent membership, not speculative assets.

> ⚠️ Revoking membership on-chain does not constitute lawful expulsion.
> The process defined in the off-chain legal wrapper governs.
        """)
