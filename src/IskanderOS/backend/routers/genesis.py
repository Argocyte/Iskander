"""
Genesis Boot Sequence — FastAPI Router.

Prefix: /genesis
Tags: ["genesis-boot"]
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from backend.auth.dependencies import verify_founder_token
from backend.config import settings
from backend.schemas.genesis import (
    BootRequest,
    BylawsUploadRequest,
    FounderRegisterRequest,
    FounderRegisterResponse,
    GenesisMode,
    GenesisStatusResponse,
    ModeSelectRequest,
    RatifyRequest,
    RuleConfirmRequest,
    TemplateSelectRequest,
    TierAssignRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/genesis", tags=["genesis-boot"])

_boot_state: dict[str, Any] = {
    "boot_complete": False,
    "mode": None,
    "boot_phase": "pre-genesis",
    "founders": {},
    "thread_id": None,
}


def _check_not_complete():
    latch_file = Path(settings.genesis_boot_complete_file)
    if _boot_state["boot_complete"] or latch_file.exists():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Genesis boot sequence already complete. This is a one-way operation.",
        )


@router.get("/status", response_model=GenesisStatusResponse)
async def get_status():
    latch_file = Path(settings.genesis_boot_complete_file)
    is_complete = _boot_state["boot_complete"] or latch_file.exists()
    return GenesisStatusResponse(
        status="complete" if is_complete else _boot_state["boot_phase"],
        mode=_boot_state.get("mode"),
        boot_phase=_boot_state["boot_phase"],
        founder_count=len(_boot_state.get("founders", {})),
        boot_complete=is_complete,
    )


@router.post("/founders/register", response_model=FounderRegisterResponse)
async def register_founder(req: FounderRegisterRequest):
    _check_not_complete()
    if req.did in _boot_state.get("founders", {}):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Founder {req.did} already registered.")
    from backend.auth.dependencies import generate_founder_token
    token, token_hash = generate_founder_token()
    _boot_state.setdefault("founders", {})[req.did] = {
        "did": req.did, "address": req.address, "name": req.name, "founder_token_hash": token_hash,
    }
    return FounderRegisterResponse(did=req.did, address=req.address, founder_token=token)


@router.get("/founders")
async def list_founders():
    founders = _boot_state.get("founders", {})
    return {
        "founders": [{"did": f["did"], "address": f["address"], "name": f["name"]} for f in founders.values()],
        "count": len(founders),
    }


@router.post("/boot")
async def start_boot(req: BootRequest):
    _check_not_complete()
    _boot_state["mode"] = req.mode.value
    _boot_state["boot_phase"] = "in-progress"
    _boot_state["thread_id"] = str(uuid4())
    return {"status": "boot-started", "mode": req.mode.value, "thread_id": _boot_state["thread_id"]}


@router.post("/mode")
async def select_mode(req: ModeSelectRequest, founder: dict = Depends(verify_founder_token)):
    _check_not_complete()
    _boot_state["mode"] = req.mode.value
    return {"mode": req.mode.value}


@router.post("/bylaws/upload")
async def upload_bylaws(req: BylawsUploadRequest, founder: dict = Depends(verify_founder_token)):
    _check_not_complete()
    return {"status": "bylaws-uploaded", "text_length": len(req.text)}


@router.get("/templates")
async def list_templates(founder: dict = Depends(verify_founder_token)):
    _check_not_complete()
    return {"templates": [], "count": 0}


@router.post("/templates/select")
async def select_template(req: TemplateSelectRequest, founder: dict = Depends(verify_founder_token)):
    _check_not_complete()
    return {"template_cid": req.template_cid, "status": "template-selected"}


@router.get("/mappings")
async def get_mappings(founder: dict = Depends(verify_founder_token)):
    _check_not_complete()
    return {"mappings": [], "status": _boot_state["boot_phase"]}


@router.post("/mappings/{rule_id}/confirm")
async def confirm_mapping(rule_id: str, req: RuleConfirmRequest, founder: dict = Depends(verify_founder_token)):
    _check_not_complete()
    return {"rule_id": rule_id, "approved": req.approved}


@router.post("/mappings/{rule_id}/assign-tier")
async def assign_tier(rule_id: str, req: TierAssignRequest, founder: dict = Depends(verify_founder_token)):
    _check_not_complete()
    return {"rule_id": rule_id, "tier": req.tier.value}


@router.get("/manifest/preview")
async def preview_manifest(founder: dict = Depends(verify_founder_token)):
    _check_not_complete()
    return {"manifest": None, "status": _boot_state["boot_phase"]}


@router.post("/ratify")
async def ratify(req: RatifyRequest, founder: dict = Depends(verify_founder_token)):
    _check_not_complete()
    return {"ratified": req.ratified, "status": "pending"}


@router.post("/recovery/resume")
async def resume_recovery(founder: dict = Depends(verify_founder_token)):
    return {"status": _boot_state["boot_phase"]}
