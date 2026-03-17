#!/usr/bin/env python3
"""
atecc_provision.py — ATECC608B Secure Element Provisioning Script

License: CERN-OHL-S v2 / MIT (software component)
Run once during first-boot setup flow.

SECURITY POSTURE:
    The ATECC608B stores ECC-P256 private keys in hardware. Private key material
    never leaves the chip — only public keys and signatures are exported.
    This is the only acceptable key storage model for a cooperative node:
    no passphrase, no HSM cloud service, no trusted third party.

KEY SLOT ASSIGNMENTS:
    Slot 0: Web3 Safe multi-sig signing key
            Used by the Iskander OS Web3 daemon to co-sign Gnosis Safe transactions.
            Once locked, this slot cannot be erased without destroying the chip.

    Slot 1: Node TLS identity key
            Used for mutual TLS authentication between federated Hearth nodes.
            The node's DID document references this key's public component.

    Slots 2–15: Reserved. Not provisioned here.

FAILURE POLICY:
    Any provisioning step failure writes a sovereignty lock and aborts.
    The node MUST NOT be deployed without a successfully provisioned ATECC608B.
    Re-run this script with --force to reprovision (WARNING: destroys existing keys).

USAGE:
    python3 atecc_provision.py [--verify] [--force] [--bus N] [--addr 0xNN]

    --verify  : Read and print public keys from provisioned slots (non-destructive)
    --force   : Re-provision even if slots are already written (DESTRUCTIVE)
    --bus N   : I2C bus number (default: 1)
    --addr    : I2C address in hex (default: 0x60)

Dependencies:
    pip install cryptoauthlib
"""

from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import sys
import time

log = logging.getLogger("hearth.atecc_provision")

try:
    from cryptoauthlib import (
        atcab_init,
        atcab_release,
        atcab_get_pubkey,
        atcab_genkey,
        atcab_info,
        atcab_is_locked,
        atcab_lock_config_zone,
        atcab_lock_data_zone,
        atcab_write_config_zone,
        cfg_ateccx08a_i2c_default,
        ATCA_SUCCESS,
    )
    CRYPTOAUTHLIB_AVAILABLE = True
except ImportError:
    CRYPTOAUTHLIB_AVAILABLE = False

# ── Configuration ─────────────────────────────────────────────────────────────

SLOT_WEB3_SIGNING   = 0   # Web3 Safe multi-sig signing key
SLOT_NODE_IDENTITY  = 1   # Node TLS / DID identity key

SOVEREIGNTY_LOCK_PATH = os.environ.get(
    "HEARTH_SOVEREIGNTY_LOCK", "/run/iskander/sovereignty.lock"
)

PROVISIONING_RECORD_PATH = os.environ.get(
    "HEARTH_PROVISION_RECORD", "/etc/iskander/atecc_provisioning.json"
)


# ── Sovereignty lock ──────────────────────────────────────────────────────────

def _write_sovereignty_lock(reason: str) -> None:
    lock_dir = os.path.dirname(SOVEREIGNTY_LOCK_PATH)
    os.makedirs(lock_dir, exist_ok=True)
    with open(SOVEREIGNTY_LOCK_PATH, "w") as f:
        f.write(f"LOCKED: {reason}\nTimestamp: {time.time()}\n")
    log.critical("SOVEREIGNTY LOCK: %s", reason)


def _clear_sovereignty_lock() -> None:
    try:
        os.remove(SOVEREIGNTY_LOCK_PATH)
    except FileNotFoundError:
        pass


# ── Low-level helpers ─────────────────────────────────────────────────────────

def _check_lib() -> None:
    if not CRYPTOAUTHLIB_AVAILABLE:
        _write_sovereignty_lock("cryptoauthlib_not_installed")
        log.critical(
            "cryptoauthlib not installed. Run: pip install cryptoauthlib\n"
            "ATECC608B provisioning cannot proceed. Node is NOT deployment-ready."
        )
        sys.exit(1)


