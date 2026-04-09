"""
IPFS Kubo API client.

Pins decision payloads to IPFS and returns the content identifier (CID).
The CID is stored alongside the decision record — anyone can verify the
payload hasn't been tampered with by fetching it from IPFS and comparing.

Uses the Kubo HTTP API (not the deprecated go-ipfs-api Python library).
"""
from __future__ import annotations

import io
import json
import logging
import os

import httpx

logger = logging.getLogger(__name__)

IPFS_API = os.environ.get("IPFS_API_URL", "http://ipfs:5001")
_client = httpx.Client(timeout=30)


def pin_json(data: dict) -> str:
    """
    Serialise `data` to canonical JSON, add it to IPFS, and pin it locally.
    Returns the CIDv1 string (base32).

    The canonical JSON serialisation (sorted keys, no whitespace) ensures that
    two identical payloads always produce the same CID, making the hash
    independently verifiable.
    """
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    content = canonical.encode("utf-8")

    # POST to /api/v0/add with pin=true
    resp = _client.post(
        f"{IPFS_API}/api/v0/add",
        params={"pin": "true", "cid-version": "1", "hash": "sha2-256"},
        files={"file": ("decision.json", io.BytesIO(content), "application/json")},
    )
    resp.raise_for_status()
    result = resp.json()
    cid = result["Hash"]
    logger.info("Pinned to IPFS: %s (%.0f bytes)", cid, len(content))
    return cid


def is_available() -> bool:
    """Health check — returns True if the IPFS node is reachable."""
    try:
        _client.post(f"{IPFS_API}/api/v0/id", timeout=5).raise_for_status()
        return True
    except Exception:
        return False
