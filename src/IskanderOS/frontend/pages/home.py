"""
Home page — Node status & First-Boot Constitutional Dialogue entry point.
"""

from __future__ import annotations

import streamlit as st
from frontend.api_client import generate_constitution

CCIN_PRINCIPLES = [
    "Open Membership",
    "Democratic Member Control",
    "Member Economic Participation",
    "Autonomy & Independence",
    "Education, Training & Information",
    "Cooperation Among Cooperatives",
    "Concern for Community",
    "Ecological Sustainability",
    "Solidarity Economy",
    "Digital Commons",
]


def render() -> None:
    st.title("🤝 Welcome to your Iskander Sovereign Node")
    st.markdown(
        "_An open-source, federated Agentic AI OS for DisCOs and Platform Co-ops._"
    )

    if not st.session_state.node_ok:
        st.error("Backend is offline. Run `docker-compose up` and refresh.")
        st.code("docker-compose up -d", language="bash")
        return

    st.success("Node is running. Complete the First-Boot Dialogue below to initialise your cooperative.")
    st.divider()

    # ── First-Boot Constitutional Dialogue ────────────────────────────────────
    st.subheader("📜 First-Boot Constitutional Dialogue")
    st.caption(
        "This form generates your cooperative's Ricardian Constitution and pins it to IPFS. "
        "The resulting CID must be passed to `CoopIdentity.sol` at deployment. "
        "**Consult a lawyer before ratifying this document.**"
    )

    with st.form("constitution_form"):
        coop_name         = st.text_input("Cooperative Name *", placeholder="Sunrise Worker Co-op")
        jurisdiction      = st.text_input("Jurisdiction *", placeholder="Colorado, USA")
        legal_wrapper     = st.selectbox("Legal Wrapper Type", ["LCA", "LLC Operating Agreement", "Bylaws", "Other"])
        mission           = st.text_area("Mission Statement *", placeholder="We exist to...")
        founding_members  = st.text_area("Founding Member DIDs (one per line) *", placeholder="did:key:z6Mk...")
        pay_ratio         = st.slider("Pay Ratio Cap (highest:lowest)", min_value=1, max_value=20, value=6)
        ccin_selected     = st.multiselect("CCIN Principles", CCIN_PRINCIPLES, default=CCIN_PRINCIPLES[:7])
        submitted         = st.form_submit_button("Generate Constitution & Pin to IPFS")

    if submitted:
        members = [m.strip() for m in founding_members.splitlines() if m.strip()]
        if not all([coop_name, jurisdiction, mission, members]):
            st.error("Please fill in all required fields (*).")
            return

        with st.spinner("Generating constitution and uploading to IPFS..."):
            try:
                result = generate_constitution({
                    "coop_name":          coop_name,
                    "jurisdiction":       jurisdiction,
                    "legal_wrapper_type": legal_wrapper,
                    "mission_statement":  mission,
                    "founding_members":   members,
                    "pay_ratio":          pay_ratio,
                    "ccin_principles":    ccin_selected,
                })
                st.success(f"Constitution generated! IPFS CID: `{result['ipfs_cid']}`")
                st.info(f"**Next step:** Deploy `CoopIdentity.sol` with `legalWrapperCID = \"{result['ipfs_cid']}\"`")

                with st.expander("View Constitution Markdown"):
                    st.markdown(result["constitution_markdown"])

                with st.expander("View Glass Box Agent Action"):
                    st.json(result["agent_action"])

            except Exception as exc:
                st.error(f"Error: {exc}")
