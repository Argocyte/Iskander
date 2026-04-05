"""
InitializerAgent — LangGraph StateGraph for the Genesis Boot Sequence.

Two paths: solo (SOLO_NODE) and cooperative (LEGACY_IMPORT / NEW_FOUNDING).
Identity first, governance second. All founding decisions require
unanimous consent (N-of-N).

GLASS BOX: Every node appends an AgentAction to state["action_log"].
GENESIS CRITICAL: Not interruptible by agents_are_paused().
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from backend.config import settings
from backend.schemas.genesis import GenesisMode, GovernanceTier
from backend.schemas.glass_box import AgentAction, EthicalImpactLevel

logger = logging.getLogger(__name__)

AGENT_ID = "initializer-agent-v1"


def _append_action(
    state: dict[str, Any],
    action: str,
    rationale: str,
    impact: EthicalImpactLevel = EthicalImpactLevel.LOW,
    payload: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Build an AgentAction and return updated action_log."""
    agent_action = AgentAction(
        agent_id=AGENT_ID,
        action=action,
        rationale=rationale,
        ethical_impact=impact,
        payload=payload or {},
    )
    return state.get("action_log", []) + [agent_action.model_dump()]


def select_mode(state: dict[str, Any]) -> dict[str, Any]:
    """Read mode from state and set node_type."""
    if state.get("error"):
        return state

    if state.get("boot_complete"):
        return {
            **state,
            "error": "Genesis already complete. Boot sequence cannot be re-run.",
        }

    mode = state.get("mode")
    if mode == GenesisMode.SOLO_NODE.value:
        node_type = "solo"
    else:
        node_type = "cooperative"

    return {
        **state,
        "node_type": node_type,
        "boot_phase": "mode-selected",
        "action_log": _append_action(
            state,
            "select_genesis_mode",
            f"Genesis mode selected: {mode}. Node type: {node_type}.",
            payload={"mode": mode, "node_type": node_type},
        ),
    }


def collect_owner_profile(state: dict[str, Any]) -> dict[str, Any]:
    """Solo mode: validate owner profile is present in state."""
    if state.get("error"):
        return state

    profile = state.get("owner_profile")
    if not profile:
        return {
            **state,
            "error": "Solo mode requires owner_profile in state.",
        }

    return {
        **state,
        "boot_phase": "owner-profile-collected",
        "action_log": _append_action(
            state,
            "collect_owner_profile",
            f"Solo node owner profile collected: DID={profile.get('did', 'unknown')}.",
            payload={"owner_did": profile.get("did")},
        ),
    }


def inject_regulatory_layer(state: dict[str, Any]) -> dict[str, Any]:
    """Load jurisdiction-specific regulatory layer from templates directory."""
    if state.get("error"):
        return state

    profile = state.get("owner_profile") or state.get("coop_profile") or {}
    jurisdiction = profile.get("jurisdiction", settings.genesis_default_jurisdiction)

    templates_dir = Path(settings.genesis_regulatory_templates_dir)
    template_path = templates_dir / f"{jurisdiction}.json"

    if not template_path.exists():
        logger.warning(
            "Regulatory template not found for '%s', falling back to UNIVERSAL",
            jurisdiction,
        )
        template_path = templates_dir / "UNIVERSAL.json"
        jurisdiction = "UNIVERSAL"

    with open(template_path) as f:
        regulatory_data = json.load(f)

    regulatory_data["non_overridable"] = True

    return {
        **state,
        "regulatory_layer": regulatory_data,
        "boot_phase": "regulatory-layer-injected",
        "action_log": _append_action(
            state,
            "inject_regulatory_layer",
            f"Loaded regulatory layer for jurisdiction '{jurisdiction}': "
            f"{len(regulatory_data.get('rules', []))} rule(s). Non-overridable.",
            EthicalImpactLevel.MEDIUM,
            payload={
                "jurisdiction": jurisdiction,
                "rule_count": len(regulatory_data.get("rules", [])),
            },
        ),
    }