def _init_device(i2c_bus: int, address: int) -> None:
    """Initialize cryptoauthlib I2C connection to ATECC608B."""
    cfg = cfg_ateccx08a_i2c_default()
    cfg.cfg.atcai2c.bus     = i2c_bus
    cfg.cfg.atcai2c.address = address << 1  # cryptoauthlib expects 8-bit address
    status = atcab_init(cfg)
    if status != ATCA_SUCCESS:
        raise RuntimeError(
            f"atcab_init failed with status 0x{status:02X}. "
            "ATECC608B not responding — check I2C wiring and address (0x60)."
        )
    log.info("ATECC608B connected at I2C 0x%02X bus %d.", address, i2c_bus)


def _read_info() -> bytes:
    """Read device revision info bytes."""
    info = bytearray(4)
    status = atcab_info(info)
    if status != ATCA_SUCCESS:
        raise RuntimeError(f"atcab_info failed: 0x{status:02X}")
    return bytes(info)


def _is_locked(zone: int) -> bool:
    """Check if a zone is locked. zone=0=config, zone=1=data."""
    locked = bytearray(1)
    status = atcab_is_locked(zone, locked)
    if status != ATCA_SUCCESS:
        raise RuntimeError(f"atcab_is_locked failed: 0x{status:02X}")
    return bool(locked[0])


def _genkey(slot: int) -> bytes:
    """Generate a new ECC-P256 key in the specified slot. Returns 64-byte public key."""
    pub_key = bytearray(64)
    status = atcab_genkey(slot, pub_key)
    if status != ATCA_SUCCESS:
        raise RuntimeError(
            f"atcab_genkey failed for slot {slot}: 0x{status:02X}. "
            "Ensure data zone is not locked before first provisioning."
        )
    return bytes(pub_key)


def _get_pubkey(slot: int) -> bytes:
    """Read existing public key from provisioned slot."""
    pub_key = bytearray(64)
    status = atcab_get_pubkey(slot, pub_key)
    if status != ATCA_SUCCESS:
        raise RuntimeError(f"atcab_get_pubkey failed for slot {slot}: 0x{status:02X}")
    return bytes(pub_key)


def _pubkey_to_uncompressed_hex(raw_64: bytes) -> str:
    """Convert 64-byte raw ECC public key to 0x04-prefixed uncompressed hex."""
    return "04" + raw_64.hex()


def _save_provisioning_record(slots: dict[str, str]) -> None:
    """Write public keys to provisioning record for node identity and audit."""
    record_dir = os.path.dirname(PROVISIONING_RECORD_PATH)
    os.makedirs(record_dir, exist_ok=True)
    record = {
        "provisioned_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "atecc608b_i2c_address": "0x60",
        "slots": slots,
        "warning": (
            "Private keys never leave the ATECC608B hardware. "
            "This file contains only public keys and is safe to store on disk."
        ),
    }
    with open(PROVISIONING_RECORD_PATH, "w") as f:
        json.dump(record, f, indent=2)
    log.info("Provisioning record saved: %s", PROVISIONING_RECORD_PATH)


# ── Provisioning flow ─────────────────────────────────────────────────────────

