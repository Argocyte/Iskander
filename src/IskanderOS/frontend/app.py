"""
Project Iskander — Universal Client (Streamlit)
Run: streamlit run frontend/app.py --server.port 8501

Pages:
  🏠 Home           — Node status & first-boot entry point
  🪪 Identity       — Cooperative identity & wallet connect
  💬 Agentic Chat   — Natural language → LangGraph workflows
  🏛 Governance     — Pending Safe tx proposals (HITL dashboard)
  📊 DisCO Ledger   — Contributory accounting & REA inventory
"""

import streamlit as st

st.set_page_config(
    page_title="Iskander Sovereign Node",
    page_icon="🤝",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Session state defaults ────────────────────────────────────────────────────
if "identity" not in st.session_state:
    st.session_state.identity = None   # active CoopIdentity (address + DID + role)
if "node_ok" not in st.session_state:
    st.session_state.node_ok  = False

# ── Sidebar navigation ────────────────────────────────────────────────────────
st.sidebar.image("https://upload.wikimedia.org/wikipedia/commons/thumb/f/f1/Heartandhand.svg/240px-Heartandhand.svg.png", width=80)
st.sidebar.title("Iskander Node")
st.sidebar.caption("Solidarity Stack v0.1")

page = st.sidebar.radio(
    "Navigate",
    ["🏠 Home", "🪪 Identity", "💬 Agentic Chat", "🏛 Governance", "📊 DisCO Ledger"],
)

# ── Node health indicator ─────────────────────────────────────────────────────
try:
    from frontend.api_client import health
    h = health()
    st.session_state.node_ok = True
    st.sidebar.success(f"Node: **{h.get('node', 'iskander.local')}** ✓")
    st.sidebar.caption(f"LLM: `{h.get('llm_model')}` | Chain: `{h.get('evm_chain_id')}`")
except Exception:
    st.session_state.node_ok = False
    st.sidebar.error("Backend unreachable — is docker-compose up?")

st.sidebar.divider()

# ── Identity badge in sidebar ─────────────────────────────────────────────────
if st.session_state.identity:
    id_ = st.session_state.identity
    st.sidebar.markdown(f"**Active Identity**")
    st.sidebar.markdown(f"`{id_['address'][:10]}...`")
    st.sidebar.caption(f"Role: {id_['role']}")
    if st.sidebar.button("Disconnect"):
        st.session_state.identity = None
        st.rerun()
else:
    st.sidebar.warning("No identity connected")

# ── Page routing ──────────────────────────────────────────────────────────────
if page == "🏠 Home":
    from frontend.pages.home import render
    render()
elif page == "🪪 Identity":
    from frontend.pages.identity import render
    render()
elif page == "💬 Agentic Chat":
    from frontend.pages.chat import render
    render()
elif page == "🏛 Governance":
    from frontend.pages.governance import render
    render()
elif page == "📊 DisCO Ledger":
    from frontend.pages.ledger import render
    render()
