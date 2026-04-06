-- Project Iskander — PostgreSQL Ledger Bootstrap
-- Tracks EVM revert events, agent actions, and contributory accounting records.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- Agent audit log (Glass Box Protocol)
CREATE TABLE IF NOT EXISTS agent_actions (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id      TEXT NOT NULL,
    action        TEXT NOT NULL,
    rationale     TEXT NOT NULL,
    ethical_impact TEXT NOT NULL,
    timestamp     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    payload       JSONB
);

-- EVM revert log
CREATE TABLE IF NOT EXISTS evm_reverts (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tx_hash       TEXT,
    contract      TEXT NOT NULL,
    reason        TEXT NOT NULL,
    agent_action_id UUID REFERENCES agent_actions(id),
    timestamp     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- DisCO contributory accounting streams
-- Phase 12: care work entries replace `description` with a ZK-SNARK proof JSON
--   stored in `zk_proof`. The raw conversational rationale is NEVER persisted.
--   Privacy guarantee: no auditor can reconstruct private member conversations
--   from this table. Only the cryptographic commitment to the result is stored.
CREATE TABLE IF NOT EXISTS contributions (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    member_did    TEXT NOT NULL,
    stream        TEXT NOT NULL CHECK (stream IN ('livelihood', 'care', 'commons')),
    -- For care work: value is '[REDACTED: see zk_proof]' — raw evidence is purged.
    -- For livelihood/commons: retains the original description.
    description   TEXT NOT NULL,
    hours         NUMERIC(10, 2),
    care_score    NUMERIC(10, 2),   -- Phase 9+: SCP points after multiplier.
    value_tokens  NUMERIC(20, 8),
    timestamp     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ipfs_cid      TEXT,             -- optional: link to evidence on IPFS
    -- Phase 12: ZK-SNARK proof JSON (ZKProof dataclass serialized).
    --   NULL for livelihood/commons entries where privacy is not required.
    --   REQUIRED for care work entries — a NULL here means the entry was
    --   rejected by write_ledger_entry and must not be treated as valid.
    zk_proof      TEXT             -- JSON-serialized ZKProof from MACICoordinator.
);

-- Pending Safe multi-sig transactions (HITL queue)
CREATE TABLE IF NOT EXISTS pending_transactions (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    safe_address  TEXT NOT NULL,
    to_address    TEXT NOT NULL,
    value_wei     NUMERIC(30, 0) NOT NULL DEFAULT 0,
    data          TEXT,
    nonce         INTEGER,
    status        TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'executed')),
    proposed_by   TEXT NOT NULL,
    proposed_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    agent_action_id UUID REFERENCES agent_actions(id)
);

