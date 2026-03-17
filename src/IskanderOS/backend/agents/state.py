"""
Shared LangGraph state types for all Iskander agents.

All agents use TypedDict state so LangGraph can checkpoint and resume
at HITL breakpoints without losing context.
"""

from __future__ import annotations

from typing import Any, Annotated
from typing_extensions import TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """Base state shared across all Iskander agents."""
    messages:       Annotated[list, add_messages]
    agent_id:       str
    action_log:     list[dict[str, Any]]   # Glass Box Protocol records
    error:          str | None


class InventoryState(AgentState):
    """State for the Web3 Inventory Agent."""
    resources:      list[dict[str, Any]]   # REA Economic Resources
    rea_report:     dict[str, Any] | None


class ContributionState(AgentState):
    """State for the Steward (DisCO Contributory Accounting) Agent."""
    raw_contribution: dict[str, Any] | None
    classified_stream: str | None          # livelihood | care | commons
    ledger_entry:      dict[str, Any] | None


class ContributionStateV2(AgentState):
    """State for the upgraded Steward Agent v2 (Phase 9).

    Extends the base contribution state with Care Work quantification
    and a circuit-breaker field for conflict resolution.
    """
    raw_contribution:     dict[str, Any] | None
    classified_stream:    str | None            # livelihood | care | commons
    care_score:           float | None          # synergistic contribution points
    conflict_resolution:  dict[str, Any] | None # circuit breaker output
    ledger_entry:         dict[str, Any] | None
    requires_human_token: bool


class GovernanceState(AgentState):
    """State for the HITL Governance Agent."""
    proposal:           dict[str, Any] | None   # human-submitted proposal
    safe_tx_draft:      dict[str, Any] | None   # unsigned Safe tx
    hitl_approved:      bool | None             # set at HITL breakpoint
    rejection_reason:   str | None


class SecretaryState(AgentState):
    """State for the Secretary Agent (Phase 9).

    Handles meeting summaries, consensus extraction, and ActivityPub
    governance broadcasts to federated sister cooperatives.
    """
    meeting_transcript:     str | None
    summary:                str | None
    consensus_items:        list[dict[str, Any]]
    activitypub_broadcast:  dict[str, Any] | None


class TreasuryState(AgentState):
    """State for the Finance & Treasury Agent (Phase 9).

    Enforces Mondragon pay-ratio caps and requires HITL approval for all
    external payments.  Drafts unsigned Safe multi-sig transactions.
    """
    payment_request:      dict[str, Any] | None
    mondragon_check:      dict[str, Any] | None   # ratio validation result
    safe_tx_draft:        dict[str, Any] | None
    hitl_approved:        bool | None
    requires_human_token: bool


class ProcurementState(AgentState):
    """State for the Procurement Agent (Phase 9).

    Manages supply-chain sourcing with preference for cooperative vendors.
    Outputs Valueflows/REA EconomicEvents.
    """
    purchase_request:   dict[str, Any] | None
    vendor_candidates:  list[dict[str, Any]]
    selected_vendor:    dict[str, Any] | None
    rea_order:          dict[str, Any] | None    # Valueflows EconomicEvent


class ProvisionerState(AgentState):
    """State for the Provisioner Agent (Phase 13).

    Manages the democratic app deployment lifecycle:
      parse_app_request → search_app_catalog → propose_deployment
      → [HITL: human_vote_app]
      → pull_image → deploy_container → configure_proxy → generate_credentials
    """
    app_request:          dict[str, Any] | None
    catalog_matches:      list[dict[str, Any]]
    deployment_spec:      dict[str, Any] | None  # Compiled DeploymentSpec (no creds in log).
    container_id:         str | None             # Docker container ID after successful deploy.
    proxy_configured:     bool                   # True once Traefik labels are confirmed.
    admin_credentials:    dict[str, Any] | None  # Delivered to requesting member; not logged.
    requires_human_token: bool


class ICAVettingState(AgentState):
    """State for the ICA Ethics Vetting Agent (Phase 17).

    Evaluates potential trading partners — on-chain cooperatives, off-chain
    meatspace businesses, and federated peers — against the 7 ICA Cooperative
    Principles.  Outputs a per-principle compliance score and a composite
    value matrix ranking all candidates.

    Graph:
      intake_partner → gather_on_chain_signals → gather_off_chain_signals
        → assess_ica_principles → compute_value_matrix
        → [conditional: HITL if any principle scores FAIL] → emit_report → END
    """
    partner_query:          dict[str, Any] | None   # Sector need + search parameters
    candidate_partners:     list[dict[str, Any]]     # Discovered on/off-chain entities
    on_chain_signals:       list[dict[str, Any]]     # Trust scores, escrow history, SBT data
    off_chain_signals:      list[dict[str, Any]]     # Federation metadata, public records
    principle_assessments:  list[dict[str, Any]]     # Per-partner, per-principle scores
    value_matrix:           dict[str, Any] | None    # Composite ranked matrix
    vetting_report:         dict[str, Any] | None    # Final human-readable report
    requires_human_token:   bool
    # Phase 18: IPD cooperation predictions injected by enrich_with_ipd_prediction.
    ipd_predictions:        list[dict[str, Any]]     # Per-candidate cooperation_probability + strategy