def configure_solo_manifest(state: dict[str, Any]) -> dict[str, Any]:
    """Build minimal GovernanceManifest for solo node: ICA core + regulatory layer."""
    if state.get("error"):
        return state

    regulatory_layer = state.get("regulatory_layer") or {}
    regulatory_rules = regulatory_layer.get("rules", [])

    manifest = {
        "version": 1,
        "constitutional_core": [
            "anti_extractive",
            "democratic_control",
            "transparency",
            "open_membership",
        ],
        "policies": regulatory_rules,
    }

    return {
        **state,
        "genesis_manifest": manifest,
        "boot_phase": "solo-manifest-configured",
        "action_log": _append_action(
            state,
            "configure_solo_manifest",
            f"Solo manifest configured with {len(regulatory_rules)} regulatory rule(s) "
            f"+ ICA constitutional core.",
            EthicalImpactLevel.MEDIUM,
            payload={"policy_count": len(regulatory_rules)},
        ),
    }


def register_founders(state: dict[str, Any]) -> dict[str, Any]:
    """Validate minimum 3 founders are registered."""
    if state.get("error"):
        return state

    confirmations = state.get("founder_confirmations", {})
    if len(confirmations) < settings.genesis_min_founders:
        return {
            **state,
            "error": (
                f"Cooperative genesis requires minimum {settings.genesis_min_founders} "
                f"founders. Currently registered: {len(confirmations)}."
            ),
        }

    return {
        **state,
        "boot_phase": "founders-registered",
        "action_log": _append_action(
            state,
            "register_founders",
            f"Registered {len(confirmations)} founding member(s). "
            f"Minimum {settings.genesis_min_founders} met.",
            payload={"founder_count": len(confirmations)},
        ),
    }


def compile_genesis_manifest(state: dict[str, Any]) -> dict[str, Any]:
    """Merge confirmed rules by tier + regulatory layer into GovernanceManifest."""
    if state.get("error"):
        return state

    extracted = state.get("extracted_rules", [])
    regulatory = state.get("regulatory_layer") or {}
    regulatory_rules = regulatory.get("rules", [])

    confirmed_policies = []
    for rule in extracted:
        if rule.get("confirmed"):
            policy = rule.get("proposed_policy_rule", {})
            confirmed_policies.append(policy)

    all_policies = regulatory_rules + confirmed_policies

    manifest = {
        "version": 1,
        "constitutional_core": [
            "anti_extractive",
            "democratic_control",
            "transparency",
            "open_membership",
        ],
        "policies": all_policies,
    }

    return {
        **state,
        "genesis_manifest": manifest,
        "boot_phase": "manifest-compiled",
        "action_log": _append_action(
            state,
            "compile_genesis_manifest",
            f"Compiled genesis manifest: {len(regulatory_rules)} regulatory + "
            f"{len(confirmed_policies)} confirmed = {len(all_policies)} total rules.",
            EthicalImpactLevel.MEDIUM,
            payload={
                "regulatory_count": len(regulatory_rules),
                "confirmed_count": len(confirmed_policies),
                "total_count": len(all_policies),
            },
        ),
    }


REQUIRED_ICA = {"anti_extractive", "democratic_control", "transparency", "open_membership"}


def validate_genesis_manifest(state: dict[str, Any]) -> dict[str, Any]:
    """Validate the compiled manifest has all required fields."""
    if state.get("error"):
        return state

    manifest = state.get("genesis_manifest")
    if not manifest:
        return {**state, "error": "No genesis manifest to validate."}

    core = set(manifest.get("constitutional_core", []))
    missing_ica = REQUIRED_ICA - core
    if missing_ica:
        return {
            **state,
            "error": f"ICA constitutional core incomplete. Missing: {missing_ica}",
        }

    if manifest.get("version", 0) < 1:
        return {**state, "error": "Manifest version must be >= 1."}

    return {
        **state,
        "boot_phase": "manifest-validated",
        "action_log": _append_action(
            state,
            "validate_genesis_manifest",
            f"Genesis manifest validated: version={manifest['version']}, "
            f"ICA core complete, {len(manifest.get('policies', []))} policy rule(s).",
            EthicalImpactLevel.MEDIUM,
            payload={
                "version": manifest["version"],
                "policy_count": len(manifest.get("policies", [])),
                "ica_complete": True,
            },
        ),
    }


# ── Task 12: StateGraph wiring ───────────────────────────────────────────────

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from backend.agents.state import BootState
from backend.agents.genesis.rule_extractor import (
    extract_rules_from_bylaws,
    tag_ambiguous_rules,
)


