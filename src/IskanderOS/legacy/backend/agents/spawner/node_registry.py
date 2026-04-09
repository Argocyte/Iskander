"""
Node Registry — Maps string node-type names to callable LangGraph node functions.

The spawner resolves AJD ``node_sequence`` entries against this registry.
Only pre-registered functions can be used — no eval(), no exec(), no
arbitrary code injection.  The registry is fixed at deployment time.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from backend.agents.state import AgentState

logger = logging.getLogger(__name__)


# ── Generic HITL breakpoint node ──────────────────────────────────────────────


def _generic_hitl_breakpoint(state: AgentState) -> dict[str, Any]:
    """No-op node used as an HITL interrupt point in spawned agents.

    Same pattern as ``human_review`` in the governance agent.
    """
    return state


# ── Registry ──────────────────────────────────────────────────────────────────
# Lazy-loaded to avoid circular imports at module level.

_NODE_REGISTRY: dict[str, Callable] | None = None


def _build_registry() -> dict[str, Callable]:
    """Build the node registry from all library agents.

    Called once on first access.  Imports are deferred to avoid circular
    dependencies during module initialization.
    """
    from backend.agents.library.secretary import (
        parse_transcript,
        extract_consensus,
        prepare_broadcast,
    )
    from backend.agents.library.treasurer import (
        validate_payment,
        check_mondragon_ratio,
        draft_payment_tx,
        human_approve,
    )
    from backend.agents.library.steward import (
        validate_claim,          # Phase 17: replaced classify_contribution
        validate_member,
        verify_peer_witness,     # Phase 17: peer verification gate
        quantify_care_work,
        check_circuit_breaker,
        write_ledger_entry,
        human_review,
    )
    from backend.agents.library.procurement import (
        parse_purchase_request,
        search_cooperative_vendors,
        rank_and_select_vendor,
        prepare_order,
    )
    from backend.agents.library.provisioner import (
        parse_app_request,
        search_app_catalog,
        propose_deployment,
        human_vote_app,
        pull_image,
        deploy_container,
        configure_proxy,
        generate_credentials,
    )
    from backend.agents.library.ica_vetter import (
        intake_partner,
        gather_on_chain_signals,
        gather_off_chain_signals,
        assess_ica_principles,
        compute_value_matrix,
        enrich_with_ipd_prediction,
        human_review_vetting,
        emit_report,
    )
    from backend.agents.library.ipd_auditor import (
        load_interaction_history,
        compute_cooperation_signals,
        predict_cooperation_probability,
        compute_payoff_matrix,
        select_strategy,
        human_review_ipd,
        emit_ipd_report,
        classify_escrow_outcome,
        update_reputation_graph,
        compute_updated_probability,
        broadcast_audit_summary,
    )
    from backend.agents.library.voting import (
        validate_stance,
        record_stance,
        compute_tally,
        evaluate_closing_condition,
        notify_block,
        trigger_outcome,
    )
    from backend.agents.library.discussion import (
        receive_prompt,
        research_precedents,
        draft_thread_context,
        human_edit_context,
        publish_thread,
        suggest_invitees,
        notify_members,
    )
    from backend.agents.library.proposal import (
        summarise_discussion,
        recommend_process,
        draft_proposal_text,
        human_edit_proposal,
        open_poll,
        notify_participants,
    )
    from backend.agents.library.outcome import (
        tally_final_results,
        classify_decision,
        draft_outcome_statement,
        human_approve_outcome,
        publish_outcome,
        store_precedent_data,
        broadcast_outcome,
        invoke_task_agent,
    )
    from backend.agents.library.task_extractor import (
        extract_action_items,
        confirm_assignments,
        create_task_records,
        schedule_reminders,
    )
    from backend.matrix.bridge import AgentBridge

    _bridge = AgentBridge.get_instance()

    return {
        # Secretary nodes
        "parse_transcript": parse_transcript,
        "extract_consensus": extract_consensus,
        "prepare_broadcast": prepare_broadcast,
        # Treasurer nodes
        "validate_payment": validate_payment,
        "check_mondragon_ratio": check_mondragon_ratio,
        "draft_payment_tx": draft_payment_tx,
        "human_approve": human_approve,
        # Steward v2 nodes (Phase 17: opt-in claim model replaces passive classification)
        "validate_claim": validate_claim,
        "validate_member": validate_member,
        "verify_peer_witness": verify_peer_witness,
        "quantify_care_work": quantify_care_work,
        "check_circuit_breaker": check_circuit_breaker,
        "write_ledger_entry": write_ledger_entry,
        "human_review": human_review,
        # Procurement nodes
        "parse_purchase_request": parse_purchase_request,
        "search_cooperative_vendors": search_cooperative_vendors,
        "rank_and_select_vendor": rank_and_select_vendor,
        "prepare_order": prepare_order,
        # Provisioner nodes (Phase 13)
        "parse_app_request":   parse_app_request,
        "search_app_catalog":  search_app_catalog,
        "propose_deployment":  propose_deployment,
        "human_vote_app":      human_vote_app,
        "pull_image":          pull_image,
        "deploy_container":    deploy_container,
        "configure_proxy":     configure_proxy,
        "generate_credentials": generate_credentials,
        # ICA Ethics Vetting Agent nodes (Phase 17)
        "intake_partner":            intake_partner,
        "gather_on_chain_signals":   gather_on_chain_signals,
        "gather_off_chain_signals":  gather_off_chain_signals,
        "assess_ica_principles":     assess_ica_principles,
        "compute_value_matrix":          compute_value_matrix,
        "enrich_with_ipd_prediction":    enrich_with_ipd_prediction,
        "human_review_vetting":          human_review_vetting,
        "emit_report":                   emit_report,
        # IPD Auditor Agent nodes (Phase 18: Game-Theoretic Auditing)
        # Pre-trade graph
        "load_interaction_history":      load_interaction_history,
        "compute_cooperation_signals":   compute_cooperation_signals,
        "predict_cooperation_probability": predict_cooperation_probability,
        "compute_payoff_matrix":         compute_payoff_matrix,
        "select_strategy":               select_strategy,
        "human_review_ipd":              human_review_ipd,
        "emit_ipd_report":               emit_ipd_report,
        # Post-trade graph
        "classify_escrow_outcome":       classify_escrow_outcome,
        "update_reputation_graph":       update_reputation_graph,
        "compute_updated_probability":   compute_updated_probability,
        "broadcast_audit_summary":       broadcast_audit_summary,
        # Matrix notification node (Phase 14A) — generic, usable in any graph
        "send_matrix_notification": _bridge.send_matrix_notification_node,
        # Generic
        "hitl_breakpoint": _generic_hitl_breakpoint,
        # Deliberation: Voting nodes (Phase B — deterministic, no LLM)
        "validate_stance":            validate_stance,
        "record_stance":              record_stance,
        "compute_tally":              compute_tally,
        "evaluate_closing_condition": evaluate_closing_condition,
        "notify_block":               notify_block,
        "trigger_outcome":            trigger_outcome,
        # Deliberation: Discussion nodes (Phase B — LLM + HITL)
        "receive_prompt":        receive_prompt,
        "research_precedents":   research_precedents,
        "draft_thread_context":  draft_thread_context,
        "human_edit_context":    human_edit_context,
        "publish_thread":        publish_thread,
        "suggest_invitees":      suggest_invitees,
        "notify_members":        notify_members,
        # Deliberation: Proposal nodes (Phase B — LLM + HITL)
        "summarise_discussion":  summarise_discussion,
        "recommend_process":     recommend_process,
        "draft_proposal_text":   draft_proposal_text,
        "human_edit_proposal":   human_edit_proposal,
        "open_poll":             open_poll,
        "notify_participants":   notify_participants,
        # Deliberation: Outcome nodes (Phase B — LLM + HITL)
        "tally_final_results":     tally_final_results,
        "classify_decision":       classify_decision,
        "draft_outcome_statement": draft_outcome_statement,
        "human_approve_outcome":   human_approve_outcome,
        "publish_outcome":         publish_outcome,
        "store_precedent_data":    store_precedent_data,
        "broadcast_outcome":       broadcast_outcome,
        "invoke_task_agent":       invoke_task_agent,
        # Deliberation: Task Extractor nodes (Phase B — LLM + HITL)
        "extract_action_items":  extract_action_items,
        "confirm_assignments":   confirm_assignments,
        "create_task_records":   create_task_records,
        "schedule_reminders":    schedule_reminders,
    }


def get_registry() -> dict[str, Callable]:
    """Return the global node registry, building it on first access."""
    global _NODE_REGISTRY
    if _NODE_REGISTRY is None:
        _NODE_REGISTRY = _build_registry()
    return _NODE_REGISTRY


def resolve_nodes(node_names: list[str]) -> list[tuple[str, Callable]]:
    """Validate and resolve a list of node-type strings to callables.

    Parameters
    ----------
    node_names:
        Ordered list of node-type strings (from an AJD ``node_sequence``).

    Returns
    -------
    list[tuple[str, Callable]]
        Ordered list of ``(name, function)`` tuples.

    Raises
    ------
    ValueError
        If any name is not found in the registry.
    """
    registry = get_registry()
    resolved: list[tuple[str, Callable]] = []
    unknown: list[str] = []

    for name in node_names:
        func = registry.get(name)
        if func is None:
            unknown.append(name)
        else:
            resolved.append((name, func))

    if unknown:
        available = sorted(registry.keys())
        raise ValueError(
            f"Unknown node types: {unknown}.  "
            f"Available: {available}"
        )

    return resolved