class ArbitrationState(AgentState):
    """State for the Arbitrator Agent (Phase 15 — Solidarity Court).

    Graph:
      receive_dispute → assess_jurisdiction
      → [conditional: intra_coop → human_jury_deliberation
                       inter_coop → request_jury_federation → human_jury_deliberation]
      → [HITL: human_jury_deliberation]
      → record_verdict → execute_remedy → END

    FUNDAMENTAL CONSTRAINT: requires_human_token MUST be True before
    record_verdict is reached. The human_jury_deliberation HITL breakpoint
    is MANDATORY and enforced by interrupt_before in the compiled graph.
    """
    dispute:              dict[str, Any] | None  # DisputeCreate fields + case_id
    evidence:             list[str]              # IPFS CIDs of evidence artefacts
    jury_pool:            list[dict[str, Any]]   # All JuryNomination responses received
    jury_selected:        list[dict[str, Any]]   # Deterministically selected jury members
    verdict:              dict[str, Any] | None  # Set by human jury via POST /verdict
    escrow_id:            str | None             # Linked escrow contract ID
    remedy_executed:      bool                   # True after executeVerdict() stub
    requires_human_token: bool                   # HITL gate — must be False before record_verdict
    case_id:              str | None             # UUID for this arbitration case
    jurisdiction:         str | None             # "intra_coop" | "inter_coop"


class IPDAuditState(AgentState):
    """State for the IPD Auditor Agent (Phase 18 — Game-Theoretic Auditing).

    Models every inter-coop trade as a round in an infinitely repeated
    Prisoner's Dilemma.  Two graphs share this state type:

    Pre-Trade Graph:
      load_interaction_history → compute_cooperation_signals
        → predict_cooperation_probability → compute_payoff_matrix
        → select_strategy → [HITL if P(coop) < floor] → emit_ipd_report → END

    Post-Trade Graph:
      classify_escrow_outcome → update_reputation_graph
        → compute_updated_probability → broadcast_audit_summary → END

    Strategy: Generous Tit-for-Tat — start cooperative, mirror partner's
    last move, forgive defections with probability `ipd_forgiveness_rate`.
    """
    partner_did:              str | None              # DID of the partner being assessed
    audit_mode:               str | None              # "pre_trade" | "post_trade" | "inter_node_audit"
    interaction_history:      list[dict[str, Any]]    # Pairwise trade history records
    global_history:           dict[str, Any] | None   # Partner's global reputation data
    trust_score_trajectory:   list[dict[str, Any]]    # On-chain trust score trend
    federation_behavior:      dict[str, Any] | None   # Federation responsiveness metrics
    ica_scores:               dict[str, Any] | None   # ICA composite score if available
    cooperation_probability:  float | None            # P(cooperate) — weighted signal aggregation
    payoff_matrix:            dict[str, Any] | None   # {R, S, T, P} + expected values
    recommended_strategy:     str | None              # "cooperate" | "defect" (GTfT output)
    strategy_rationale:       str | None              # Plain-language explanation
    risk_assessment:          dict[str, Any] | None   # Risk profile summary
    escrow_outcome:           dict[str, Any] | None   # Post-trade: raw escrow resolution data
    outcome_classification:   dict[str, Any] | None   # Post-trade: (C/D, C/D) classification
    reputation_update:        dict[str, Any] | None   # Post-trade: delta applied to reputation
    audit_request:            dict[str, Any] | None   # Inter-node audit request payload
    audit_response:           dict[str, Any] | None   # Inter-node audit response payload
    ipd_report:               dict[str, Any] | None   # Final compiled report for human review
    requires_human_token:     bool                    # HITL gate when P(coop) < floor
    is_meatspace:             bool                    # True if no on-chain presence
    peer_attestations:        list[dict[str, Any]]    # Meatspace attestation records


class StewardshipCouncilState(AgentState):
    """State for the Stewardship Council Scorer Agent (Phase 23).

    Computes dynamic Impact Scores for all cooperative members based on
    contribution history and ethical audit signals. Determines steward
    eligibility and proposes threshold updates.

    Graph:
      aggregate_contributions → fetch_ethical_audit → compute_impact_scores
        → evaluate_steward_eligibility → propose_threshold_update
        → [HITL if threshold change] → push_scores_to_chain → END
    """
    target_nodes:            list[str]                     # DIDs to score
    contribution_aggregates: list[dict[str, Any]]          # Per-node contribution totals
    ecosystem_total_value:   float | None                  # Sum of all contribution value
    ethical_audit_results:   list[dict[str, Any]]          # Per-node ethical audit scores
    impact_scores:           list[dict[str, Any]]          # Computed Impact_Score per node
    current_threshold:       float | None                  # Current steward threshold
    proposed_threshold:      float | None                  # Proposed new threshold
    threshold_rationale:     str | None                    # Why threshold changed
    chain_update_result:     dict[str, Any] | None         # Oracle tx result
    anticipatory_warnings:   list[dict[str, Any]]          # Nodes near threshold
    requires_human_token:    bool