def _route_after_mode(state: dict[str, Any]) -> str:
    if state.get("error"):
        return END
    if state["node_type"] == "solo":
        return "collect_owner_profile"
    return "register_founders"


def _route_after_founders(state: dict[str, Any]) -> str:
    if state.get("error"):
        return END
    mode = state.get("mode")
    if mode == GenesisMode.LEGACY_IMPORT.value:
        return "extract_rules"
    return "browse_templates"


def deploy_identity(state: dict[str, Any]) -> dict[str, Any]:
    """STUB: Deploy CoopIdentity.sol and mint founder SBTs."""
    if state.get("error"):
        return state
    founders = state.get("founder_confirmations", {})
    sbt_ids = list(range(1, len(founders) + 1))
    return {
        **state,
        "founder_sbt_ids": sbt_ids,
        "boot_phase": "identity-deployed",
        "action_log": _append_action(
            state, "deploy_coop_identity",
            f"STUB: CoopIdentity.sol deployed. Minted {len(sbt_ids)} founder SBTs.",
            EthicalImpactLevel.HIGH,
            payload={"sbt_ids": sbt_ids, "founder_count": len(founders)},
        ),
    }


def deploy_safe(state: dict[str, Any]) -> dict[str, Any]:
    """STUB: Deploy Gnosis Safe with all founders as N-of-N owners."""
    if state.get("error"):
        return state
    founders = state.get("founder_confirmations", {})
    stub_safe = "0x" + "5" * 40
    return {
        **state,
        "safe_address": stub_safe,
        "boot_phase": "safe-deployed",
        "action_log": _append_action(
            state, "deploy_gnosis_safe",
            f"STUB: Gnosis Safe deployed at {stub_safe}. Threshold: {len(founders)}-of-{len(founders)}.",
            EthicalImpactLevel.HIGH,
            payload={"safe_address": stub_safe, "threshold": len(founders)},
        ),
    }


def browse_templates(state: dict[str, Any]) -> dict[str, Any]:
    """STUB: Query LibraryManager for governance templates."""
    if state.get("error"):
        return state
    return {
        **state,
        "boot_phase": "browsing-templates",
        "action_log": _append_action(state, "browse_governance_templates", "STUB: Queried LibraryManager for governance templates."),
    }


def select_template(state: dict[str, Any]) -> dict[str, Any]:
    """STUB: Human selects a governance template."""
    if state.get("error"):
        return state
    return {
        **state,
        "boot_phase": "template-selected",
        "action_log": _append_action(state, "select_governance_template", f"STUB: Template selected (CID: {state.get('skeleton_template_cid', 'none')})."),
    }


def propose_novel_fields(state: dict[str, Any]) -> dict[str, Any]:
    """Package novel fields as KnowledgeAsset proposals."""
    if state.get("error"):
        return state
    extracted = state.get("extracted_rules", [])
    novel = [r for r in extracted if r.get("is_novel_field")]
    return {
        **state,
        "boot_phase": "novel-fields-proposed",
        "action_log": _append_action(
            state, "propose_novel_fields",
            f"Proposed {len(novel)} novel field(s) as KnowledgeAsset candidates. STUB.",
            EthicalImpactLevel.MEDIUM,
            payload={"novel_count": len(novel)},
        ),
    }


def execute_genesis_binding(state: dict[str, Any]) -> dict[str, Any]:
    """The one-way trip — cooperative genesis binding. STUB for Web3."""
    if state.get("error"):
        return state

    from backend.governance.policy_engine import PolicyEngine
    manifest = state.get("genesis_manifest")
    if manifest:
        engine = PolicyEngine.get_instance()
        _loaded_manifest, load_action = engine.load_manifest(manifest_dict=manifest)
        action_log = state.get("action_log", []) + [load_action.model_dump()]
    else:
        action_log = state.get("action_log", [])

    return {
        **state,
        "boot_complete": True,
        "boot_phase": "genesis-complete",
        "action_log": _append_action(
            {**state, "action_log": action_log},
            "execute_genesis_binding",
            "STUB: Genesis binding executed. PolicyEngine loaded. Web3 steps deferred.",
            EthicalImpactLevel.HIGH,
            payload={"manifest_version": manifest.get("version") if manifest else None, "boot_complete": True},
        ),
    }