def provision(i2c_bus: int, address: int, force: bool) -> None:
    """
    Full provisioning flow:
    1. Verify chip identity.
    2. Check lock state.
    3. Generate keys in slots 0 and 1.
    4. Lock config and data zones.
    5. Save public key record.
    """
    log.info("Starting ATECC608B provisioning (force=%s).", force)

    _init_device(i2c_bus, address)

    info = _read_info()
    log.info("Device info bytes: %s", info.hex())

    config_locked = _is_locked(0)
    data_locked   = _is_locked(1)
    log.info("Zone lock state — config: %s  data: %s", config_locked, data_locked)

    if data_locked and not force:
        log.warning(
            "Data zone already locked. Run with --force to reprovision (DESTRUCTIVE). "
            "Use --verify to read existing public keys."
        )
        return

    # Generate Web3 multi-sig signing key
    log.info("Generating Web3 signing key in slot %d...", SLOT_WEB3_SIGNING)
    web3_pubkey = _genkey(SLOT_WEB3_SIGNING)
    log.info("Slot %d public key: %s", SLOT_WEB3_SIGNING, _pubkey_to_uncompressed_hex(web3_pubkey))

    # Generate node TLS identity key
    log.info("Generating node identity key in slot %d...", SLOT_NODE_IDENTITY)
    node_pubkey = _genkey(SLOT_NODE_IDENTITY)
    log.info("Slot %d public key: %s", SLOT_NODE_IDENTITY, _pubkey_to_uncompressed_hex(node_pubkey))

    # Lock config zone if not already locked
    if not config_locked:
        log.warning("Locking config zone (irreversible)...")
        status = atcab_lock_config_zone()
        if status != ATCA_SUCCESS:
            raise RuntimeError(f"atcab_lock_config_zone failed: 0x{status:02X}")
        log.info("Config zone locked.")

    # Lock data zone
    if not data_locked:
        log.warning("Locking data zone (irreversible — keys are now permanent)...")
        status = atcab_lock_data_zone()
        if status != ATCA_SUCCESS:
            raise RuntimeError(f"atcab_lock_data_zone failed: 0x{status:02X}")
        log.info("Data zone locked.")

    _save_provisioning_record({
        "slot_0_web3_signing": {
            "purpose": "Web3 Safe multi-sig signing key",
            "public_key_uncompressed": _pubkey_to_uncompressed_hex(web3_pubkey),
            "public_key_b64": base64.b64encode(web3_pubkey).decode(),
        },
        "slot_1_node_identity": {
            "purpose": "Node TLS / DID identity key",
            "public_key_uncompressed": _pubkey_to_uncompressed_hex(node_pubkey),
            "public_key_b64": base64.b64encode(node_pubkey).decode(),
        },
    })

    _clear_sovereignty_lock()
    log.info("Provisioning complete. ATECC608B is deployment-ready.")


def verify(i2c_bus: int, address: int) -> None:
    """Read and print public keys from provisioned slots (non-destructive)."""
    log.info("Verifying ATECC608B provisioning (read-only).")
    _init_device(i2c_bus, address)

    for slot, label in [
        (SLOT_WEB3_SIGNING,  "Web3 multi-sig signing"),
        (SLOT_NODE_IDENTITY, "Node TLS identity"),
    ]:
        try:
            pub = _get_pubkey(slot)
            print(f"\nSlot {slot} [{label}]")
            print(f"  Uncompressed hex: {_pubkey_to_uncompressed_hex(pub)}")
            print(f"  Base64: {base64.b64encode(pub).decode()}")
        except RuntimeError as exc:
            print(f"\nSlot {slot} [{label}]: ERROR — {exc}")
            _write_sovereignty_lock(f"atecc_verify_slot{slot}_failed")
            sys.exit(1)

    log.info("Verification complete.")


# ── CLI entry point ───────────────────────────────────────────────────────────

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Provision or verify the Solidarity HAT ATECC608B secure element."
    )
    parser.add_argument("--verify", action="store_true", help="Read-only verification mode")
    parser.add_argument("--force",  action="store_true", help="Re-provision (DESTRUCTIVE)")
    parser.add_argument("--bus",  type=int, default=1,    help="I2C bus number (default: 1)")
    parser.add_argument("--addr", type=lambda x: int(x, 0), default=0x60,
                        help="I2C address (default: 0x60)")
    args = parser.parse_args()

    _check_lib()

    try:
        if args.verify:
            verify(args.bus, args.addr)
        else:
            provision(args.bus, args.addr, force=args.force)
    except RuntimeError as exc:
        log.critical("Provisioning failed: %s", exc)
        _write_sovereignty_lock(f"atecc_provision_failed: {exc}")
        sys.exit(1)
    finally:
        try:
            atcab_release()
        except Exception:
            pass


if __name__ == "__main__":
    main()
