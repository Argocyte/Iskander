"""
Librarian Agent tools.

Read-only access to the cooperative's knowledge commons:
  nextcloud_search      — search Nextcloud files by name and content
  nextcloud_get_document — retrieve a document's text content
  commons_search        — search the local S3 governance pattern library
"""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

_NEXTCLOUD_URL = os.environ.get("NEXTCLOUD_URL", "").rstrip("/")
_NEXTCLOUD_USERNAME = os.environ.get("NEXTCLOUD_USERNAME", "")
_NEXTCLOUD_APP_PASSWORD = os.environ.get("NEXTCLOUD_APP_PASSWORD", "")
_TIMEOUT = float(os.environ.get("LIBRARIAN_HTTP_TIMEOUT", "30"))

# Path to the governance pattern library — co-located with the Clerk's patterns
_PATTERN_LIBRARY_PATH = Path(__file__).parent.parent.parent / "governance_patterns.yaml"

# Maximum document size to retrieve (characters) — avoid huge binary files
_MAX_DOC_CHARS = 8_000


def _nc_auth() -> tuple[str, str]:
    return (_NEXTCLOUD_USERNAME, _NEXTCLOUD_APP_PASSWORD)


def _nc_available() -> bool:
    return bool(_NEXTCLOUD_URL and _NEXTCLOUD_USERNAME and _NEXTCLOUD_APP_PASSWORD)


# ---------------------------------------------------------------------------
# nextcloud_search
# ---------------------------------------------------------------------------

def nextcloud_search(query: str, limit: int = 10) -> dict:
    """
    Search Nextcloud for files matching the query.

    Uses the OCS unified search API (/ocs/v2.php/search/providers/files/search).
    Falls back to a WebDAV PROPFIND name search if the OCS endpoint returns
    no results (e.g. full-text search plugin not installed).

    Returns a list of matching files with paths, last modified, and size.
    """
    if not _nc_available():
        return {"error": "Nextcloud is not configured (NEXTCLOUD_URL / NEXTCLOUD_APP_PASSWORD)"}

    limit = max(1, min(limit, 25))
    results: list[dict] = []

    with httpx.Client(timeout=_TIMEOUT, auth=_nc_auth()) as client:
        # Try OCS unified search first (requires Nextcloud 20+)
        try:
            ocs_resp = client.get(
                f"{_NEXTCLOUD_URL}/ocs/v2.php/search/providers/files/search",
                params={"term": query, "limit": limit},
                headers={"OCS-APIREQUEST": "true", "Accept": "application/json"},
            )
            if ocs_resp.status_code == 200:
                data = ocs_resp.json()
                entries = (
                    data.get("ocs", {})
                    .get("data", {})
                    .get("entries", [])
                )
                for entry in entries[:limit]:
                    results.append({
                        "path": entry.get("resourceUrl", ""),
                        "title": entry.get("title", ""),
                        "subline": entry.get("subline", ""),
                        "modified": entry.get("attributes", {}).get("modifiedDate", ""),
                    })
        except Exception as exc:
            logger.warning("OCS search failed: %s", exc)

        # WebDAV PROPFIND fallback — searches by filename only
        if not results:
            try:
                dav_results = _webdav_name_search(client, query, limit)
                results.extend(dav_results)
            except Exception as exc:
                logger.warning("WebDAV search failed: %s", exc)

    if not results:
        return {"files": [], "message": f"No documents found matching '{query}'."}

    return {"files": results, "count": len(results)}


def _webdav_name_search(client: httpx.Client, query: str, limit: int) -> list[dict]:
    """PROPFIND on the files root and filter by name — fallback for bare Nextcloud."""
    dav_url = f"{_NEXTCLOUD_URL}/remote.php/dav/files/{_NEXTCLOUD_USERNAME}/"
    search_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<d:searchrequest xmlns:d="DAV:" xmlns:nc="http://nextcloud.org/ns">
  <d:basicsearch>
    <d:select><d:prop><d:displayname/><d:getlastmodified/><nc:size/></d:prop></d:select>
    <d:from>
      <d:scope>
        <d:href>/files/{_NEXTCLOUD_USERNAME}</d:href>
        <d:depth>infinity</d:depth>
      </d:scope>
    </d:from>
    <d:where>
      <d:like>
        <d:prop><d:displayname/></d:prop>
        <d:literal>%{query}%</d:literal>
      </d:like>
    </d:where>
    <d:orderby/>
  </d:basicsearch>