def execute_solo_genesis(state: dict[str, Any]) -> dict[str, Any]:
    """The one-way trip — solo genesis binding (lightweight). STUB."""
    if state.get("error"):
        return state

    from backend.governance.policy_engine import PolicyEngine
    manifest = state.get("genesis_manifest")
    if manifest:
        engine = PolicyEngine.get_instance()
        _loaded_manifest, load_action = engine.load_manifest(manifest_dict=manifest)
        action_log = state.get("action_log", []) + [load_action.model_dump()]
    else:
        action_log = state.get("action_log", [])

    return {
        **state,
        "boot_complete": True,
        "boot_phase": "genesis-complete",
        "action_log": _append_action(
            {**state, "action_log": action_log},
            "execute_solo_genesis",
            "STUB: Solo genesis binding executed. PolicyEngine loaded. Constitution.sol deferred.",
            EthicalImpactLevel.HIGH,
            payload={"boot_complete": True},
        ),
    }


def build_genesis_graph():
    """Build and compile the Genesis Boot Sequence StateGraph."""
    graph = StateGraph(BootState)

    # Add nodes
    graph.add_node("select_mode", select_mode)
    graph.add_node("collect_owner_profile", collect_owner_profile)
    graph.add_node("configure_solo_manifest", configure_solo_manifest)
    graph.add_node("owner_review", lambda state: {**state, "requires_human_token": True, "boot_phase": "owner-review"})
    graph.add_node("execute_solo_genesis", execute_solo_genesis)
    graph.add_node("register_founders", register_founders)
    graph.add_node("deploy_identity", deploy_identity)
    graph.add_node("deploy_safe", deploy_safe)
    graph.add_node("extract_rules", extract_rules_from_bylaws)
    graph.add_node("tag_ambiguous", tag_ambiguous_rules)
    graph.add_node("browse_templates", browse_templates)
    graph.add_node("select_template", select_template)
    graph.add_node("propose_novel_fields", propose_novel_fields)
    graph.add_node("inject_regulatory_layer", inject_regulatory_layer)
    graph.add_node("compile_genesis_manifest", compile_genesis_manifest)
    graph.add_node("validate_genesis_manifest", validate_genesis_manifest)
    graph.add_node("confirm_mappings", lambda state: {**state, "requires_human_token": True, "boot_phase": "confirm-mappings"})
    graph.add_node("ratify_genesis", lambda state: {**state, "requires_human_token": True, "boot_phase": "ratify-genesis"})
    graph.add_node("execute_genesis_binding", execute_genesis_binding)

    # Entry
    graph.set_entry_point("select_mode")

    # Edges
    graph.add_conditional_edges("select_mode", _route_after_mode)
    graph.add_edge("collect_owner_profile", "inject_regulatory_layer")
    graph.add_conditional_edges(
        "inject_regulatory_layer",
        lambda s: "configure_solo_manifest" if s.get("node_type") == "solo" else "compile_genesis_manifest",
    )
    graph.add_edge("configure_solo_manifest", "validate_genesis_manifest")
    graph.add_conditional_edges(
        "validate_genesis_manifest",
        lambda s: "owner_review" if s.get("node_type") == "solo" else "confirm_mappings",
    )
    graph.add_edge("owner_review", "execute_solo_genesis")
    graph.add_edge("execute_solo_genesis", END)

    graph.add_edge("register_founders", "deploy_identity")
    graph.add_edge("deploy_identity", "deploy_safe")
    graph.add_conditional_edges("deploy_safe", _route_after_founders)
    graph.add_edge("extract_rules", "tag_ambiguous")
    graph.add_edge("tag_ambiguous", "inject_regulatory_layer")
    graph.add_edge("browse_templates", "select_template")
    graph.add_edge("select_template", "inject_regulatory_layer")
    graph.add_edge("compile_genesis_manifest", "validate_genesis_manifest")
    graph.add_edge("confirm_mappings", "propose_novel_fields")
    graph.add_edge("propose_novel_fields", "ratify_genesis")
    graph.add_edge("ratify_genesis", "execute_genesis_binding")
    graph.add_edge("execute_genesis_binding", END)

    checkpointer = MemorySaver()
    return graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["owner_review", "confirm_mappings", "ratify_genesis"],
    )
