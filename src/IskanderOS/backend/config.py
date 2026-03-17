"""
Project Iskander — Central Configuration
Loaded from environment variables / .env file via pydantic-settings.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── PostgreSQL ────────────────────────────────────────────────────────────
    database_url: str = (
        "postgresql+asyncpg://iskander:changeme_in_prod@localhost:5432/iskander_ledger"
    )

    # ── Ollama ────────────────────────────────────────────────────────────────
    # Phase 17: Default model switched from Llama 3 to OLMo (AI2).
    # OLMo is fully open-weight, open-data (Dolma corpus), open-training-code.
    # The cooperative can audit the entire pipeline. No extractive dependency.
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "olmo"

    # ── EVM / Anvil ───────────────────────────────────────────────────────────
    evm_rpc_url: str = "http://localhost:8545"
    evm_chain_id: int = 31337
    deployer_private_key: str = ""  # Never hardcode; load from .env

    # ── IPFS ──────────────────────────────────────────────────────────────────
    ipfs_api_url: str = "http://localhost:5001"

    # ── ActivityPub ───────────────────────────────────────────────────────────
    activitypub_domain: str = "iskander.local"
    activitypub_base_url: str = "http://iskander.local"

    # ── Safe Multi-sig ────────────────────────────────────────────────────────
    safe_address: str = "0x0000000000000000000000000000000000000000"

    # ── Vector Store / RAG (Phase 11) ────────────────────────────────────────
    embedding_model: str = "nomic-embed-text"
    rag_top_k: int = 3

    # ── ZK Democracy (Phase 12) ───────────────────────────────────────────────
    zk_coordinator_address: str = "0x0000000000000000000000000000000000000000"
    maci_coordinator_url: str = "http://localhost:3100"
    zk_circuits_dir: str = "/app/infra/zk-circuits"
    zk_care_work_enabled: bool = False

    # ── App Store / Container Orchestration (Phase 13) ────────────────────────
    docker_socket_url: str = "unix:///var/run/docker.sock"
    traefik_network: str = "iskander_apps"
    app_domain_suffix: str = "iskander.local"

    # ── Matrix Homeserver (Phase 14A) ─────────────────────────────────────────
    matrix_homeserver_url: str = "http://localhost:8008"
    matrix_domain: str = "iskander.local"
    matrix_appservice_token: str = ""        # Load from .env — never hardcode.
    matrix_bot_prefix: str = "@iskander_"

    # ── ActivityPub Signing Key (Phase 14B) ───────────────────────────────────
    activitypub_private_key_pem: str = ""    # RSA PEM string, loaded from .env.

    # ── Arbitration / Solidarity Court (Phase 15) ─────────────────────────────
    arbitration_jury_size: int = 5
    arbitration_timeout_days: int = 30
    escrow_default_timeout_days: int = 90
    trust_score_default: int = 1000
    trust_score_min: int = 0

    # ── LLM Concurrency Queue (Phase 16A) ─────────────────────────────────────
    # Max number of pending graph.invoke() calls before new requests get HTTP 503.
    agent_queue_max_depth: int = 50
    # Number of parallel queue workers. Keep at 1 for CPU-only Ollama nodes.
    # Increase to match GPU count on multi-GPU deployments.
    agent_queue_workers: int = 1

    # ── WebSocket Notifier (Phase 16B) ────────────────────────────────────────
    websocket_ping_interval: int = 30  # seconds between server-side keepalive pings

    # ── ICA Ethics Vetting Agent (Phase 17) ─────────────────────────────────
    # Minimum composite score (0-100) below which the agent flags a candidate
    # for mandatory human review, even if no individual principle scored FAIL.
    ica_vetting_composite_floor: int = 40
    # BrightID sponsor contract address (Phase 17: Sybil resistance).
    brightid_sponsor_contract: str = "0x0000000000000000000000000000000000000000"
    # Treasury private key for BrightID sponsorship (loaded from .env).
    treasury_private_key: str = ""

    # ── SIWE + JWT Authentication (Phase 19) ────────────────────────────────
    # Generate secret with: python -c "import secrets; print(secrets.token_urlsafe(64))"
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_access_expiry_minutes: int = 1440   # 24 hours
    jwt_refresh_expiry_days: int = 7

    # ── Gnosis Chain (Phase 19) ──────────────────────────────────────────────
    # Primary RPC is evm_rpc_url above. Fallback for Gnosis Chain public RPC.
    gnosis_rpc_fallback: str = "https://gnosis-pokt.nodies.app"

    # ── IPD Auditing System (Phase 18) ──────────────────────────────────────
    # Game-theoretic cooperation prediction and post-trade auditing.
    # Strategy: Generous Tit-for-Tat (GTfT).

    # P(cooperation) below this floor triggers mandatory HITL review.
    ipd_cooperation_floor: float = 0.4
    # Strategy identifier. Generous TfT: start cooperative, mirror partner's
    # last move, forgive defections with probability ipd_forgiveness_rate.
    ipd_strategy: str = "generous_tft"
    # Probability of cooperating when GTfT would defect (10% forgiveness).
    # Prevents mutual-defection death spirals from noise/misclassification.
    ipd_forgiveness_rate: float = 0.1
    # Bayesian prior cooperation probability for first-time partners.
    ipd_prior_cooperation: float = 0.7

    # Payoff matrix values (standard PD: T > R > P > S).
    ipd_payoff_r: float = 3.0   # Reward: mutual cooperation
    ipd_payoff_s: float = 0.0   # Sucker: cooperate vs defector
    ipd_payoff_t: float = 5.0   # Temptation: defect vs cooperator
    ipd_payoff_p: float = 1.0   # Punishment: mutual defection

    # Signal weights for cooperation probability aggregation.
    ipd_weight_pairwise: float = 0.25   # Pairwise cooperation ratio
    ipd_weight_global: float = 0.20     # Global cooperation ratio
    ipd_weight_trust_score: float = 0.15  # On-chain trust score (0-1000)
    ipd_weight_federation: float = 0.15   # Federation responsiveness
    ipd_weight_ica: float = 0.15         # ICA composite score
    ipd_weight_meatspace: float = 0.10   # Peer attestation average

    # Soft penalty for refusing an inter-node audit request.
    # Deducted from audit_compliance_rate in reputation_scores.
    # Only human juries (ArbitrationRegistry) can slash on-chain trust.
    ipd_audit_refusal_penalty: int = 5

    # ── HITL Routing Manager (Phase 20) ──────────────────────────────────────
    # Sovereign Personal Node HITL Routing: members who run their own Iskander
    # nodes receive proposals via ActivityPub. The cooperative routes — it does
    # not gatekeep.

    # Timeout for HITL proposals before auto-expiry (default: 72 hours).
    hitl_routing_timeout_seconds: int = 259200
    # DID resolver cache TTL — avoids hammering did:web endpoints.
    did_resolver_cache_ttl: int = 3600

    # ── Democratic AI Model Lifecycle (Phase 21) ──────────────────────────────
    # Hardware-aware model upgrades gated by democratic consensus.
    # Prevents OOM crashes while allowing the cooperative's AI to evolve.

    # Timeout for ollama pull operations (default: 30 minutes).
    model_pull_timeout_seconds: int = 1800
    # VRAM safety margin — reserve this fraction of VRAM for system overhead.
    vram_safety_margin: float = 0.15

    # ── Fiat-Backed Solidarity Economy (Phase 22) ─────────────────────────────
    # Cooperative Fiat Token (cFIAT) bridge: on-chain escrow ↔ off-chain bank.
    # Anti-extractive: bypasses Visa/MC/Stripe, returns fees to workers.
    # Regulatory: 1:1 fiat backing in a regulated cooperative bank trust account.

    # CoopFiatToken ERC-20 contract address (deployed via Foundry).
    cfiat_token_address: str = "0x0000000000000000000000000000000000000000"
    # BankOracle address — the only address that can mint/burn cFIAT.
    bank_oracle_address: str = "0x0000000000000000000000000000000000000000"
    # Open Banking API base URL (PSD2-compliant provider: Plaid, TrueLayer, etc.).
    open_banking_api_url: str = "http://localhost:9000/api/v1"
    # Open Banking API key — read-only by default. Write access requires HITL.
    open_banking_api_key: str = ""
    # Default fiat currency for cFIAT operations.
    cfiat_currency: str = "GBP"
    # cFIAT token symbol (matches CoopFiatToken.sol symbol()).
    cfiat_symbol: str = "cGBP"

    # ── Stewardship Council (Phase 23) ──────────────────────────────────────
    # Dynamic governance delegation with gSBT-weighted voting, Impact Score
    # reputation, and emergency veto. Anti-hierarchical: steward roles expire
    # automatically when contribution scores drop below the protocol threshold.

    # StewardshipLedger contract address (deployed via Foundry).
    stewardship_ledger_address: str = "0x0000000000000000000000000000000000000000"
    # Oracle address authorised to push Impact Score batches to the contract.
    stewardship_oracle_address: str = "0x0000000000000000000000000000000000000000"
    # Default steward eligibility threshold (0.0–1.0). Nodes below this cannot
    # receive delegations. Updated periodically by the StewardshipScorer agent.
    steward_threshold_default: float = 0.25
    # Anticipatory warning margin: warn nodes whose Impact Score is within this
    # distance of the threshold that their steward status may expire.
    steward_warning_margin: float = 0.10
    # How often the StewardshipScorer recalculates Impact Scores (hours).
    stewardship_scoring_interval_hours: int = 24
    # Solvency circuit-breaker ratio (basis points). If total on-chain escrow
    # exceeds fiat_reserve * (solvency_factor_bps / 10000), the contract blocks
    # new delegations and exposure-increasing decisions.
    solvency_factor_bps: int = 10000

    # ── Energy Gate / Hearth Driver (Phase 24) ────────────────────────────────
    # Hardware-in-the-loop energy-aware scheduling. The Hearth driver reads
    # battery telemetry and enforces tri-state execution policies (GREEN/
    # YELLOW/RED) that throttle or halt agent activity when power is scarce.

    # Battery percentage thresholds for tri-state transitions.
    energy_green_battery_pct: int = 80   # Above this = GREEN (if on battery)
    energy_yellow_battery_pct: int = 20  # Above this = YELLOW; below = RED

    # ── Mesh Archive / Sovereign Data Fabric (Phase 25) ──────────────────────
    # Distributed, content-addressed archive using IPFS for storage and
    # SBT/EVM identity for access control. Glass Box rationale is immutable
    # and permissioned correctly.

    # IPFS gateway URL for public reads (ipfs_api_url above is for daemon API).
    ipfs_gateway_url: str = "http://localhost:8080"
    # Environment variable name holding the Fernet encryption key for mesh data.
    mesh_encryption_key_env: str = "ISKANDER_MESH_KEY"

    # ── Federated Pinning (Fix 3) ──────────────────────────────────────────
    mesh_min_replicas: int = 3
    mesh_pin_timeout_seconds: int = 30
    mesh_require_geo_diversity: bool = True
    mesh_min_distinct_regions: int = 2

    # ── Chain-Anchored Sync (Fix 4) ────────────────────────────────────────
    mesh_anchor_batch_window_seconds: int = 60

    # ── Fiat-Crypto Bridge Agent (Phase 26) ───────────────────────────────────
    # Extends Phase 22 stubs with agent-level solvency enforcement and oracle.

    # cFIAT mint approval threshold — mints above this require HITL approval.
    cfiat_mint_approval_threshold: int = 10000  # in smallest token unit

    # ── Signed Sensor Protocol (Fix 5) ────────────────────────────────────
    # When True, unverified psutil readings are capped at YELLOW (never GREEN).
    # Set to True on nodes with Hearth hardware HATs. Leave False for dev/VMs.
    energy_require_signed_telemetry: bool = False
    # Grace period for deprecated signature versions (days).
    energy_legacy_grace_period_days: int = 180

    # ── HITL Rate Limiting (Fix 6) ────────────────────────────────────────
    hitl_max_requests_per_hour: int = 10
    hitl_batch_window_seconds: int = 300
    hitl_crisis_multiplier: int = 100

    # ── Boundary Agent / Embassy (Fix 7) ──────────────────────────────────
    boundary_initial_trust_penalty: float = 0.3
    boundary_trust_recovery_rate: float = 0.02
    boundary_trust_decay_rate: float = 0.1
    boundary_causal_buffer_max_age_seconds: int = 300
    boundary_causal_buffer_max_size: int = 1000
    boundary_require_governance_proof: bool = True
    boundary_unknown_field_policy: str = "quarantine"

    # ── Iskander Knowledge Commons (IKC) ─────────────────────────────────────
    # Decentralized University: content-addressed knowledge assets with
    # curator consensus and tombstone-only lifecycle.

    # Maximum number of assets that can declare dependency on a single CID.
    # Prevents dependency-graph-poisoning attacks (VULN-1).
    ikc_max_dependents_per_asset: int = 50
    # Cooldown after Break-Glass deactivation before it can be re-activated.
    ikc_break_glass_cooldown_seconds: int = 3600
    # Maximum Break-Glass activations per 24-hour window (VULN-3 mitigation).
    ikc_break_glass_max_activations_per_day: int = 3
    # DeepFreeze auto-expiry: assets transition to Legacy after this many days.
    # Prevents permanent lock if StewardshipCouncil is inactive (VULN-6).
    ikc_deep_freeze_max_days: int = 365
    # Flag identical curator rationales across N debates as suspicious.
    ikc_curator_vote_staleness_threshold: int = 10

    # ── Foreign Reputation System (FRS) / Diplomatic Embassy ──────────────
    # On-chain exponential-decay reputation for foreign SDCs.
    # Tier thresholds in basis points (0–10000):
    #   Tier 0 (Quarantine)  : score < frs_quarantine_threshold_bps
    #   Tier 1 (Provisional) : score < frs_provisional_threshold_bps
    #   Tier 2 (Trusted)     : score < frs_trusted_threshold_bps
    #   Tier 3 (Allied)      : score >= frs_trusted_threshold_bps

    # ForeignReputation.sol contract address (deployed via Foundry).
    frs_contract_address: str = "0x0000000000000000000000000000000000000000"
    # Oracle address authorised to push score updates.
    frs_oracle_address: str = "0x0000000000000000000000000000000000000000"
    # Tier thresholds (basis points).
    frs_quarantine_threshold_bps: int = 1000     # 10%
    frs_provisional_threshold_bps: int = 3000    # 30%
    frs_trusted_threshold_bps: int = 7000        # 70%
    # Half-life for exponential decay (seconds). Default: 30 days.
    frs_decay_half_life_seconds: int = 2592000   # 30 * 86400
    # Collision detection: title similarity threshold for flagging overlaps.
    frs_collision_similarity_threshold: float = 0.7
    # Quarantine sandbox TTL: unresolved assets expire after this many days.
    frs_quarantine_ttl_days: int = 90

    # ── Researcher-in-the-Loop (RITL) ─────────────────────────────────────
    # Peer review parameters for the Research Fellowship module.

    # Maximum review rounds before automatic rejection.
    ritl_max_review_rounds: int = 3
    # Score floor (0-100) below which a dimension triggers HITL review.
    ritl_review_score_floor: int = 40
    # Enable blind review (ZK-flow) by default for new submissions.
    ritl_default_blind_mode: bool = False

    # ── Governance Orchestrator (ComplianceFactory + PolicyEngine + Tx) ────
    # ComplianceFactory: jurisdiction-agnostic template DSL
    compliance_manifests_dir: str = "backend/compliance/manifests"
    # TxOrchestrator: Safe batch draft time-to-live (days before Stale)
    tx_draft_ttl_days: int = 14
    # DigitalNotary: env var name for the HMAC/Ed25519 signing key
    notary_signing_key_env: str = "ISKANDER_NOTARY_KEY"
    # PolicyEngine: path to the cooperative's governance manifest JSON
    governance_manifest_path: str = "backend/governance/governance_manifest.json"
    # Background check interval for stale transaction cleanup
    tx_stale_check_interval_hours: int = 24

    # ── Credential Embassy (W3C VC → Internal Attestation) ─────────────────
    # Offline-first verification of W3C Verifiable Credentials against the
    # on-chain TrustRegistry. No live pings to issuer servers.

    # TrustRegistry.sol contract address (deployed via Foundry).
    trust_registry_address: str = "0x0000000000000000000000000000000000000000"
    # Revocation list cache TTL — how long to cache issuer revocation lists.
    # Default: 24 hours. Prevents per-verification HTTP requests.
    vc_revocation_cache_ttl_seconds: int = 86400
    # Maximum number of attestations per holder DID (DoS mitigation).
    vc_max_attestations_per_holder: int = 100


settings = Settings()
