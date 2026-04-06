"""
Project Iskander — FastAPI Sovereign Node Entry Point
Run: uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
"""

import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.db import close_pool, init_pool

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("iskander_node_starting", domain=settings.activitypub_domain)
    from backend.core.llm_queue_manager import AsyncAgentQueue
    try:
        await init_pool()
        logger.info("asyncpg_pool_initialised")
    except Exception as exc:
        logger.warning("asyncpg_pool_unavailable", error=str(exc))
    AsyncAgentQueue.get_instance().start()
    logger.info("iskander_agent_queue_started")
    yield
    AsyncAgentQueue.get_instance().stop()
    await close_pool()
    logger.info("iskander_node_stopping")


app = FastAPI(
    title="Project Iskander — Sovereign Node API",
    description=(
        "Agentic AI operating system for DisCOs and Platform Co-ops. "
        "Implements the Solidarity Stack and ICA Cooperative Principles."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production via Legal Wrapper policy
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
from backend.routers.constitution import router as constitution_router
from backend.routers.federation   import router as federation_router
from backend.routers.governance   import router as governance_router
from backend.routers.inventory    import router as inventory_router
from backend.routers.power        import router as power_router
from backend.routers.secretary    import router as secretary_router
from backend.routers.treasury     import router as treasury_router
from backend.routers.steward_v2   import router as steward_v2_router
from backend.routers.procurement  import router as procurement_router
from backend.routers.spawner      import router as spawner_router
from backend.routers.appstore     import router as appstore_router
from backend.routers.matrix_admin import router as matrix_router
from backend.routers.escrow       import router as escrow_router
from backend.routers.arbitration  import router as arbitration_router
from backend.routers.tasks        import router as tasks_router
from backend.api.websocket_notifier import router as ws_router
# Phase 17: ICA Ethics Vetting Agent, BrightID Sponsorship, Ricardian Legal Generator
from backend.routers.ica_vetting           import router as ica_vetting_router
from backend.api.brightid_sponsor          import router as brightid_router
from backend.api.constitutional_dialogue   import router as legal_router
# Phase 18: IPD Auditing System — game-theoretic cooperation prediction & auditing
from backend.routers.ipd_audit             import router as ipd_audit_router
# Phase 19: SIWE + JWT Authentication
from backend.routers.auth                  import router as auth_router
# Phase 19: Custodial Treasury / Internal Credit System
from backend.routers.credits               import router as credits_router
# Phase 21: Democratic AI Model Lifecycle & Hardware-Aware Upgrades
from backend.api.model_manager             import router as model_router
from backend.api.model_manager             import system_router as system_capabilities_router
# Phase 23: Stewardship Council — dynamic governance delegation & Impact Scores
from backend.routers.stewardship           import router as stewardship_router
# Phase 25: Mesh Archive — sovereign data fabric (IPFS, CausalEvents, Delta-Sync)
from backend.routers.mesh                  import router as mesh_router
# Phase 26: Fiat-Crypto Bridge — cFIAT mint/burn, solvency oracle
from backend.routers.fiat                  import router as fiat_router
# IKC: Iskander Knowledge Commons — Decentralized University
from backend.routers.knowledge             import router as knowledge_router
# Diplomatic Embassy: Foreign Reputation System, Ingestion Embassy, RITL Peer Review
from backend.routers.diplomacy             import router as diplomacy_router
# Genesis Boot Sequence — one-way cooperative initialization
from backend.routers.genesis               import router as genesis_router
# Deliberation Data Layer — working group management
from backend.routers.subgroups             import router as subgroups_router
from backend.routers.deliberation          import router as deliberation_router

app.include_router(constitution_router)
app.include_router(federation_router)
app.include_router(governance_router)
app.include_router(inventory_router)
app.include_router(power_router)
app.include_router(secretary_router)
app.include_router(treasury_router)
app.include_router(steward_v2_router)
app.include_router(procurement_router)
app.include_router(spawner_router)
app.include_router(appstore_router)
app.include_router(matrix_router)
app.include_router(escrow_router)
app.include_router(arbitration_router)
app.include_router(tasks_router)
app.include_router(ws_router)      # WebSocket /ws/events
# Phase 17: Ethics vetting, identity, and legal arbitration endpoints
app.include_router(ica_vetting_router)   # /ica-vetting/assess, /ica-vetting/principles
app.include_router(brightid_router)      # /api/brightid/sponsor
app.include_router(legal_router)         # /api/legal/generate-ricardian
# Phase 18: Game-theoretic cooperation prediction and post-trade auditing
app.include_router(ipd_audit_router)     # /ipd-audit/predict, /ipd-audit/record-outcome, etc.
# Phase 19: Wallet authentication via Sign-In with Ethereum
app.include_router(auth_router)          # /auth/nonce, /auth/login, /auth/refresh, /auth/logout
# Phase 19: Custodial treasury — internal credit system for off-chain members
app.include_router(credits_router)       # /credits/deposit, /credits/balance, /credits/transfer, etc.
# Phase 21: Hardware-aware model lifecycle — democratic AI upgrades
app.include_router(system_capabilities_router)  # /api/system/capabilities
app.include_router(model_router)                # /api/models/available, /api/models/propose_upgrade
# Phase 23: Stewardship Council — delegation, scoring, veto, rationale
app.include_router(stewardship_router)          # /stewardship/compute-scores, /stewardship/delegate, etc.
# Phase 25: Mesh Archive — content-addressed IPFS storage with SBT access control
app.include_router(mesh_router)                 # /mesh/pin, /mesh/cat/{cid}, /mesh/events, /mesh/sync
# Phase 26: Fiat-Crypto Bridge — cFIAT mint/burn proposals and solvency queries
app.include_router(fiat_router)                 # /fiat/mint, /fiat/burn, /fiat/reserve, /fiat/solvency
# IKC: Iskander Knowledge Commons — Decentralized University
app.include_router(knowledge_router)            # /knowledge/register, /knowledge/curate, /knowledge/break-glass
# Diplomatic Embassy: FRS, quarantine sandbox, RITL peer review
app.include_router(diplomacy_router)            # /diplomacy/sdc, /diplomacy/ingest, /diplomacy/research
# Genesis Boot Sequence — one-way cooperative initialization
app.include_router(genesis_router)          # /genesis/status, /genesis/boot, /genesis/founders, etc.
# Deliberation Data Layer — working group management
app.include_router(subgroups_router)        # /subgroups — working group management
app.include_router(deliberation_router)      # /deliberation — threads, proposals, votes


@app.get("/health", tags=["system"])
async def health() -> dict:
    """Liveness probe — confirms node is running."""
    from backend.core.llm_queue_manager import AsyncAgentQueue
    from backend.api.websocket_notifier import WebSocketNotifier
    return {
        "status": "ok",
        "node": settings.activitypub_domain,
        "evm_chain_id": settings.evm_chain_id,
        "llm_model": settings.ollama_model,
        "queue_depth": AsyncAgentQueue.get_instance().queue_depth(),
        "ws_connections": WebSocketNotifier.get_instance().active_connections(),
    }

