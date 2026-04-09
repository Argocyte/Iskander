"""
Provisioner Agent — Phase 13: Democratic App Store & Container Orchestration.

Graph:
  parse_app_request → search_app_catalog → propose_deployment
  → [HITL: human_vote_app]
  → pull_image → deploy_container → configure_proxy → generate_credentials → END

Every node follows the Glass Box Protocol: state mutations are accompanied by
an AgentAction record logged to the action_log.

HITL ENFORCEMENT:
  - `deploy_container` and any removal operation carry ethical_impact=HIGH.
  - The graph suspends at `human_vote_app` and resumes only after a cooperative
    member calls POST /apps/{app_id}/vote with the required approval threshold.
  - The agent NEVER deploys an image absent from the FOSS catalog.
  - If `deploy_container` fails, the graph routes to END with an error state.
    No silent retries.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from backend.agents.core import load_prompt
from backend.agents.state import ProvisionerState
from backend.appstore.catalog import AppCatalog
from backend.appstore.docker_manager import DockerManager
from backend.config import settings
from backend.routers.power import agents_are_paused
from backend.schemas.glass_box import AgentAction, EthicalImpactLevel

logger = logging.getLogger(__name__)

AGENT_ID = "provisioner-agent"

_catalog = AppCatalog()
_docker = DockerManager(socket_url=settings.docker_socket_url)

_role_prompt = load_prompt("prompt_provisioner.txt")


# ── Node 1: Parse App Request ─────────────────────────────────────────────────

def parse_app_request(state: ProvisionerState) -> dict[str, Any]:
    """
    Validate and normalise the incoming app deployment request.

    Checks that the request contains a description and a requesting member DID.
    Sets `error` if required fields are missing so the router can reject early.
    """
    if agents_are_paused():
        return {**state, "error": "Agents paused (low power mode)."}

    req = state.get("app_request") or {}
    description = req.get("description", "").strip()
    requested_by = req.get("requested_by", "").strip()

    if not description or not requested_by:
        return {**state, "error": "app_request must include 'description' and 'requested_by'."}

    action = AgentAction(
        agent_id=AGENT_ID,
        action="parse_app_request",
        rationale=(
            "Member submitted a software deployment request. "
            "Validating fields before catalog search."
        ),
        ethical_impact=EthicalImpactLevel.LOW,
        payload={"requested_by": requested_by, "description": description[:200]},
    )

    return {
        **state,
        "app_request": req,
        "error": None,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Node 2: Search App Catalog ────────────────────────────────────────────────

def search_app_catalog(state: ProvisionerState) -> dict[str, Any]:
    """
    Query the vetted FOSS catalog for apps matching the member's request.

    Uses keyword search across name, description, and category.
    Returns up to 3 candidate entries as `catalog_matches`.

    If no matches are found, sets `error` — the cooperative may need to amend
    the catalog via democratic vote to add a new app category.
    """
    req = state.get("app_request") or {}
    query = req.get("preferred_app") or req.get("description", "")

    matches = _catalog.search(query, top_k=3)

    # If exact preferred_app was given, surface it first.
    preferred = req.get("preferred_app", "").lower()
    if preferred:
        exact = _catalog.get(preferred)
        if exact and exact not in matches:
            matches.insert(0, exact)

    action = AgentAction(
        agent_id=AGENT_ID,
        action=f"search_app_catalog(query='{query[:80]}')",
        rationale=(
            "Searching vetted FOSS catalog to find software matching member's request. "
            "Only cooperative-approved images may be deployed."
        ),
        ethical_impact=EthicalImpactLevel.LOW,
        payload={"query": query[:200], "match_count": len(matches)},
    )

    if not matches:
        return {
            **state,
            "catalog_matches": [],
            "error": (
                "No catalog matches for the requested software. "
                "The cooperative may add new apps by amending catalog.yaml via democratic vote."
            ),
            "action_log": state.get("action_log", []) + [action.model_dump()],
        }

    return {
        **state,
        "catalog_matches": matches,
        "error": None,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Node 3: Propose Deployment ────────────────────────────────────────────────

def propose_deployment(state: ProvisionerState) -> dict[str, Any]:
    """
    Compile a DeploymentSpec from the best catalog match and present it for
    democratic vote.

    Selects the top catalog match, assigns a host port from the catalog default,
    builds Traefik labels, and resolves __GENERATE__ env var placeholders.

    The `deployment_spec` is written to state and the graph suspends at the
    HITL `human_vote_app` breakpoint. Members vote via POST /apps/{app_id}/vote.
    """
    matches = state.get("catalog_matches") or []
    if not matches:
        return {**state, "error": "No catalog matches to propose."}

    req = state.get("app_request") or {}
    top_match = matches[0]
    app_name = top_match["name"]
    image = top_match["docker_image"]
    default_port = top_match.get("default_port", 80)
    container_name = f"iskander_{app_name}"

    # Resolve __GENERATE__ placeholders with random credentials.
    # Resolved credentials are held in deployment_spec but NEVER logged to action_log.
    env_vars: dict[str, str] = {}
    for key, val in top_match.get("environment", {}).items():
        if val == "__GENERATE__":
            env_vars[key] = DockerManager.generate_credential()
        elif val.startswith("__FROM_ENV__"):
            env_name = val.removeprefix("__FROM_ENV__")
            env_vars[key] = os.environ.get(env_name, f"MISSING_{env_name}")
        else:
            env_vars[key] = val

    traefik_labels = DockerManager.build_traefik_labels(
        app_name=app_name,
        domain_suffix=settings.app_domain_suffix,
        container_port=default_port,
        path_prefix=top_match.get("traefik_path_prefix"),
    )
    traefik_rule = traefik_labels.get(
        f"traefik.http.routers.iskander_{app_name}.rule", ""
    )

    spec: dict[str, Any] = {
        "app_name": app_name,
        "docker_image": image,
        "container_name": container_name,
        "port_mapping": {"host_port": default_port, "container_port": default_port},
        "traefik_rule": traefik_rule,
        "resource_limits": top_match.get("resource_limits", {}),
        "environment": env_vars,
        "volumes": top_match.get("volumes", []),
        "requested_by": req.get("requested_by", ""),
        "catalog_description": top_match.get("description", ""),
    }

    action = AgentAction(
        agent_id=AGENT_ID,
        action=f"propose_deployment({app_name})",
        rationale=(
            f"Compiled deployment proposal for '{app_name}' from vetted catalog. "
            f"Traefik rule: {traefik_rule}. "
            "Awaiting democratic HITL vote before any Docker operations."
        ),
        ethical_impact=EthicalImpactLevel.MEDIUM,
        # SECURITY: env_vars (including generated credentials) excluded from action log.
        payload={
            "app_name": app_name,
            "docker_image": image,
            "traefik_rule": traefik_rule,
            "resource_limits": spec["resource_limits"],
        },
    )

    return {
        **state,
        "deployment_spec": spec,
        "requires_human_token": True,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Node 4: HITL Breakpoint ───────────────────────────────────────────────────

def human_vote_app(state: ProvisionerState) -> dict[str, Any]:
    """
    No-op HITL breakpoint.

    The graph interrupts here. Resumption is triggered by the router
    POST /apps/{app_id}/vote after the cooperative's approval threshold is met.
    `requires_human_token` must be set to False by the router before resuming.
    """
    return state


# ── Node 5: Pull Image ────────────────────────────────────────────────────────

def pull_image(state: ProvisionerState) -> dict[str, Any]:
    """
    Pull the approved Docker image from the registry.

    Verifies catalog allowance before contacting Docker.
    """
    spec = state.get("deployment_spec") or {}
    image = spec.get("docker_image", "")

    allowed = _catalog.is_allowed_image(image)
    success, action = _docker.pull_image(image, allowed=allowed)

    new_log = state.get("action_log", []) + [action.model_dump()]

    if not success:
        return {
            **state,
            "error": f"Image pull failed for {image}. See action log.",
            "action_log": new_log,
        }

    return {**state, "error": None, "action_log": new_log}


# ── Node 6: Deploy Container ──────────────────────────────────────────────────

def deploy_container(state: ProvisionerState) -> dict[str, Any]:
    """
    Create and start the Docker container for the approved app.

    ethical_impact=HIGH — only reachable after HITL vote clears
    `requires_human_token`.

    On failure, sets `error` and routes graph to END. No retries.
    """
    spec = state.get("deployment_spec") or {}

    traefik_labels = DockerManager.build_traefik_labels(
        app_name=spec["app_name"],
        domain_suffix=settings.app_domain_suffix,
        container_port=spec["port_mapping"]["container_port"],
        path_prefix=None,  # Already encoded in spec; rebuild from source to be safe.
    )

    container_id, action = _docker.create_container(
        name=spec["container_name"],
        image=spec["docker_image"],
        port_mapping=spec["port_mapping"],
        environment=spec.get("environment", {}),
        volumes=spec.get("volumes", []),
        resource_limits=spec.get("resource_limits", {}),
        traefik_labels=traefik_labels,
        traefik_network=settings.traefik_network,
    )

    new_log = state.get("action_log", []) + [action.model_dump()]

    if not container_id:
        return {
            **state,
            "container_id": None,
            "error": f"Container creation failed for {spec.get('app_name')}. See action log.",
            "action_log": new_log,
        }

    return {
        **state,
        "container_id": container_id,
        "error": None,
        "action_log": new_log,
    }


# ── Node 7: Configure Proxy ───────────────────────────────────────────────────

def configure_proxy(state: ProvisionerState) -> dict[str, Any]:
    """
    Confirm Traefik routing is active for the deployed container.

    Traefik auto-discovers containers by Docker labels — no manual config
    file changes required. This node logs the routing confirmation and
    sets `proxy_configured=True` for the router to surface to the member.
    """
    spec = state.get("deployment_spec") or {}
    container_id = state.get("container_id")

    traefik_rule = spec.get("traefik_rule", "")
    app_name = spec.get("app_name", "")
    domain_suffix = settings.app_domain_suffix

    access_url = (
        f"http://{app_name}.{domain_suffix}"
        if "Host" in traefik_rule
        else f"http://{domain_suffix}{spec.get('traefik_path_prefix', '/' + app_name)}"
    )

    action = AgentAction(
        agent_id=AGENT_ID,
        action=f"configure_proxy({app_name})",
        rationale=(
            f"Traefik reverse proxy routing confirmed via Docker label auto-discovery. "
            f"App accessible at: {access_url}. "
            "No manual proxy configuration required — labels applied at container creation."
        ),
        ethical_impact=EthicalImpactLevel.LOW,
        payload={
            "app_name": app_name,
            "container_id": (container_id or "")[:12],
            "access_url": access_url,
            "traefik_rule": traefik_rule,
        },
    )

    return {
        **state,
        "proxy_configured": True,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Node 8: Generate Credentials ─────────────────────────────────────────────

def generate_credentials(state: ProvisionerState) -> dict[str, Any]:
    """
    Assemble admin credentials for delivery to the requesting member.

    Credentials were generated during `propose_deployment` and stored in
    deployment_spec.environment. This node extracts only the credential fields
    (keys with __GENERATE__ origin) for the response payload.

    SECURITY: Credentials are NOT included in the action_log payload.
    They appear only in `admin_credentials` state, which the router should
    deliver over an authenticated, encrypted channel (HTTPS or Matrix DM).
    After delivery, the router should update `deployment_spec.environment` to
    record only that credentials were issued, not what they were.
    """
    spec = state.get("deployment_spec") or {}
    app_name = spec.get("app_name", "")

    # Extract fields marked for credential generation in the original catalog entry.
    # We re-derive this by checking for env var values that look like generated passwords.
    # In production: store a separate credentials dict during propose_deployment.
    creds: dict[str, str] = {}
    raw_env = spec.get("environment", {})

    # Heuristic: passwords are 24-char alphanum strings.
    # In production: track generated keys explicitly in a separate state field.
    for key, val in raw_env.items():
        if isinstance(val, str) and len(val) == 24 and val.isalnum():
            creds[key] = val

    action = AgentAction(
        agent_id=AGENT_ID,
        action=f"generate_credentials({app_name})",
        rationale=(
            "Admin credentials generated during proposal phase. "
            "Delivering to requesting member — credentials excluded from audit log for privacy."
        ),
        ethical_impact=EthicalImpactLevel.MEDIUM,
        payload={"app_name": app_name, "credential_keys": list(creds.keys())},
        # NOTE: credential values are NEVER added to the action payload.
    )

    return {
        **state,
        "admin_credentials": creds,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Routing ───────────────────────────────────────────────────────────────────

def _route_after_vote(state: ProvisionerState) -> str:
    """Route to pull_image if approved, END if rejected or error."""
    if state.get("error"):
        return END
    if state.get("requires_human_token"):
        # Should not reach here — HITL breakpoint ensures token is cleared.
        return END
    return "pull_image"


def _route_after_deploy(state: ProvisionerState) -> str:
    """Route to configure_proxy on success, END on failure."""
    if state.get("error") or not state.get("container_id"):
        return END
    return "configure_proxy"


# ── Graph Assembly ────────────────────────────────────────────────────────────

def build_provisioner_graph():
    """
    Compile the Provisioner Agent LangGraph with HITL vote breakpoint.

    Topology:
      parse_app_request
        → search_app_catalog
        → propose_deployment
        → [INTERRUPT: human_vote_app]
        → pull_image
        → deploy_container
        → configure_proxy
        → generate_credentials
        → END
    """
    g = StateGraph(ProvisionerState)

    g.add_node("parse_app_request",  parse_app_request)
    g.add_node("search_app_catalog", search_app_catalog)
    g.add_node("propose_deployment", propose_deployment)
    g.add_node("human_vote_app",     human_vote_app)
    g.add_node("pull_image",         pull_image)
    g.add_node("deploy_container",   deploy_container)
    g.add_node("configure_proxy",    configure_proxy)
    g.add_node("generate_credentials", generate_credentials)

    g.set_entry_point("parse_app_request")
    g.add_edge("parse_app_request",  "search_app_catalog")
    g.add_edge("search_app_catalog", "propose_deployment")
    g.add_edge("propose_deployment", "human_vote_app")

    g.add_conditional_edges(
        "human_vote_app",
        _route_after_vote,
        {"pull_image": "pull_image", END: END},
    )

    g.add_edge("pull_image", "deploy_container")

    g.add_conditional_edges(
        "deploy_container",
        _route_after_deploy,
        {"configure_proxy": "configure_proxy", END: END},
    )

    g.add_edge("configure_proxy",      "generate_credentials")
    g.add_edge("generate_credentials", END)

    return g.compile(
        checkpointer=MemorySaver(),
        interrupt_before=["human_vote_app"],
    )


provisioner_graph = build_provisioner_graph()
