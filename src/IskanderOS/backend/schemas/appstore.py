"""
Pydantic schemas for Phase 13: Democratic App Store.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AppRequest(BaseModel):
    """A member's natural-language request to deploy an app."""
    requested_by: str = Field(..., description="Member DID submitting the request.")
    description: str = Field(
        ...,
        min_length=5,
        description="Natural-language description of what the member needs.",
    )
    # Optional: preferred app name / image if the member already knows what they want.
    preferred_app: str | None = Field(None, description="Optional preferred app name from catalog.")


class AppCatalogEntry(BaseModel):
    """A single entry in the vetted FOSS app catalog."""
    name: str
    docker_image: str
    description: str
    default_port: int
    category: str                           # e.g. "collaboration", "devops", "planning"
    resource_limits: dict[str, Any] = {}    # default CPU/memory limits
    environment: dict[str, str] = {}        # required env vars (values are placeholders)
    volumes: list[str] = []                 # named volume mounts
    traefik_path_prefix: str | None = None  # e.g. "/nextcloud" for path-based routing


class DeploymentSpec(BaseModel):
    """Compiled deployment specification produced by the Provisioner Agent."""
    app_name: str
    docker_image: str
    container_name: str = Field(..., description="Unique container name (iskander_<app>).")
    port_mapping: dict[str, int] = Field(
        ...,
        description="{'host_port': N, 'container_port': N}",
    )
    traefik_rule: str = Field(
        ...,
        description="Traefik Host/PathPrefix rule, e.g. 'PathPrefix(`/gitea`)'",
    )
    resource_limits: dict[str, Any] = {}
    environment: dict[str, str] = {}
    volumes: list[str] = []
    requested_by: str


class AppStatus(BaseModel):
    """Runtime status of a deployed app."""
    deployment_id: UUID
    app_name: str
    container_id: str | None
    container_name: str
    status: str  # proposed | approved | pulling | running | stopped | failed | removed
    traefik_rule: str | None
    port_mapping: dict[str, Any] | None
    approved_at: str | None


class AppVoteRequest(BaseModel):
    """A member's vote on a proposed app deployment."""
    voter_did: str
    approved: bool
    reason: str = ""
