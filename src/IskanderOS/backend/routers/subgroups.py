# backend/routers/subgroups.py
"""
subgroups.py — Working Group management for Iskander OS.

Sub-groups are lightweight working groups within a cooperative
(e.g. Finance Committee, Tech Working Group). They scope deliberation
threads and proposals to relevant members without requiring separate
CoopIdentity SBTs — governance stays at the cooperative level.

Endpoints:
  GET  /subgroups                     — list all working groups
  POST /subgroups                     — create (steward only)
  GET  /subgroups/{id}/members        — list members of a working group
  POST /subgroups/{id}/members        — add member
  DELETE /subgroups/{id}/members/{did} — remove member
"""
from __future__ import annotations

import logging
import uuid

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status

from backend.auth.dependencies import AuthenticatedUser, get_current_user, require_role
from backend.db import get_db
from backend.schemas.deliberation import (
    SubGroupCreate,
    SubGroupMemberAdd,
    SubGroupMemberResponse,
    SubGroupResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subgroups", tags=["subgroups"])


# ── GET /subgroups ────────────────────────────────────────────────────────────

@router.get("", response_model=list[SubGroupResponse])
async def list_subgroups(
    conn: asyncpg.Connection = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
) -> list[SubGroupResponse]:
    """Return all working groups in the cooperative."""
    rows = await conn.fetch(
        "SELECT id::text, slug, name, description, created_by, created_at "
        "FROM sub_groups ORDER BY name"
    )
    return [SubGroupResponse(**dict(r)) for r in rows]


# ── POST /subgroups ───────────────────────────────────────────────────────────

@router.post("", response_model=SubGroupResponse, status_code=status.HTTP_201_CREATED)
async def create_subgroup(
    req: SubGroupCreate,
    conn: asyncpg.Connection = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role("steward")),
) -> SubGroupResponse:
    """Create a new working group (steward-only)."""
    try:
        row = await conn.fetchrow(
            """
            INSERT INTO sub_groups (slug, name, description, created_by)
            VALUES ($1, $2, $3, $4)
            RETURNING id::text, slug, name, description, created_by, created_at
            """,
            req.slug, req.name, req.description, req.created_by,
        )
    except asyncpg.UniqueViolationError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Sub-group slug '{req.slug}' already exists",
        )
    return SubGroupResponse(**dict(row))


# ── GET /subgroups/{id}/members ───────────────────────────────────────────────

@router.get("/{subgroup_id}/members", response_model=list[SubGroupMemberResponse])
async def list_members(
    subgroup_id: str,
    conn: asyncpg.Connection = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
) -> list[SubGroupMemberResponse]:
    """List members of a working group."""
    rows = await conn.fetch(
        "SELECT sub_group_id::text, member_did, role, joined_at "
        "FROM sub_group_members WHERE sub_group_id = $1 ORDER BY joined_at",
        uuid.UUID(subgroup_id),
    )
    return [SubGroupMemberResponse(**dict(r)) for r in rows]


# ── POST /subgroups/{id}/members ──────────────────────────────────────────────

@router.post("/{subgroup_id}/members", response_model=SubGroupMemberResponse,
             status_code=status.HTTP_201_CREATED)
async def add_member(
    subgroup_id: str,
    req: SubGroupMemberAdd,
    conn: asyncpg.Connection = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role("steward", "worker-owner")),
) -> SubGroupMemberResponse:
    """Add a member to a working group."""
    try:
        row = await conn.fetchrow(
            """
            INSERT INTO sub_group_members (sub_group_id, member_did, role)
            VALUES ($1, $2, $3)
            RETURNING sub_group_id::text, member_did, role, joined_at
            """,
            uuid.UUID(subgroup_id), req.member_did, req.role.value,
        )
    except asyncpg.UniqueViolationError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Member already in this working group",
        )
    return SubGroupMemberResponse(**dict(row))


# ── DELETE /subgroups/{id}/members/{did} ──────────────────────────────────────

@router.delete("/{subgroup_id}/members/{member_did}",
               status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    subgroup_id: str,
    member_did: str,
    conn: asyncpg.Connection = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role("steward")),
) -> None:
    """Remove a member from a working group (steward only)."""
    result = await conn.execute(
        "DELETE FROM sub_group_members WHERE sub_group_id = $1 AND member_did = $2",
        uuid.UUID(subgroup_id), member_did,
    )
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Member not found in this working group")
