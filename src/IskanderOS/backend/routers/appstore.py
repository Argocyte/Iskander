"""
appstore.py — Phase 13: Democratic App Store API Router.

Endpoints:
  POST /apps/request          — Submit a natural-language app deployment request.
  GET  /apps                  — List all deployments (proposed, running, stopped).
  GET  /apps/catalog          — List vetted FOSS catalog entries.
  POST /apps/{app_id}/vote    — Cast a democratic vote on a proposed deployment.
  DELETE /apps/{app_id}       — Request removal of a running app (triggers HITL).

All mutating operations require a valid member DID in the request body.
The Provisioner LangGraph graph handles the full deployment lifecycle;
this router provides the HTTP interface and manages DB persistence.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from backend.agents.library.provisioner import provisioner_graph
from backend.appstore.catalog import AppCatalog
from backend.auth.dependencies import AuthenticatedUser, get_current_user
from backend.schemas.appstore import AppRequest, AppVoteRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/apps", tags=["appstore"])
_catalog = AppCatalog()

# ── In-memory deployment registry (replace with asyncpg queries in production) ─

_deployments: dict[str, dict[str, Any]] = {}
_thread_counter = 0


def _next_thread_id() -> str:
    global _thread_counter
    _thread_counter += 1
    return f"provisioner-{_thread_counter}"


# ── POST /apps/request ────────────────────────────────────────────────────────

@router.post("/request", status_code=status.HTTP_202_ACCEPTED)
async def request_app(
    body: AppRequest,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Submit a natural-language app deployment request.

    Starts the Provisioner Agent LangGraph. The graph runs until the
    `human_vote_app` HITL breakpoint, then suspends. Members vote via
    POST /apps/{app_id}/vote to resume the deployment pipeline.

    Returns:
        deployment_id — use this to vote and track status.
        catalog_matches — apps the agent found in the FOSS catalog.
        deployment_spec — compiled deployment proposal awaiting vote.
    """
    deployment_id = str(uuid.uuid4())
    thread_id = _next_thread_id()
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "messages": [],
        "agent_id": "provisioner-agent",
        "action_log": [],
        "error": None,
        "app_request": body.model_dump(),
        "catalog_matches": [],
        "deployment_spec": None,
        "container_id": None,
        "proxy_configured": False,
        "admin_credentials": None,
        "requires_human_token": True,
    }

    try:
        final_state = provisioner_graph.invoke(initial_state, config=config)
    except Exception as exc:
        logger.exception("Provisioner graph error for request %s", deployment_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Provisioner agent error: {exc}",
        )

    if final_state.get("error"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=final_state["error"],
        )

    _deployments[deployment_id] = {
        "deployment_id": deployment_id,
        "thread_id": thread_id,
        "status": "proposed",
        "app_name": (final_state.get("deployment_spec") or {}).get("app_name", "unknown"),
        "deployment_spec": final_state.get("deployment_spec"),
        "container_id": None,
        "proxy_configured": False,
        "votes_for": 0,
        "votes_against": 0,
    }

    return {
        "deployment_id": deployment_id,
        "status": "proposed",
        "catalog_matches": [m.get("name") for m in (final_state.get("catalog_matches") or [])],
        "deployment_spec": {
            k: v for k, v in (final_state.get("deployment_spec") or {}).items()
            if k != "environment"  # Never return env vars (may contain credentials).
        },
        "message": (
            "Deployment proposal created. "
            "Cooperative members must vote before the app will be deployed. "
            f"Vote endpoint: POST /apps/{deployment_id}/vote"
        ),
    }


# ── GET /apps ─────────────────────────────────────────────────────────────────

@router.get("", status_code=status.HTTP_200_OK)
async def list_apps() -> dict[str, Any]:
    """
    List all app deployments (proposed, running, stopped, failed).

    In production: replace with asyncpg SELECT from app_deployments table.
    """
    return {
        "deployments": [
            {
                "deployment_id": d["deployment_id"],
                "app_name": d["app_name"],
                "status": d["status"],
                "votes_for": d["votes_for"],
                "votes_against": d["votes_against"],
                "container_id": (d.get("container_id") or "")[:12] or None,
                "proxy_configured": d.get("proxy_configured", False),
            }
            for d in _deployments.values()
        ]
    }


# ── GET /apps/catalog ─────────────────────────────────────────────────────────