class FiatGatewayState(AgentState):
    """State for the Fiat Gateway Agent (Phase 26).

    Orchestrates mint/burn of cFIAT tokens based on cooperative bank
    reserve changes. Bridges on-chain escrow settlements with off-chain
    Open Banking fiat transfers.

    Graph:
      check_reserve → evaluate_solvency → propose_action
        → [HITL if mint above threshold] → execute_on_chain → END
    """
    reserve_balance:         dict[str, Any] | None         # FiatReserveBalance snapshot
    on_chain_supply:         int | None                    # Total cFIAT supply (wei)
    solvency_ratio:          float | None                  # reserve / supply ratio
    proposed_action:         str | None                    # "mint" | "burn" | "hold"
    proposed_amount:         int | None                    # Token amount (wei)
    chain_tx_result:         dict[str, Any] | None         # Mint/burn tx result
    requires_human_token:    bool


class CuratorDebateState(AgentState):
    """State for the Curator Network debate graph (IKC).

    Three curators (Efficiency, Ethics, Resilience) evaluate a proposed
    status change to a KnowledgeAsset. Unanimous consent required; mixed
    votes escalate to StewardshipCouncil HITL.

    Graph:
      validate_proposal → check_downstream_impact
        → [conditional: reject if deps exist]
        → check_break_glass → [conditional: pause if active]
        → efficiency_curator_vote → ethics_curator_vote
        → resilience_curator_vote → evaluate_consensus
        → [conditional: apply | reject | escalate to HITL]
        → apply_status_change → END
    """
    asset_cid:               str | None
    proposed_status:         str | None              # Target KnowledgeAssetStatus value
    proposer_rationale:      str | None
    asset_metadata:          dict[str, Any] | None   # Current asset record from LibraryManager
    downstream_deps:         list[str]               # Active CIDs depending on this asset
    dependency_check_passed: bool
    votes:                   list[dict[str, Any]]    # CuratorVote dicts
    consensus_status:        str | None              # in_progress|unanimous_approve|unanimous_reject|escalated|paused|rejected_downstream_deps
    rationale_log:           list[str]
    escalation_signal:       bool
    break_glass_active:      bool
    requires_human_token:    bool


class DraftingState(AgentState):
    """State for the RegulatoryScribe + DigitalNotary graph (Governance Orchestrator).

    The ComplianceFactory pipeline: load manifest -> resolve data sources ->
    fill fields -> validate -> render -> diff-lock check -> submit for review.

    Graph:
      load_manifest -> resolve_data_sources -> fill_fields -> validate_fields
        -> render_document -> diff_lock_check -> END
    """
    manifest_id:          str | None
    manifest_version:     int | None
    manifest_content_cid: str | None
    boilerplate_text:     str | None
    field_definitions:    list[dict[str, Any]]     # Serialised FieldDefinition dicts
    resolved_fields:      dict[str, str]            # data_source_path -> resolved value
    filled_fields:        dict[str, str]            # field_id -> filled value
    rendered_text:        str | None
    diff_lock_valid:      bool
    draft_status:         str | None                # DraftStatus.value
    rationale_log:        list[str]
    version_warnings:     list[str]
    # approval_status for HITL proposal lifecycle (Pending|Approved|Settled|Expired)
    approval_status:      str | None


class ResearchFellowshipState(AgentState):
    """State for the RITL Peer Review Graph (Diplomatic Embassy).

    Four reviewer agents (Rigor, Novelty, Ethics, Reproducibility) evaluate
    a knowledge asset submission. Includes Socratic Cross-Examination and
    optional Blind Review (ZK-flow) mode.

    Graph:
      validate_submission → assign_reviewers
        → rigor_review → novelty_review → ethics_review → reproducibility_review
        → socratic_cross_examination → evaluate_consensus
        → [conditional: finalize | HITL | END]
    """
    asset_cid:              str | None
    author_did:             str | None
    submission_title:       str | None
    asset_metadata:         dict[str, Any] | None
    blind_mode:             bool                        # True = ZK blind review
    reviewer_assignments:   list[dict[str, Any]]        # Reviewer-dimension mappings
    reviews:                list[dict[str, Any]]         # PeerReview dicts
    socratic_exchanges:     list[dict[str, Any]]         # SocraticExchange dicts
    review_consensus:       str | None                   # accept|minor_revisions|major_revisions|reject
    rationale_log:          list[str]
    escalation_signal:      bool
    requires_human_token:   bool
