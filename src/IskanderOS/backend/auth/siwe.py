"""
siwe.py — Phase 19: Sign-In with Ethereum (EIP-4361) Verification.

Handles SIWE message parsing, EIP-191 signature verification for EOA wallets,
and EIP-1271 signature verification for Smart Contract wallets (Gnosis Safe).

Dependencies: siwe, web3, eth_account
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from eth_account.messages import encode_defunct
from web3 import Web3

from backend.auth.web3_provider import get_web3
from backend.config import settings

logger = logging.getLogger(__name__)

# EIP-1271 magic value returned by isValidSignature when signature is valid.
EIP1271_MAGIC_VALUE = bytes.fromhex("1626ba7e")

# Minimal ABI for EIP-1271 isValidSignature (used by Gnosis Safe).
EIP1271_ABI = [
    {
        "inputs": [
            {"name": "_hash", "type": "bytes32"},
            {"name": "_signature", "type": "bytes"},
        ],
        "name": "isValidSignature",
        "outputs": [{"name": "", "type": "bytes4"}],
        "stateMutability": "view",
        "type": "function",
    }
]


@dataclass
class SiweVerificationResult:
    """Result of verifying a SIWE message + signature."""

    address: str          # Checksummed Ethereum address
    chain_id: int         # Chain ID from the SIWE message
    domain: str           # Domain that issued the SIWE message
    nonce: str            # Server-issued nonce
    issued_at: str        # ISO-8601 timestamp
    is_smart_contract: bool  # True if verified via EIP-1271 (Safe)


def verify_siwe_message(
    message: str,
    signature: str,
    expected_nonce: str | None = None,
    expected_domain: str | None = None,
) -> SiweVerificationResult:
    """Parse and verify a SIWE (EIP-4361) message + signature.

    Attempts EOA verification first (EIP-191). If that fails and the address
    is a smart contract, falls back to EIP-1271 (Safe multi-sig).

    Parameters
    ----------
    message:
        The raw SIWE message string.
    signature:
        The hex-encoded signature (with or without 0x prefix).
    expected_nonce:
        If provided, the message nonce must match.
    expected_domain:
        If provided, the message domain must match.

    Returns
    -------
    SiweVerificationResult with the verified address and metadata.

    Raises
    ------
    ValueError:
        If the signature is invalid or the message fails validation.
    """
    # Parse the SIWE message fields.
    parsed = _parse_siwe_message(message)
    address = parsed["address"]
    chain_id = parsed["chain_id"]
    domain = parsed["domain"]
    nonce = parsed["nonce"]
    issued_at = parsed.get("issued_at", "")

    # Validate nonce if expected.
    if expected_nonce and nonce != expected_nonce:
        raise ValueError(f"Nonce mismatch: expected {expected_nonce}, got {nonce}")

    # Validate domain if expected.
    if expected_domain and domain != expected_domain:
        raise ValueError(f"Domain mismatch: expected {expected_domain}, got {domain}")

    # Validate chain ID.
    if chain_id != settings.evm_chain_id:
        # Allow both Gnosis (100) and Anvil (31337) during development.
        if settings.evm_chain_id == 31337 or chain_id == 31337:
            logger.warning(
                "Chain ID mismatch (expected=%d, got=%d) — allowed in dev mode",
                settings.evm_chain_id,
                chain_id,
            )
        else:
            raise ValueError(
                f"Chain ID mismatch: expected {settings.evm_chain_id}, got {chain_id}"
            )

    # Check expiration if present.
    expiration = parsed.get("expiration_time")
    if expiration:
        exp_dt = datetime.fromisoformat(expiration.replace("Z", "+00:00"))
        if exp_dt < datetime.now(timezone.utc):
            raise ValueError("SIWE message has expired")

    # Normalize signature.
    sig_bytes = bytes.fromhex(signature.removeprefix("0x"))

    # Try EOA verification first (EIP-191).
    is_smart_contract = False
    try:
        recovered = _recover_eoa_address(message, sig_bytes)
        if recovered.lower() != address.lower():
            raise ValueError("EOA signature recovery mismatch")
        address = Web3.to_checksum_address(recovered)
    except (ValueError, Exception) as eoa_err:
        # EOA verification failed — try EIP-1271 (smart contract wallet).
        logger.debug("EOA verification failed (%s), trying EIP-1271", eoa_err)
        try:
            valid = verify_eip1271_signature(address, message, sig_bytes)
            if not valid:
                raise ValueError("EIP-1271 signature verification returned false")
            is_smart_contract = True
            address = Web3.to_checksum_address(address)
        except Exception as sc_err:
            raise ValueError(
                f"Signature verification failed for both EOA and EIP-1271: "
                f"EOA={eoa_err}, EIP-1271={sc_err}"
            ) from sc_err

    logger.info(
        "SIWE verified: address=%s, chain=%d, smart_contract=%s",
        address,
        chain_id,
        is_smart_contract,
    )

    return SiweVerificationResult(
        address=address,
        chain_id=chain_id,
        domain=domain,
        nonce=nonce,
        issued_at=issued_at,
        is_smart_contract=is_smart_contract,
    )


def verify_eip1271_signature(
    contract_address: str,
    message: str,
    signature: bytes,
) -> bool:
    """Verify a signature using EIP-1271 isValidSignature on a smart contract.

    This is used for Gnosis Safe multi-sig wallets where the "signer" is the
    Safe contract itself, not an individual EOA.

    Parameters
    ----------
    contract_address:
        The checksummed address of the smart contract (e.g., the Safe).
    message:
        The original message that was signed.
    signature:
        The raw signature bytes.

    Returns
    -------
    True if the contract returns the EIP-1271 magic value.
    """
    w3 = get_web3()

    # Hash the message the same way as EIP-191 personal_sign.
    message_hash = w3.keccak(
        text=f"\x19Ethereum Signed Message:\n{len(message)}{message}"
    )

    contract = w3.eth.contract(
        address=Web3.to_checksum_address(contract_address),
        abi=EIP1271_ABI,
    )

    try:
        result = contract.functions.isValidSignature(
            message_hash, signature
        ).call()
        return result[:4] == EIP1271_MAGIC_VALUE
    except Exception as exc:
        logger.warning(
            "EIP-1271 call failed for %s: %s",
            contract_address,
            exc,
        )
        return False


def _recover_eoa_address(message: str, signature: bytes) -> str:
    """Recover the EOA address from an EIP-191 personal_sign signature."""
    from eth_account import Account

    msg = encode_defunct(text=message)
    return Account.recover_message(msg, signature=signature)


def _parse_siwe_message(message: str) -> dict[str, Any]:
    """Parse a SIWE (EIP-4361) message into its component fields.

    SIWE message format (RFC):
        {domain} wants you to sign in with your Ethereum account:
        {address}

        {statement}

        URI: {uri}
        Version: {version}
        Chain ID: {chain_id}
        Nonce: {nonce}
        Issued At: {issued_at}
        [Expiration Time: {expiration_time}]
        [Resources:
          - {resource_1}
          - {resource_2}]
    """
    lines = message.strip().split("\n")
    result: dict[str, Any] = {}

    if not lines:
        raise ValueError("Empty SIWE message")

    # Line 0: "{domain} wants you to sign in with your Ethereum account:"
    first_line = lines[0]
    if "wants you to sign in" not in first_line:
        raise ValueError(f"Invalid SIWE message header: {first_line}")
    result["domain"] = first_line.split(" wants you to sign in")[0].strip()

    # Line 1: Ethereum address
    if len(lines) < 2:
        raise ValueError("SIWE message missing address line")
    result["address"] = lines[1].strip()

    # Parse key-value fields from remaining lines.
    for line in lines[2:]:
        line = line.strip()
        if line.startswith("URI:"):
            result["uri"] = line[4:].strip()
        elif line.startswith("Version:"):
            result["version"] = line[8:].strip()
        elif line.startswith("Chain ID:"):
            result["chain_id"] = int(line[9:].strip())
        elif line.startswith("Nonce:"):
            result["nonce"] = line[6:].strip()
        elif line.startswith("Issued At:"):
            result["issued_at"] = line[10:].strip()
        elif line.startswith("Expiration Time:"):
            result["expiration_time"] = line[16:].strip()

    # Validate required fields.
    for field in ("address", "domain", "chain_id", "nonce"):
        if field not in result:
            raise ValueError(f"SIWE message missing required field: {field}")

    return result