-- ══════════════════════════════════════════════════════════════════════════════
-- Phase 10: Agent Job Descriptions (AJD Spawner)
-- ══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS agent_job_descriptions (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id            TEXT NOT NULL UNIQUE,
    name                TEXT NOT NULL,
    description         TEXT NOT NULL,
    created_by          TEXT NOT NULL,
    approved_at         TIMESTAMPTZ,
    status              TEXT NOT NULL DEFAULT 'proposed'
                        CHECK (status IN ('proposed', 'approved', 'active', 'suspended', 'revoked')),
    permissions         JSONB NOT NULL DEFAULT '[]',
    budget_limit_wei    NUMERIC(30, 0) DEFAULT 0,
    budget_period       TEXT DEFAULT 'monthly',
    multisig_threshold  INTEGER DEFAULT 1,
    node_sequence       JSONB NOT NULL,
    prompt_file         TEXT,
    ethical_ceiling      TEXT DEFAULT 'MEDIUM'
                        CHECK (ethical_ceiling IN ('LOW', 'MEDIUM', 'HIGH')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ajd_votes (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ajd_id      UUID NOT NULL REFERENCES agent_job_descriptions(id),
    voter_did   TEXT NOT NULL,
    approved    BOOLEAN NOT NULL,
    reason      TEXT,
    voted_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ══════════════════════════════════════════════════════════════════════════════
-- Phase 11: Democratic Precedent Memory (pgvector RAG)
-- ══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS democratic_precedents (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_agent    TEXT NOT NULL,
    decision_type   TEXT NOT NULL,
    original_text   TEXT NOT NULL,
    vote_result     TEXT NOT NULL,
    metadata        JSONB,
    embedding       vector(768),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_precedents_embedding
    ON democratic_precedents USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- ══════════════════════════════════════════════════════════════════════════════
-- Phase 12: ZK-Democracy Vote Tallies
-- Stores the on-chain tally commitment and ZK proof for each finalized
-- MACIVoting proposal. This is the audit trail that the Safe executor reads
-- before approving High-Impact transactions — individual votes are NEVER stored.
-- ══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS zk_vote_tallies (
    id                   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    proposal_id          INTEGER NOT NULL,          -- matches MACIVoting.sol proposalId
    proposal_description TEXT NOT NULL,
    ipfs_cid             TEXT,                      -- IPFS CID of full proposal document
    -- Tally results (aggregate only — no individual votes stored).
    yes_votes            INTEGER NOT NULL DEFAULT 0,
    no_votes             INTEGER NOT NULL DEFAULT 0,
    abstain_votes        INTEGER NOT NULL DEFAULT 0,
    total_sign_ups       INTEGER NOT NULL DEFAULT 0,
    quorum_met           BOOLEAN NOT NULL DEFAULT FALSE,
    -- On-chain anchoring.
    tally_commitment_root TEXT NOT NULL,            -- Poseidon hash committed on-chain
    tx_hash              TEXT,                      -- Transaction hash of processMessages()
    -- ZK proof for this tally (JSON-serialized ZKProof from MACICoordinator).
    -- A NULL here indicates the tally was rejected or is pending proof generation.
    zk_proof             TEXT,
    -- Status mirrors MACIVoting.ProposalStatus enum.
    status               TEXT NOT NULL DEFAULT 'active'
                         CHECK (status IN ('active', 'processing', 'finalized', 'rejected')),
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finalized_at         TIMESTAMPTZ
);

-- ══════════════════════════════════════════════════════════════════════════════
-- Phase 13: Democratic App Store
-- ══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS app_deployments (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    app_name        TEXT NOT NULL,
    docker_image    TEXT NOT NULL,
    container_id    TEXT,
    container_name  TEXT NOT NULL UNIQUE,
    port_mapping    JSONB,
    traefik_rule    TEXT,
    status          TEXT NOT NULL DEFAULT 'proposed'
                    CHECK (status IN ('proposed', 'approved', 'pulling', 'running',
                                      'stopped', 'failed', 'removed', 'removal_requested')),
    requested_by    TEXT NOT NULL,
    approved_at     TIMESTAMPTZ,
    resource_limits JSONB,
    -- Credentials stored encrypted; plain-text never written here.
    admin_creds     TEXT,           -- Encrypted credential bundle (future: age encryption).
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS app_votes (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    deployment_id   UUID NOT NULL REFERENCES app_deployments(id),
    voter_did       TEXT NOT NULL,
    approved        BOOLEAN NOT NULL,
    reason          TEXT,
    voted_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ══════════════════════════════════════════════════════════════════════════════
-- Phase 14A: Matrix Room Bridge Tracking
-- ══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS matrix_room_bridges (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    room_id     TEXT NOT NULL,
    room_alias  TEXT,
    agent_id    TEXT,
    room_type   TEXT NOT NULL CHECK (room_type IN
                    ('general', 'governance', 'treasury', 'steward', 'secretary')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS matrix_events_log (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_id        TEXT NOT NULL,
    room_id         TEXT NOT NULL,
    sender          TEXT NOT NULL,
    event_type      TEXT NOT NULL,
    content         JSONB,
    agent_action_id UUID REFERENCES agent_actions(id),
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ══════════════════════════════════════════════════════════════════════════════
-- Phase 14B: ActivityPub Federation Inbox / Outbox / Followers
-- ══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS federation_inbox (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    activity_id   TEXT NOT NULL UNIQUE,
    activity_type TEXT NOT NULL,
    actor_iri     TEXT NOT NULL,
    raw_activity  JSONB NOT NULL,
    processed     BOOLEAN DEFAULT FALSE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS federation_outbox (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    activity_id   TEXT NOT NULL UNIQUE,
    activity_type TEXT NOT NULL,
    raw_activity  JSONB NOT NULL,
    delivered     BOOLEAN DEFAULT FALSE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS federation_followers (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    local_handle TEXT NOT NULL,
    follower_iri TEXT NOT NULL,
    accepted     BOOLEAN DEFAULT FALSE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(local_handle, follower_iri)
);

-- ══════════════════════════════════════════════════════════════════════════════
-- Phase 15: Inter-Coop Escrow & Solidarity Court Arbitration
-- ══════════════════════════════════════════════════════════════════════════════

-- Mirrors IskanderEscrow.sol on-chain state for the API stub layer.
-- Production: read directly from contract events via web3.py listener.
CREATE TABLE IF NOT EXISTS escrow_contracts (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    escrow_id       TEXT NOT NULL UNIQUE,   -- on-chain uint256 cast to text
    buyer_coop      TEXT NOT NULL,          -- Safe address of buyer cooperative
    seller_coop     TEXT NOT NULL,          -- Safe address of seller cooperative
    token_address   TEXT NOT NULL,          -- ERC-20 token contract address
    amount_wei      NUMERIC(30, 0) NOT NULL,
    terms_ipfs_cid  TEXT,                   -- IPFS CID of trade terms document
    expires_at      TIMESTAMPTZ,            -- NULL = no expiry
    status          TEXT NOT NULL DEFAULT 'Active'
                    CHECK (status IN ('Active', 'Released', 'Disputed', 'Arbitrated', 'Expired')),
    has_active_case BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Solidarity Court arbitration cases.
-- One case per escrow dispute. Linked to the escrow and to the jury's
-- ActivityPub identity (stored as an IPFS CID of the JuryNomination bundle).
CREATE TABLE IF NOT EXISTS arbitration_cases (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    case_id         TEXT NOT NULL UNIQUE,
    escrow_id       TEXT NOT NULL REFERENCES escrow_contracts(escrow_id)
                        ON DELETE RESTRICT,
    complainant_did TEXT NOT NULL,
    respondent_did  TEXT NOT NULL,
    description     TEXT NOT NULL,
    evidence_cids   JSONB NOT NULL DEFAULT '[]',  -- array of IPFS CIDs
    jury_ipfs_cid   TEXT,                         -- IPFS bundle of jury nominations
    jurisdiction    TEXT CHECK (jurisdiction IN ('intra_coop', 'inter_coop')),
    status          TEXT NOT NULL DEFAULT 'filing'
                    CHECK (status IN (
                        'filing', 'jury_selection', 'deliberation',
                        'verdict_rendered', 'remedy_executed', 'dismissed'
                    )),
    -- Verdict fields (populated after human jury deliberation)
    outcome         TEXT CHECK (outcome IN ('buyer_favored', 'seller_favored', 'split', 'dismissed')),
    buyer_amount_wei  NUMERIC(30, 0),
    seller_amount_wei NUMERIC(30, 0),
    remedy_executed   BOOLEAN NOT NULL DEFAULT FALSE,
    -- Glass Box Protocol link
    agent_action_id UUID REFERENCES agent_actions(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at     TIMESTAMPTZ
);

-- Append-only trust score history.
-- Every slashTrust / restoreTrust event is mirrored here from on-chain logs.
-- Used for trend analysis, rehabilitation tracking, and member appeals.
-- The raw on-chain event is the authoritative source; this table is a cache.
CREATE TABLE IF NOT EXISTS trust_score_history (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    member_address  TEXT NOT NULL,
    member_did      TEXT,
    event_type      TEXT NOT NULL CHECK (event_type IN ('slash', 'restore', 'initial')),
    delta           SMALLINT NOT NULL,   -- negative for slash, positive for restore
    new_score       SMALLINT NOT NULL,   -- score after this event
    case_id         TEXT REFERENCES arbitration_cases(case_id) ON DELETE SET NULL,
    case_hash       TEXT,               -- keccak256 from on-chain event
    tx_hash         TEXT,               -- transaction that emitted TrustSlashed/TrustRestored
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ══════════════════════════════════════════════════════════════════════════════
-- Phase 18: Iterated Prisoner's Dilemma Auditing System
-- Game-theoretic model treating every inter-coop trade as a round in an
-- infinitely repeated Prisoner's Dilemma. Predicts cooperation pre-trade,
-- records outcomes post-trade, and enables inter-node auditing.
-- Strategy: Generous Tit-for-Tat (start cooperative, mirror last move,
-- occasionally forgive defections to prevent death spirals from noise).
-- ══════════════════════════════════════════════════════════════════════════════

-- Every escrow resolution as a cooperate/defect signal per party.
-- This is the raw event stream that feeds the reputation graph.
CREATE TABLE IF NOT EXISTS interaction_history (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    node_a            TEXT NOT NULL,       -- DID or address of party A
    node_b            TEXT NOT NULL,       -- DID or address of party B
    escrow_id         TEXT REFERENCES escrow_contracts(escrow_id)
                          ON DELETE SET NULL,
    node_a_action     TEXT NOT NULL CHECK (node_a_action IN ('cooperate', 'defect')),
    node_b_action     TEXT NOT NULL CHECK (node_b_action IN ('cooperate', 'defect')),
    escrow_outcome    TEXT NOT NULL CHECK (escrow_outcome IN (
                          'Released', 'Disputed', 'Arbitrated', 'Expired')),
    arbitration_outcome TEXT CHECK (arbitration_outcome IN (
                          'buyer_favored', 'seller_favored', 'split', 'dismissed')),
    is_meatspace      BOOLEAN NOT NULL DEFAULT FALSE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_interaction_history_pair
    ON interaction_history (node_a, node_b);
CREATE INDEX IF NOT EXISTS idx_interaction_history_created
    ON interaction_history (created_at DESC);

-- Cached per-node reputation scores. UPSERTED after each post-trade audit.
-- The off-chain complement to on-chain trust scores in CoopIdentity.sol.
CREATE TABLE IF NOT EXISTS reputation_scores (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    node_did                TEXT NOT NULL UNIQUE,
    total_interactions      INTEGER NOT NULL DEFAULT 0,
    cooperate_count         INTEGER NOT NULL DEFAULT 0,
    defect_count            INTEGER NOT NULL DEFAULT 0,
    cooperation_ratio       NUMERIC(5, 4) NOT NULL DEFAULT 0.0,
    avg_response_time_sec   NUMERIC(10, 2),
    jury_participation_rate NUMERIC(5, 4) NOT NULL DEFAULT 0.0,
    audit_compliance_rate   NUMERIC(5, 4) NOT NULL DEFAULT 1.0,
    federation_uptime       NUMERIC(5, 4),
    is_meatspace            BOOLEAN NOT NULL DEFAULT FALSE,
    peer_attestation_avg    NUMERIC(5, 2) NOT NULL DEFAULT 0.0,
    -- Phase 19: Synced from CoopIdentity.trustScore via web3.py event listener.
    on_chain_trust_score    SMALLINT DEFAULT NULL,
    linked_address          TEXT,            -- Ethereum address (Phase 19: wallet-to-DID bridge)
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Per-pair cooperation cache for pairwise GTfT strategy lookups.
CREATE TABLE IF NOT EXISTS pairwise_cooperation (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    node_a                  TEXT NOT NULL,
    node_b                  TEXT NOT NULL,
    total_interactions      INTEGER NOT NULL DEFAULT 0,
    mutual_cooperate        INTEGER NOT NULL DEFAULT 0,
    a_defect_b_cooperate    INTEGER NOT NULL DEFAULT 0,
    b_defect_a_cooperate    INTEGER NOT NULL DEFAULT 0,
    mutual_defect           INTEGER NOT NULL DEFAULT 0,
    last_a_action           TEXT CHECK (last_a_action IN ('cooperate', 'defect')),
    last_b_action           TEXT CHECK (last_b_action IN ('cooperate', 'defect')),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (node_a, node_b)
);

-- Meatspace entity attestations from peer cooperatives.
-- Provides soft reputation signals for partners without on-chain presence.
-- A bakery with excellent peer attestations scores equally against a DAO.
CREATE TABLE IF NOT EXISTS peer_attestations (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    attester_did        TEXT NOT NULL,
    subject_did         TEXT NOT NULL,
    attestation_type    TEXT NOT NULL CHECK (attestation_type IN (
                            'delivery_confirmed', 'quality_verified',
                            'ica_compliance', 'general')),
    score               SMALLINT NOT NULL CHECK (score >= 0 AND score <= 100),
    comment             TEXT,
    escrow_id           TEXT REFERENCES escrow_contracts(escrow_id)
                            ON DELETE SET NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_peer_attestations_subject
    ON peer_attestations (subject_did);

-- Inter-node audit request log. Tracks cross-federation audit exchanges.
CREATE TABLE IF NOT EXISTS audit_requests (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    request_id          TEXT NOT NULL UNIQUE,
    requesting_node     TEXT NOT NULL,
    target_node         TEXT NOT NULL,
    audit_type          TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'responded', 'refused', 'expired')),
    request_activity    JSONB,
    response_activity   JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    responded_at        TIMESTAMPTZ
);


-- ═══════════════════════════════════════════════════════════════════════════════
-- Phase 19: Custodial Treasury / Fiat Bridge — Internal Credit System
-- ═══════════════════════════════════════════════════════════════════════════════
-- The cooperative acts as custodian for off-chain (meatspace) members.
-- Credits are internal accounting units denominated in the same unit as the
-- on-chain token (xDAI equivalent). Conversion to/from on-chain tokens is
-- gated by steward multi-sig approval (HITL).

-- Per-member credit balance.
CREATE TABLE IF NOT EXISTS credit_accounts (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    member_did      TEXT NOT NULL UNIQUE,
    balance         NUMERIC(20, 8) NOT NULL DEFAULT 0.0
                    CHECK (balance >= 0),
    is_on_chain     BOOLEAN NOT NULL DEFAULT FALSE,
    linked_address  TEXT,                    -- Ethereum address if wallet-linked
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_credit_accounts_did ON credit_accounts (member_did);
CREATE INDEX IF NOT EXISTS idx_credit_accounts_address ON credit_accounts (linked_address)
    WHERE linked_address IS NOT NULL;

-- Credit transaction ledger (full audit trail).
CREATE TABLE IF NOT EXISTS credit_transactions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    from_did        TEXT,                    -- NULL for deposits
    to_did          TEXT,                    -- NULL for withdrawals
    amount          NUMERIC(20, 8) NOT NULL CHECK (amount > 0),
    tx_type         TEXT NOT NULL
                    CHECK (tx_type IN ('deposit', 'withdrawal', 'transfer', 'conversion_to_chain', 'conversion_from_chain')),
    fiat_reference  TEXT,                    -- External payment reference (bank transfer ID, etc.)
    on_chain_tx_hash TEXT,                   -- EVM tx hash for on-chain conversions
    note            TEXT,
    created_by      TEXT NOT NULL,           -- DID or address of the steward who authorized
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_credit_tx_from ON credit_transactions (from_did);
CREATE INDEX IF NOT EXISTS idx_credit_tx_to ON credit_transactions (to_did);
CREATE INDEX IF NOT EXISTS idx_credit_tx_type ON credit_transactions (tx_type);

-- Fiat deposit records (for regulatory audit trail).
CREATE TABLE IF NOT EXISTS fiat_deposits (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    member_did      TEXT NOT NULL REFERENCES credit_accounts(member_did),
    amount_fiat     NUMERIC(20, 2) NOT NULL CHECK (amount_fiat > 0),
    currency        TEXT NOT NULL DEFAULT 'USD',
    payment_method  TEXT NOT NULL DEFAULT 'bank_transfer'
                    CHECK (payment_method IN ('bank_transfer', 'cash', 'check', 'other')),
    reference_id    TEXT,                    -- External reference number
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'confirmed', 'failed', 'reversed')),
    confirmed_by    TEXT,                    -- Steward DID who confirmed
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    confirmed_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_fiat_deposits_did ON fiat_deposits (member_did);
CREATE INDEX IF NOT EXISTS idx_fiat_deposits_status ON fiat_deposits (status);

-- ══════════════════════════════════════════════════════════════════════════════
-- Phase 20: Sovereign Personal Node HITL Routing
-- Routes HITL approval requests to individual members based on DID resolution.
-- If the member runs their own Iskander node, proposals arrive via ActivityPub.
-- Otherwise, they land here for Streamlit UI pickup.
-- The individual member is sovereign — the cooperative routes, it does not gatekeep.
-- ══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS hitl_notifications (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    proposal_id     TEXT NOT NULL UNIQUE,
    member_did      TEXT NOT NULL,
    proposal_type   TEXT NOT NULL CHECK (proposal_type IN (
                        'governance', 'treasury', 'steward', 'arbitration', 'ipd')),
    summary         TEXT NOT NULL,
    safe_tx_draft   JSONB,
    voting_deadline TIMESTAMPTZ,
    callback_inbox  TEXT,
    thread_id       TEXT NOT NULL,          -- LangGraph thread_id for resumption
    agent_id        TEXT NOT NULL,          -- which agent triggered this
    route           TEXT NOT NULL CHECK (route IN ('activitypub', 'local_db')),
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'approved', 'rejected', 'expired')),
    agent_action_id UUID REFERENCES agent_actions(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    responded_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_hitl_notifications_member
    ON hitl_notifications (member_did, status);
CREATE INDEX IF NOT EXISTS idx_hitl_notifications_status
    ON hitl_notifications (status, created_at);

-- DID Document cache — avoids repeated HTTP resolution for did:web.
-- The cooperative caches DID documents to determine routing preference,
-- not to assert authority over the member's identity.
CREATE TABLE IF NOT EXISTS did_document_cache (
    did             TEXT PRIMARY KEY,
    document        JSONB NOT NULL,
    has_ap_inbox    BOOLEAN NOT NULL DEFAULT FALSE,
    ap_inbox_url    TEXT,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ══════════════════════════════════════════════════════════════════════════════
-- Phase 21: Democratic AI Model Lifecycle & Hardware-Aware Upgrades
-- Changing the cooperative's AI "brain" is a High-Impact action gated by
-- physical hardware limits and democratic consensus. This prevents members
-- from bricking the server while ensuring the OS evolves with open-source AI.
-- ══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS model_upgrade_proposals (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    model_name          TEXT NOT NULL,
    justification       TEXT NOT NULL,
    proposer_did        TEXT NOT NULL,
    target_agent_id     TEXT,                    -- NULL = global default upgrade
    previous_model      TEXT NOT NULL,
    hardware_snapshot   JSONB NOT NULL,          -- HardwareCapabilities at proposal time
    status              TEXT NOT NULL DEFAULT 'pending_vote'
                        CHECK (status IN (
                            'hardware_rejected', 'pending_vote', 'approved_pulling',
                            'pull_complete', 'pull_failed_rollback'
                        )),
    error               TEXT,
    agent_action_id     UUID REFERENCES agent_actions(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at         TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_model_proposals_status
    ON model_upgrade_proposals (status, created_at);

-- ══════════════════════════════════════════════════════════════════════════════
-- Phase 22: Fiat-Backed Solidarity Economy
-- Cooperative Fiat Tokens (cFIAT) backed 1:1 by insured fiat in a regulated
-- cooperative bank trust account. Anti-extractive: bypasses Visa/MC/Stripe,
-- returns fees to workers.
-- ══════════════════════════════════════════════════════════════════════════════

-- Fiat settlement records linking on-chain escrow to off-chain bank transfers.
CREATE TABLE IF NOT EXISTS fiat_settlements (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    escrow_id           TEXT NOT NULL,
    on_chain_amount_wei NUMERIC(30, 0) NOT NULL,
    cfiat_symbol        TEXT NOT NULL DEFAULT 'cGBP',
    settlement_action   TEXT NOT NULL CHECK (settlement_action IN ('held_on_chain', 'offramped')),
    fiat_transfer_id    TEXT,                    -- PendingTransfer.id if offramped
    bank_confirmation   TEXT,                    -- Bank tx reference if fiat was moved
    approved_by         TEXT,                    -- DID of BrightID-verified treasurer
    agent_action_id     UUID REFERENCES agent_actions(id),
    settled_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fiat_settlements_escrow
    ON fiat_settlements (escrow_id);

-- Pending fiat transfer drafts awaiting human approval.
-- The AI NEVER executes transfers — only drafts them.
CREATE TABLE IF NOT EXISTS fiat_transfer_drafts (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    to_account          TEXT NOT NULL,
    amount              NUMERIC(20, 2) NOT NULL CHECK (amount > 0),
    currency            TEXT NOT NULL DEFAULT 'GBP',
    reference           TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'drafted'
                        CHECK (status IN ('drafted', 'pending_human_approval',
                                          'approved', 'executed', 'failed')),
    approved_by         TEXT,                    -- DID of approving treasurer
    drafted_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    approved_at         TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_fiat_drafts_status
    ON fiat_transfer_drafts (status);

-- ══════════════════════════════════════════════════════════════════════════════
-- Phase 23: Stewardship Council & Delegation Ledger
-- Dynamic, federated governance layer with gSBT-weighted delegation, Impact
-- Score reputation scoring, emergency veto, and solvency circuit breaker.
-- Anti-hierarchical: steward roles expire automatically when contribution
-- scores drop below the protocol-defined threshold.
-- ══════════════════════════════════════════════════════════════════════════════

-- Off-chain cache of Impact Scores computed by the StewardshipScorer agent.
-- Pushed to the StewardshipLedger contract via the Oracle after computation.
CREATE TABLE IF NOT EXISTS impact_scores (
    id                              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    node_did                        TEXT NOT NULL,
    node_address                    TEXT,
    historical_contribution_value   NUMERIC(20, 8) NOT NULL DEFAULT 0.0,
    ecosystem_total_value           NUMERIC(20, 8) NOT NULL DEFAULT 0.0,
    ethical_audit_score             NUMERIC(5, 4) NOT NULL DEFAULT 0.0,
    impact_score                    NUMERIC(5, 4) NOT NULL DEFAULT 0.0,
    is_eligible_steward             BOOLEAN NOT NULL DEFAULT FALSE,
    agent_action_id                 UUID REFERENCES agent_actions(id),
    computed_at                     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    pushed_on_chain                 BOOLEAN NOT NULL DEFAULT FALSE,
    on_chain_tx_hash                TEXT
);

CREATE INDEX IF NOT EXISTS idx_impact_scores_did
    ON impact_scores (node_did);
CREATE INDEX IF NOT EXISTS idx_impact_scores_eligible
    ON impact_scores (is_eligible_steward)
    WHERE is_eligible_steward = TRUE;

-- Mirror of on-chain delegation events for API queries and audit trail.
CREATE TABLE IF NOT EXISTS delegation_events (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    delegator_did       TEXT NOT NULL,
    delegator_address   TEXT NOT NULL,
    steward_did         TEXT,
    steward_address     TEXT NOT NULL,
    event_type          TEXT NOT NULL CHECK (event_type IN ('delegate', 'revoke', 'auto_revoke')),
    tx_hash             TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_delegation_events_delegator
    ON delegation_events (delegator_address);
CREATE INDEX IF NOT EXISTS idx_delegation_events_steward
    ON delegation_events (steward_address);

-- Audit trail for steward threshold changes proposed by the StewardshipScorer.
CREATE TABLE IF NOT EXISTS steward_threshold_history (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    threshold_value NUMERIC(5, 4) NOT NULL,
    proposed_by     TEXT NOT NULL,           -- agent_id or member_did
    rationale       TEXT NOT NULL,
    agent_action_id UUID REFERENCES agent_actions(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Glass Box Protocol records for cross-node Council decisions.
-- Every Council decision MUST have a rationale filed here for auditability.
CREATE TABLE IF NOT EXISTS council_rationale (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    decision_type       TEXT NOT NULL,
    description         TEXT NOT NULL,
    rationale_ipfs_cid  TEXT NOT NULL,       -- Full rationale on IPFS
    submitted_by        TEXT NOT NULL,       -- DID of the steward
    ica_principles      TEXT[],              -- ICA Cooperative Principles this decision supports
    agent_action_id     UUID REFERENCES agent_actions(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Emergency veto filings mirrored from on-chain events.
-- Any member can veto a Council decision by citing ICA Principle violations.
CREATE TABLE IF NOT EXISTS veto_records (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    proposal_id         TEXT NOT NULL,
    vetoer_did          TEXT NOT NULL,
    vetoer_address      TEXT NOT NULL,
    rationale_ipfs_cid  TEXT NOT NULL,       -- Glass Box: full rationale on IPFS
    cited_principles    TEXT[],              -- ICA Cooperative Principles cited as violated
    status              TEXT NOT NULL DEFAULT 'filed'
                        CHECK (status IN ('filed', 'under_review', 'upheld', 'dismissed')),
    tx_hash             TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_veto_records_proposal
    ON veto_records (proposal_id);

-- ══════════════════════════════════════════════════════════════════════════════
-- Phase 24: Energy Gate / Hearth Driver
-- Hardware-in-the-loop scheduling: records energy-level transitions so the
-- cooperative can audit when and why agent activity was throttled or halted.
-- ══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS energy_events (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    level           TEXT NOT NULL CHECK (level IN ('GREEN', 'YELLOW', 'RED')),
    previous_level  TEXT CHECK (previous_level IN ('GREEN', 'YELLOW', 'RED')),
    battery_pct     NUMERIC(5, 2),
    on_ac           BOOLEAN,
    action_taken    TEXT,                    -- e.g. 'throttled_agents', 'halted_inference'
    agent_action_id UUID REFERENCES agent_actions(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_energy_events_level
    ON energy_events (level);

-- ══════════════════════════════════════════════════════════════════════════════
-- Phase 25: Mesh Archive / Sovereign Data Fabric
-- Content-addressed IPFS storage with SBT-gated access control and CausalEvent
-- pinning for Glass Box Protocol immutability.
-- ══════════════════════════════════════════════════════════════════════════════

-- Causal events pinned to IPFS with on-chain anchor hashes.
CREATE TABLE IF NOT EXISTS causal_events (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type          TEXT NOT NULL,
    source_agent_id     TEXT NOT NULL,
    ipfs_cid            TEXT NOT NULL,
    audience            TEXT NOT NULL DEFAULT 'federation'
                        CHECK (audience IN ('federation', 'council', 'node')),
    on_chain_anchor     TEXT,                    -- Merkle root or tx hash
    agent_action_id     UUID REFERENCES agent_actions(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_causal_events_cid
    ON causal_events (ipfs_cid);
CREATE INDEX IF NOT EXISTS idx_causal_events_type
    ON causal_events (event_type);

-- Delta-sync log for federation CID replication.
CREATE TABLE IF NOT EXISTS mesh_sync_log (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    peer_did        TEXT NOT NULL,
    direction       TEXT NOT NULL CHECK (direction IN ('push', 'pull')),
    cid             TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'synced', 'denied', 'failed')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mesh_sync_peer
    ON mesh_sync_log (peer_did);

-- ══════════════════════════════════════════════════════════════════════════════
-- Phase 26: Fiat-Crypto Bridge Agent
-- Agent-level solvency enforcement and oracle snapshots extending Phase 22.
-- ══════════════════════════════════════════════════════════════════════════════

-- Fiat mint/burn operations executed by the Fiat Gateway Agent.
CREATE TABLE IF NOT EXISTS fiat_operations (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    operation_type      TEXT NOT NULL CHECK (operation_type IN ('mint', 'burn')),
    amount_wei          NUMERIC(78, 0) NOT NULL,
    reserve_balance     NUMERIC(20, 2),
    solvency_ratio      NUMERIC(10, 6),
    tx_hash             TEXT,
    initiated_by        TEXT NOT NULL,       -- agent_id or member_did
    approved_by         TEXT,                -- DID of approving treasurer (HITL)
    agent_action_id     UUID REFERENCES agent_actions(id),
    status              TEXT NOT NULL DEFAULT 'proposed'
                        CHECK (status IN ('proposed', 'approved', 'executed', 'failed')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fiat_operations_status
    ON fiat_operations (status);

-- ══════════════════════════════════════════════════════════════════════════════
-- Fix 2: ICA Verification Log
-- Second-pass adversarial rationale verification against ICA Cooperative Principles.
-- ══════════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS ica_verification_log (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_action_id     UUID REFERENCES agent_actions(id),
    violation_score     INTEGER NOT NULL CHECK (violation_score BETWEEN 0 AND 100),
    flagged_principles  TEXT[] DEFAULT '{}',
    explanation         TEXT,
    verifier_model      TEXT DEFAULT 'heuristic',
    verifier_version    TEXT NOT NULL,
    payload_hash        TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_ica_log_score
    ON ica_verification_log (violation_score DESC);
CREATE INDEX IF NOT EXISTS idx_ica_log_action
    ON ica_verification_log (agent_action_id);

-- Periodic solvency snapshots for audit trail.
CREATE TABLE IF NOT EXISTS solvency_snapshots (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    fiat_reserve        NUMERIC(20, 2) NOT NULL,
    total_escrow_wei    NUMERIC(78, 0) NOT NULL,
    cfiat_supply_wei    NUMERIC(78, 0) NOT NULL,
    solvency_ratio      NUMERIC(10, 6) NOT NULL,
    circuit_breaker_active BOOLEAN NOT NULL DEFAULT FALSE,
    agent_action_id     UUID REFERENCES agent_actions(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ══════════════════════════════════════════════════════════════════════════════
-- Fix 6: HITL Rate Limiter
-- ══════════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS hitl_rate_log (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_address    TEXT NOT NULL,
    endpoint        TEXT NOT NULL,
    requested_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_hitl_rate_log_lookup
    ON hitl_rate_log (user_address, endpoint, requested_at);

-- ══════════════════════════════════════════════════════════════════════════════
-- Fix 3: Federated Pinning Protocol + Geo-Diversity
-- Receipts from mesh peers confirming CID replication, and node metadata for
-- diversity-aware peer selection.
-- ══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS pin_receipts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    cid TEXT NOT NULL,
    peer_did TEXT NOT NULL,
    receipt_signature TEXT,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (cid, peer_did)
);
CREATE INDEX IF NOT EXISTS idx_pin_receipts_cid ON pin_receipts (cid);

CREATE TABLE IF NOT EXISTS node_metadata (
    peer_did TEXT PRIMARY KEY,
    region TEXT NOT NULL DEFAULT 'unknown',
    isp TEXT NOT NULL DEFAULT 'unknown',
    power_source TEXT NOT NULL DEFAULT 'unknown',
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ══════════════════════════════════════════════════════════════════════════════
-- Fix 7: Boundary Agent / Embassy
-- Federation hardening: trust quarantine, ontology translation, governance
-- verification, and causal buffering for all inbound foreign SDC data.
-- ══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS foreign_identity_trust (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    actor_iri TEXT NOT NULL UNIQUE,
    first_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen TIMESTAMPTZ,
    interaction_count INTEGER NOT NULL DEFAULT 0,
    cooperation_count INTEGER NOT NULL DEFAULT 0,
    quarantine_count INTEGER NOT NULL DEFAULT 0,
    trust_penalty NUMERIC(5,4) NOT NULL DEFAULT 0.3,
    declared_capabilities JSONB DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS boundary_quarantine (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    actor_iri TEXT NOT NULL,
    activity_type TEXT NOT NULL,
    quarantine_reason TEXT NOT NULL,
    quarantined_fields JSONB DEFAULT '{}',
    source_framework TEXT DEFAULT 'unknown',
    reviewed BOOLEAN NOT NULL DEFAULT FALSE,
    resolution TEXT CHECK (resolution IN ('accepted','rejected','mapping_added',NULL)),
    agent_action_id UUID REFERENCES agent_actions(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ontology_mappings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_framework TEXT NOT NULL,
    source_field TEXT NOT NULL,
    source_value TEXT NOT NULL,
    target_field TEXT NOT NULL,
    target_value TEXT NOT NULL,
    created_by TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (source_framework, source_field, source_value)
);

CREATE TABLE IF NOT EXISTS causal_buffer (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    activity_type TEXT NOT NULL,
    actor_iri TEXT NOT NULL,
    causal_key TEXT NOT NULL,
    required_types TEXT[] NOT NULL,
    raw_activity JSONB NOT NULL,
    buffered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    released_at TIMESTAMPTZ,
    expired BOOLEAN NOT NULL DEFAULT FALSE
);

-- ═══════════════════════════════════════════════════════════════════════════════
-- IKC: Iskander Knowledge Commons — Decentralized University
-- ═══════════════════════════════════════════════════════════════════════════════

-- Knowledge assets: content-addressed entries pinned to IPFS.
-- TOMBSTONE-ONLY: rows are never deleted; status changes via knowledge_status_log.
CREATE TABLE IF NOT EXISTS knowledge_assets (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    cid                 TEXT NOT NULL,
    author_did          TEXT NOT NULL,
    version             INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
    status              TEXT NOT NULL DEFAULT 'Active'
                        CHECK (status IN ('Active', 'Legacy', 'Tombstoned', 'DeepFreeze')),
    title               TEXT NOT NULL,
    description         TEXT,
    content_hash        TEXT,
    metadata_cid        TEXT,
    dependency_manifest TEXT[] NOT NULL DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_knowledge_assets_cid ON knowledge_assets (cid);
CREATE INDEX IF NOT EXISTS idx_knowledge_assets_status ON knowledge_assets (status);
CREATE INDEX IF NOT EXISTS idx_knowledge_assets_author ON knowledge_assets (author_did);

-- Dependency edges: from_cid depends_on to_cid.
-- CHECK prevents self-references; UNIQUE prevents duplicate edges.
CREATE TABLE IF NOT EXISTS knowledge_dependencies (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    from_cid    TEXT NOT NULL,
    to_cid      TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (from_cid, to_cid),
    CHECK (from_cid != to_cid)
);

CREATE INDEX IF NOT EXISTS idx_knowledge_deps_to ON knowledge_dependencies (to_cid);
CREATE INDEX IF NOT EXISTS idx_knowledge_deps_from ON knowledge_dependencies (from_cid);

-- Curator debate records: tracks each curation proposal and its outcome.
CREATE TABLE IF NOT EXISTS curator_debates (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    asset_cid           TEXT NOT NULL,
    proposed_status     TEXT NOT NULL,
    consensus_status    TEXT NOT NULL DEFAULT 'in_progress'
                        CHECK (consensus_status IN (
                            'in_progress', 'unanimous_approve', 'unanimous_reject',
                            'escalated', 'paused', 'rejected_downstream_deps',
                            'council_rejected'
                        )),
    votes               JSONB NOT NULL DEFAULT '[]',
    rationale_log       JSONB NOT NULL DEFAULT '[]',
    thread_id           TEXT NOT NULL,
    escalation_signal   BOOLEAN NOT NULL DEFAULT FALSE,
    agent_action_id     UUID REFERENCES agent_actions(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at         TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_curator_debates_asset ON curator_debates (asset_cid);
CREATE INDEX IF NOT EXISTS idx_curator_debates_status ON curator_debates (consensus_status);

-- Status change audit log: every status transition is recorded here.
-- TOMBSTONE-ONLY: this table is append-only. No rows are ever deleted.
CREATE TABLE IF NOT EXISTS knowledge_status_log (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    asset_cid       TEXT NOT NULL,
    previous_status TEXT NOT NULL,
    new_status      TEXT NOT NULL,
    changed_by      TEXT NOT NULL,
    rationale       TEXT NOT NULL,
    metadata_cid    TEXT,
    agent_action_id UUID REFERENCES agent_actions(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_knowledge_status_log_cid
    ON knowledge_status_log (asset_cid);


-- ════════════════════════════════════════════════════════════════════════════
-- DIPLOMATIC EMBASSY: Foreign Reputation System, Quarantine Sandbox, RITL
-- ════════════════════════════════════════════════════════════════════════════

-- Foreign SDC reputation profiles.
-- Mirrors ForeignReputation.sol SDCProfile struct for off-chain queries.
CREATE TABLE IF NOT EXISTS foreign_sdc_profiles (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sdc_did             TEXT NOT NULL UNIQUE,
    sdc_id_hash         TEXT NOT NULL,
    raw_score           INTEGER NOT NULL CHECK (raw_score >= 0 AND raw_score <= 10000),
    last_updated        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    force_quarantined   BOOLEAN NOT NULL DEFAULT FALSE,
    tx_count            INTEGER NOT NULL DEFAULT 0,
    registered_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_foreign_sdc_did ON foreign_sdc_profiles (sdc_did);

-- Valueflows transaction records anchoring FRS score changes.
CREATE TABLE IF NOT EXISTS frs_transactions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sdc_did         TEXT NOT NULL REFERENCES foreign_sdc_profiles(sdc_did),
    score_delta     INTEGER NOT NULL CHECK (score_delta >= -500 AND score_delta <= 500),
    tx_cid          TEXT NOT NULL,
    rationale       TEXT NOT NULL,
    previous_score  INTEGER NOT NULL,
    new_score       INTEGER NOT NULL,
    previous_tier   INTEGER NOT NULL CHECK (previous_tier >= 0 AND previous_tier <= 3),
    new_tier        INTEGER NOT NULL CHECK (new_tier >= 0 AND new_tier <= 3),
    agent_action_id UUID REFERENCES agent_actions(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_frs_transactions_sdc ON frs_transactions (sdc_did);
CREATE INDEX IF NOT EXISTS idx_frs_transactions_cid ON frs_transactions (tx_cid);

-- Quarantine sandbox: external assets pending curator review.
-- TOMBSTONE-ONLY: rejected assets remain here permanently.
CREATE TABLE IF NOT EXISTS quarantine_sandbox (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_sdc_did      TEXT NOT NULL,
    source_sdc_tier     INTEGER NOT NULL CHECK (source_sdc_tier >= 0 AND source_sdc_tier <= 3),
    original_cid        TEXT NOT NULL,
    local_cid           TEXT,
    title               TEXT NOT NULL,
    description         TEXT,
    status              TEXT NOT NULL CHECK (status IN (
        'PendingReview', 'UnderReview', 'Admitted', 'Rejected', 'Expired'
    )) DEFAULT 'PendingReview',
    collision_report    JSONB,
    promoted_asset_cid  TEXT,
    agent_action_id     UUID REFERENCES agent_actions(id),
    ingested_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_at         TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_quarantine_status ON quarantine_sandbox (status);
CREATE INDEX IF NOT EXISTS idx_quarantine_sdc ON quarantine_sandbox (source_sdc_did);

-- RITL peer review submissions.
CREATE TABLE IF NOT EXISTS research_submissions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    asset_cid       TEXT NOT NULL,
    author_did      TEXT NOT NULL,
    title           TEXT NOT NULL,
    abstract        TEXT,
    field_tags      TEXT[],
    blind_mode      BOOLEAN NOT NULL DEFAULT FALSE,
    thread_id       TEXT,
    status          TEXT NOT NULL CHECK (status IN (
        'submitted', 'under_review', 'accepted', 'minor_revisions',
        'major_revisions', 'rejected'
    )) DEFAULT 'submitted',
    agent_action_id UUID REFERENCES agent_actions(id),
    submitted_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at     TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_research_submissions_cid ON research_submissions (asset_cid);
CREATE INDEX IF NOT EXISTS idx_research_submissions_status ON research_submissions (status);

-- RITL peer review rounds and individual reviews.
CREATE TABLE IF NOT EXISTS peer_reviews (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    submission_id   UUID NOT NULL REFERENCES research_submissions(id),
    round_number    INTEGER NOT NULL CHECK (round_number >= 1),
    reviewer_id     TEXT NOT NULL,
    dimension       TEXT NOT NULL CHECK (dimension IN (
        'Rigor', 'Novelty', 'Ethics', 'Reproducibility'
    )),
    verdict         TEXT NOT NULL CHECK (verdict IN (
        'accept', 'minor_revisions', 'major_revisions', 'reject'
    )),
    score           INTEGER NOT NULL CHECK (score >= 0 AND score <= 100),
    strengths       JSONB NOT NULL DEFAULT '[]',
    weaknesses      JSONB NOT NULL DEFAULT '[]',
    questions       JSONB NOT NULL DEFAULT '[]',
    rationale       TEXT NOT NULL,
    blind_mode      BOOLEAN NOT NULL DEFAULT FALSE,
    agent_action_id UUID REFERENCES agent_actions(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_peer_reviews_submission ON peer_reviews (submission_id);

-- Socratic cross-examination exchanges.
CREATE TABLE IF NOT EXISTS socratic_exchanges (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    submission_id   UUID NOT NULL REFERENCES research_submissions(id),
    round_number    INTEGER NOT NULL CHECK (round_number >= 1),
    question        TEXT NOT NULL,
    asked_by        TEXT NOT NULL,
    response        TEXT,
    responded_by    TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_socratic_exchanges_submission ON socratic_exchanges (submission_id);

-- ══════════════════════════════════════════════════════════════════════════════
-- Credential Embassy — W3C VC Verification & Internal Attestations
-- ══════════════════════════════════════════════════════════════════════════════

-- Trusted issuer keys (Python-side mirror of on-chain TrustRegistry.sol).
CREATE TABLE IF NOT EXISTS trusted_issuers (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    key_fingerprint TEXT NOT NULL UNIQUE,
    issuer_did      TEXT NOT NULL,
    issuer_name     TEXT NOT NULL,
    key_type        TEXT NOT NULL,
    active          BOOLEAN NOT NULL DEFAULT TRUE,
    registered_by   TEXT NOT NULL,
    registered_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at      TIMESTAMPTZ,
    revocation_rationale TEXT,
    agent_action_id UUID REFERENCES agent_actions(id)
);

CREATE INDEX IF NOT EXISTS idx_trusted_issuers_active ON trusted_issuers (active);
CREATE INDEX IF NOT EXISTS idx_trusted_issuers_did ON trusted_issuers (issuer_did);

-- Internal attestations (SBT equivalents minted from verified W3C VCs).
-- TOMBSTONE-ONLY: attestations are never deleted, only flagged as Tombstoned.
CREATE TABLE IF NOT EXISTS identity_attestations (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    attestation_id      TEXT NOT NULL UNIQUE,
    holder_did          TEXT NOT NULL,
    issuer_did          TEXT NOT NULL,
    issuer_name         TEXT NOT NULL,
    key_fingerprint     TEXT NOT NULL,
    credential_type     TEXT NOT NULL,
    verified_role       TEXT NOT NULL,
    verified_institution TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'Active'
                        CHECK (status IN ('Active', 'Tombstoned')),
    mesh_cid            TEXT,
    causal_event_cid    TEXT,
    zk_attestation      JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    tombstoned_at       TIMESTAMPTZ,
    agent_action_id     UUID REFERENCES agent_actions(id)
);

CREATE INDEX IF NOT EXISTS idx_attestations_holder ON identity_attestations (holder_did);
CREATE INDEX IF NOT EXISTS idx_attestations_issuer_key ON identity_attestations (key_fingerprint);
CREATE INDEX IF NOT EXISTS idx_attestations_status ON identity_attestations (status);

-- Credential verification log (audit trail for all VC verification attempts).
CREATE TABLE IF NOT EXISTS vc_verification_log (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    credential_id   TEXT,
    issuer_did      TEXT NOT NULL,
    key_fingerprint TEXT,
    valid           BOOLEAN NOT NULL,
    error           TEXT,
    credential_type TEXT,
    subject_role    TEXT,
    verified_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    agent_action_id UUID REFERENCES agent_actions(id)
);

CREATE INDEX IF NOT EXISTS idx_vc_log_issuer ON vc_verification_log (issuer_did);
CREATE INDEX IF NOT EXISTS idx_vc_log_valid ON vc_verification_log (valid);

-- ═══════════════════════════════════════════════════════════════════════════════
-- Genesis Boot Sequence (Phase: Genesis)
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS genesis_state (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    mode            TEXT CHECK (mode IN ('solo_node', 'legacy_import', 'new_founding')),
    node_type       TEXT CHECK (node_type IN ('cooperative', 'solo')),
    boot_phase      TEXT NOT NULL DEFAULT 'pre-genesis',
    boot_complete   BOOLEAN NOT NULL DEFAULT FALSE,
    genesis_manifest_cid TEXT,
    constitution_cid     TEXT,
    founding_tx_hash     TEXT,
    safe_address         TEXT,
    thread_id            TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS founder_registrations (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    did             TEXT NOT NULL UNIQUE,
    address         TEXT NOT NULL,
    name            TEXT NOT NULL,
    founder_token_hash TEXT NOT NULL,
    sbt_token_id    INTEGER,
    ratified        BOOLEAN NOT NULL DEFAULT FALSE,
    registered_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_founder_registrations_did ON founder_registrations(did);

CREATE TABLE IF NOT EXISTS regulatory_updates (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_federation_did TEXT NOT NULL,
    legislation_reference TEXT NOT NULL,
    severity        TEXT NOT NULL CHECK (severity IN ('Advisory', 'Mandatory', 'Urgent')),
    effective_date  TIMESTAMPTZ NOT NULL,
    proposed_rules  JSONB NOT NULL DEFAULT '[]'::jsonb,
    affected_rule_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    ingested_via    TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'approved', 'rejected')),
    agent_action_id UUID REFERENCES agent_actions(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at     TIMESTAMPTZ
);

-- ═══════════════════════════════════════════════════════════════════════════
-- Phase A: Native Deliberation System (Loomio-equivalent)
-- ═══════════════════════════════════════════════════════════════════════════

-- Sub-groups (working groups within the cooperative)
CREATE TABLE IF NOT EXISTS sub_groups (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    slug        TEXT UNIQUE NOT NULL,       -- e.g. "finance-committee"
    name        TEXT NOT NULL,
    description TEXT,
    created_by  TEXT NOT NULL,              -- member DID
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sub_group_members (
    sub_group_id UUID NOT NULL REFERENCES sub_groups(id) ON DELETE CASCADE,
    member_did   TEXT NOT NULL,
    role         TEXT NOT NULL DEFAULT 'member'
                 CHECK (role IN ('member', 'coordinator')),
    joined_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (sub_group_id, member_did)
);

-- Deliberation threads (Loomio Discussions)
CREATE TABLE IF NOT EXISTS deliberation_threads (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title            TEXT NOT NULL,
    context          TEXT NOT NULL DEFAULT '',  -- rich-text body framing the topic
    author_did       TEXT NOT NULL,
    sub_group_id     UUID REFERENCES sub_groups(id) ON DELETE SET NULL,
    tags             TEXT[] NOT NULL DEFAULT '{}',
    status           TEXT NOT NULL DEFAULT 'open'
                     CHECK (status IN ('open', 'closed', 'pinned')),
    ai_context_draft TEXT,                      -- DiscussionAgent draft before human edit
    agent_action_id  UUID REFERENCES agent_actions(id),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_threads_author    ON deliberation_threads(author_did);
CREATE INDEX IF NOT EXISTS idx_threads_status    ON deliberation_threads(status);
CREATE INDEX IF NOT EXISTS idx_threads_subgroup  ON deliberation_threads(sub_group_id);
CREATE INDEX IF NOT EXISTS idx_threads_tags      ON deliberation_threads USING GIN(tags);

-- Comments within threads
CREATE TABLE IF NOT EXISTS thread_comments (
    id        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    thread_id UUID NOT NULL REFERENCES deliberation_threads(id) ON DELETE CASCADE,
    author_did TEXT NOT NULL,
    parent_id  UUID REFERENCES thread_comments(id) ON DELETE CASCADE,  -- NULL = top-level
    body       TEXT NOT NULL,
    edited_at  TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_comments_thread ON thread_comments(thread_id, created_at);

-- Emoji reactions on comments
CREATE TABLE IF NOT EXISTS thread_reactions (
    comment_id  UUID NOT NULL REFERENCES thread_comments(id) ON DELETE CASCADE,
    member_did  TEXT NOT NULL,
    emoji       TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (comment_id, member_did, emoji)
);

-- Track who has read each thread
CREATE TABLE IF NOT EXISTS thread_seen (
    thread_id    UUID NOT NULL REFERENCES deliberation_threads(id) ON DELETE CASCADE,
    member_did   TEXT NOT NULL,
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (thread_id, member_did)
);

-- Proposals attached to threads
CREATE TABLE IF NOT EXISTS deliberation_proposals (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    thread_id    UUID NOT NULL REFERENCES deliberation_threads(id) ON DELETE CASCADE,
    title        TEXT NOT NULL,
    body         TEXT NOT NULL,
    process_type TEXT NOT NULL
                 CHECK (process_type IN (
                     'sense_check', 'advice', 'consent', 'consensus',
                     'choose', 'score', 'allocate', 'rank', 'time_poll'
                 )),
    options      JSONB,               -- for choose/score/allocate/rank/time_poll
    quorum_pct   INTEGER NOT NULL DEFAULT 0 CHECK (quorum_pct BETWEEN 0 AND 100),
    closing_at   TIMESTAMPTZ,
    status       TEXT NOT NULL DEFAULT 'open'
                 CHECK (status IN ('open', 'closed', 'withdrawn')),
    ai_draft     TEXT,                -- ProposalAgent draft before human edit
    author_did   TEXT NOT NULL,
    agent_action_id UUID REFERENCES agent_actions(id),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_proposals_thread ON deliberation_proposals(thread_id);
CREATE INDEX IF NOT EXISTS idx_proposals_status ON deliberation_proposals(status, closing_at);

-- Stances (member votes with reasons)
CREATE TABLE IF NOT EXISTS proposal_stances (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    proposal_id UUID NOT NULL REFERENCES deliberation_proposals(id) ON DELETE CASCADE,
    member_did  TEXT NOT NULL,
    stance      TEXT NOT NULL,        -- 'agree'|'abstain'|'disagree'|'block' or option key
    score       INTEGER,              -- for score/allocate polls
    rank_order  JSONB,                -- for rank polls [{option_id, position}]
    reason      TEXT,                 -- member's stated reason (encouraged, not required)
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (proposal_id, member_did)  -- one stance per member per proposal
);

CREATE INDEX IF NOT EXISTS idx_stances_proposal ON proposal_stances(proposal_id);

-- Outcome statements (recorded after proposals close)
CREATE TABLE IF NOT EXISTS decision_outcomes (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    proposal_id   UUID NOT NULL UNIQUE REFERENCES deliberation_proposals(id) ON DELETE CASCADE,
    statement     TEXT NOT NULL,
    decision_type TEXT NOT NULL
                  CHECK (decision_type IN ('passed', 'rejected', 'withdrawn', 'no_quorum')),
    precedent_id  UUID REFERENCES democratic_precedents(id),  -- pgvector memory link
    ai_draft      TEXT,               -- OutcomeAgent draft before human confirms
    stated_by     TEXT NOT NULL,      -- DID of member who confirmed the outcome
    agent_action_id UUID REFERENCES agent_actions(id),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Tasks assigned from threads or outcomes
CREATE TABLE IF NOT EXISTS thread_tasks (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    thread_id    UUID NOT NULL REFERENCES deliberation_threads(id) ON DELETE CASCADE,
    outcome_id   UUID REFERENCES decision_outcomes(id) ON DELETE SET NULL,
    title        TEXT NOT NULL,
    assignee_did TEXT,                -- NULL = unassigned
    due_date     DATE,
    done         BOOLEAN NOT NULL DEFAULT FALSE,
    done_at      TIMESTAMPTZ,
    created_by   TEXT NOT NULL,
    agent_action_id UUID REFERENCES agent_actions(id),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tasks_thread   ON thread_tasks(thread_id);
CREATE INDEX IF NOT EXISTS idx_tasks_assignee ON thread_tasks(assignee_did) WHERE done = FALSE;
CREATE INDEX IF NOT EXISTS idx_regulatory_updates_status ON regulatory_updates(status);
