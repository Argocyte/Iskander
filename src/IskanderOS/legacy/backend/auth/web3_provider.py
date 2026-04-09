"""
web3_provider.py — Phase 19: Shared Web3 Provider for Gnosis Chain / Anvil.

Provides a singleton Web3 instance connected to the configured EVM RPC.
Includes fallback logic for Gnosis Chain public RPCs.

Replaces ad-hoc Web3 instantiation scattered across routers and agents.
"""
from __future__ import annotations

import logging
from functools import lru_cache

from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

from backend.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_web3() -> Web3:
    """Return a shared Web3 instance connected to the configured RPC.

    Uses `settings.evm_rpc_url` as the primary endpoint. For Gnosis Chain
    (chain ID 100), injects POA middleware for xDAI compatibility.

    Falls back to `settings.gnosis_rpc_fallback` if the primary fails.
    """
    primary_url = settings.evm_rpc_url
    w3 = Web3(Web3.HTTPProvider(primary_url))

    if w3.is_connected():
        logger.info("Web3 connected to primary RPC: %s", primary_url)
    else:
        # Try fallback for Gnosis Chain
        fallback_url = getattr(settings, "gnosis_rpc_fallback", "")
        if fallback_url:
            logger.warning(
                "Primary RPC %s unreachable, trying fallback: %s",
                primary_url,
                fallback_url,
            )
            w3 = Web3(Web3.HTTPProvider(fallback_url))
            if w3.is_connected():
                logger.info("Web3 connected to fallback RPC: %s", fallback_url)
            else:
                logger.error("Both primary and fallback RPCs unreachable")
        else:
            logger.warning("Web3 not connected to %s (no fallback configured)", primary_url)

    # Gnosis Chain (and other POA chains) return >32-byte extraData.
    # This middleware normalizes it so web3.py doesn't raise.
    if settings.evm_chain_id in (100, 10200):  # Gnosis mainnet + Chiado testnet
        w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        logger.info("POA middleware injected for chain ID %d", settings.evm_chain_id)

    return w3


def get_web3_fresh() -> Web3:
    """Return a new (non-cached) Web3 instance.

    Use when you need a separate connection (e.g., for background tasks
    that shouldn't share the request-serving connection).
    """
    get_web3.cache_clear()
    return get_web3()