@router.get("/catalog", status_code=status.HTTP_200_OK)
async def list_catalog() -> dict[str, Any]:
    """List all vetted FOSS apps available for democratic deployment."""
    return {
        "apps": [
            {
                "name": e["name"],
                "description": e.get("description", "")[:200],
                "category": e.get("category", ""),
                "docker_image": e.get("docker_image", ""),
            }
            for e in _catalog.all()
        ]
    }


# ── POST /apps/{app_id}/vote ──────────────────────────────────────────────────

@router.post("/{app_id}/vote", status_code=status.HTTP_200_OK)
async def vote_on_app(
    app_id: str,
    body: AppVoteRequest,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Cast a democratic vote on a proposed app deployment.

    When approval threshold is met (stub: any single 'approved=true' vote),
    resumes the Provisioner LangGraph past the HITL breakpoint to execute
    the actual Docker deployment.

    Production: enforce M-of-N quorum using app_votes table and AJD threshold.
    """
    deployment = _deployments.get(app_id)
    if not deployment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found.")

    if deployment["status"] != "proposed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Deployment is in '{deployment['status']}' state — not accepting votes.",
        )

    # Record vote.
    if body.approved:
        deployment["votes_for"] += 1
    else:
        deployment["votes_against"] += 1

    # Stub quorum: first 'approved' vote triggers deployment.
    # Production: require M-of-N threshold from cooperative governance settings.
    if not body.approved:
        deployment["status"] = "rejected"
        return {
            "deployment_id": app_id,
            "status": "rejected",
            "message": f"Deployment rejected by {body.voter_did}.",
        }

    # Approved — resume the graph past human_vote_app.
    deployment["status"] = "pulling"
    thread_id = deployment["thread_id"]
    config = {"configurable": {"thread_id": thread_id}}

    # Resume: clear requires_human_token and run from HITL breakpoint.
    resume_state = {"requires_human_token": False}

    try:
        final_state = provisioner_graph.invoke(resume_state, config=config)
    except Exception as exc:
        logger.exception("Provisioner graph resume error for %s", app_id)
        deployment["status"] = "failed"
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Deployment pipeline error: {exc}",
        )

    if final_state.get("error"):
        deployment["status"] = "failed"
        return {
            "deployment_id": app_id,
            "status": "failed",
            "error": final_state["error"],
        }

    container_id = final_state.get("container_id")
    deployment["container_id"] = container_id
    deployment["proxy_configured"] = final_state.get("proxy_configured", False)
    deployment["status"] = "running" if container_id else "failed"

    spec = final_state.get("deployment_spec") or {}
    return {
        "deployment_id": app_id,
        "status": deployment["status"],
        "container_id": (container_id or "")[:12] or None,
        "app_name": spec.get("app_name"),
        "traefik_rule": spec.get("traefik_rule"),
        "message": (
            f"App '{spec.get('app_name')}' deployed successfully. "
            f"Access at: http://{spec.get('app_name')}.{spec.get('requested_by', 'iskander.local').split('@')[-1]}"
            if deployment["status"] == "running"
            else "Deployment failed — see action log for details."
        ),
    }


# ── DELETE /apps/{app_id} ─────────────────────────────────────────────────────

@router.delete("/{app_id}", status_code=status.HTTP_202_ACCEPTED)
async def request_removal(
    app_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Request removal of a running app deployment.

    Marks the deployment as 'removal_requested' and requires a separate
    democratic vote before the container is stopped and removed.
    Container data volumes are NEVER deleted automatically.

    Production: implement a full removal HITL graph (same pattern as provisioner).
    """
    deployment = _deployments.get(app_id)
    if not deployment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found.")

    if deployment["status"] not in ("running", "stopped"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot request removal of a deployment in '{deployment['status']}' state.",
        )

    requesting_member = user.did or user.address
    deployment["status"] = "removal_requested"
    logger.info(
        "App removal requested for %s by %s", deployment["app_name"], requesting_member
    )

    return {
        "deployment_id": app_id,
        "status": "removal_requested",
        "message": (
            f"Removal of '{deployment['app_name']}' has been requested by {requesting_member}. "
            "A cooperative vote is required before the container will be stopped and removed. "
            "Data volumes will NOT be deleted — data is preserved for potential re-deployment."
        ),
    }