</d:searchrequest>"""

    resp = client.request(
        "SEARCH",
        dav_url,
        content=search_xml.encode(),
        headers={"Content-Type": "application/xml", "Depth": "infinity"},
    )
    resp.raise_for_status()

    # Parse minimal XML response
    results: list[dict] = []
    for href_match in re.finditer(r"<d:href>([^<]+)</d:href>", resp.text):
        path = href_match.group(1)
        if path.endswith("/"):
            continue  # skip directories
        displayname_match = re.search(
            rf"<d:href>{re.escape(path)}</d:href>.*?<d:displayname>([^<]+)</d:displayname>",
            resp.text,
            re.DOTALL,
        )
        title = displayname_match.group(1) if displayname_match else path.split("/")[-1]
        results.append({"path": path, "title": title, "subline": "", "modified": ""})
        if len(results) >= limit:
            break

    return results


# ---------------------------------------------------------------------------
# nextcloud_get_document
# ---------------------------------------------------------------------------

def nextcloud_get_document(path: str) -> dict:
    """
    Retrieve the text content of a Nextcloud document.

    ``path`` should be the WebDAV path returned by nextcloud_search, e.g.
    /remote.php/dav/files/admin/Governance/member-handbook.md

    Returns the first _MAX_DOC_CHARS characters of the document text.
    Binary files (images, PDFs without text layer) return an error.
    """
    if not _nc_available():
        return {"error": "Nextcloud is not configured"}

    # Normalise path — prepend WebDAV base if needed
    if not path.startswith("/remote.php"):
        path = f"/remote.php/dav/files/{_NEXTCLOUD_USERNAME}/{path.lstrip('/')}"

    with httpx.Client(timeout=max(_TIMEOUT, 60), auth=_nc_auth()) as client:
        resp = client.get(f"{_NEXTCLOUD_URL}{path}")

    if resp.status_code == 404:
        return {"error": f"Document not found: {path}"}
    resp.raise_for_status()

    content_type = resp.headers.get("content-type", "")
    if "text" not in content_type and "json" not in content_type and "xml" not in content_type:
        return {
            "error": "Document is not a text file and cannot be summarised directly.",
            "content_type": content_type,
            "path": path,
        }

    text = resp.text[:_MAX_DOC_CHARS]
    truncated = len(resp.text) > _MAX_DOC_CHARS

    return {
        "path": path,
        "content": text,
        "truncated": truncated,
        "total_chars": len(resp.text),
    }


# ---------------------------------------------------------------------------
# commons_search
# ---------------------------------------------------------------------------

def commons_search(query: str) -> dict:
    """
    Search the cooperative's S3 governance pattern library.

    The library is loaded from governance_patterns.yaml — a static file
    co-located with the agent code that contains S3 patterns cross-referenced
    to governance health signals.

    Returns matching patterns with their descriptions, signals, and S3 references.
    """
    if not _PATTERN_LIBRARY_PATH.exists():
        return {
            "patterns": [],
            "message": "Governance pattern library not yet available. It is populated when the Governance Health Signals feature is active.",
        }

    try:
        import yaml  # pyyaml
        raw = yaml.safe_load(_PATTERN_LIBRARY_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"error": f"Pattern library could not be loaded: {exc}"}

    patterns = raw.get("patterns", []) if isinstance(raw, dict) else []
    query_lower = query.lower()

    matches = []
    for pat in patterns:
        searchable = " ".join(str(v) for v in pat.values()).lower()
        if query_lower in searchable:
            matches.append(pat)

    if not matches:
        return {
            "patterns": [],
            "message": f"No governance patterns found matching '{query}'.",
        }

    return {"patterns": matches, "count": len(matches)}


# ---------------------------------------------------------------------------
# Tool definitions (Anthropic tool-use schema)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: list[dict] = [
    {
        "name": "nextcloud_search",
        "description": (
            "Search the cooperative's Nextcloud for documents matching a query. "
            "Searches file names and content (if full-text search is enabled). "
            "Returns a list of matching files with paths — members can open them directly in Nextcloud. "
            "Read-only — never modifies files."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search terms — file names, keywords, or topics",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results to return (1-25, default 10)",
                    "default": 10,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "nextcloud_get_document",
        "description": (
            "Retrieve the text content of a specific Nextcloud document. "
            "Use after nextcloud_search to read the content of a result. "
            "Returns up to 8,000 characters of the document. "
            "Only works on text files (markdown, plain text, HTML, JSON, XML)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": (
                        "WebDAV path to the document, as returned by nextcloud_search. "
                        "Example: /remote.php/dav/files/admin/Governance/member-handbook.md"
                    ),
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "commons_search",
        "description": (
            "Search the cooperative governance pattern library. "
            "Returns S3-aligned governance patterns relevant to the query — "
            "useful for questions like 'how have cooperatives handled X?' "
            "or 'what patterns address Y signal?'"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search terms — governance topics, signal IDs, or S3 pattern names",
                },
            },
            "required": ["query"],
        },
    },
]

TOOL_REGISTRY: dict[str, Any] = {
    "nextcloud_search": nextcloud_search,
    "nextcloud_get_document": nextcloud_get_document,
    "commons_search": commons_search,
}
