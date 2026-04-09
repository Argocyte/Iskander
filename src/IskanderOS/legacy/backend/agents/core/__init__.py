"""
backend.agents.core — Shared prompt infrastructure for all Iskander agents.

Provides dynamic prompt loading, persona injection, and the Glass Box
output parser with retry logic and human-yield failsafe.
"""
from __future__ import annotations

from pathlib import Path

# ── Module constants ──────────────────────────────────────────────────────────
CORE_DIR: Path = Path(__file__).parent

# Cache: filename -> contents (read once per process lifetime).
_prompt_cache: dict[str, str] = {}


def load_prompt(filename: str) -> str:
    """Load a `.txt` prompt template from the ``core/`` directory.

    Results are cached in-process so disk I/O happens only on first call.

    Parameters
    ----------
    filename:
        Name of the file inside ``backend/agents/core/`` (e.g. ``"base_prompt.txt"``).

    Returns
    -------
    str
        Raw text contents of the prompt file, ready for placeholder substitution.

    Raises
    ------
    FileNotFoundError
        If *filename* does not exist in the ``core/`` directory.
    """
    if filename not in _prompt_cache:
        path = CORE_DIR / filename
        if not path.exists():
            raise FileNotFoundError(
                f"Prompt file not found: {path}. "
                f"Available: {[p.name for p in CORE_DIR.glob('*.txt')]}"
            )
        _prompt_cache[filename] = path.read_text(encoding="utf-8")
    return _prompt_cache[filename]
