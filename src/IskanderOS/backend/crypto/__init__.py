"""
backend.crypto
~~~~~~~~~~~~~~
Phase 12: ZK-Democracy cryptographic primitives.

Exports:
  MACICoordinator — ephemeral key generation, vote encryption, tally proof stubs.
  ZKProof         — dataclass representing a mock ZK-SNARK proof payload.
"""
from backend.crypto.zk_maci_wrapper import MACICoordinator, ZKProof

__all__ = ["MACICoordinator", "ZKProof"]
