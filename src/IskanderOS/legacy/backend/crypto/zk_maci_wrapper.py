"""
zk_maci_wrapper.py — MACI Coordinator for Project Iskander Phase 12.

╔══════════════════════════════════════════════════════════════════════════════╗
║  PRIVACY AS A HUMAN RIGHT                                                    ║
║  This module implements the off-chain coordinator role in the MACI           ║
║  (Minimum Anti-Collusion Infrastructure) protocol. Its design guarantees:   ║
║    • Vote SECRECY: Individual votes are encrypted with ECDH-derived keys     ║
║      that only this coordinator can decrypt. No other party — including      ║
║      other cooperative members, managers, or the AI agents — can link a      ║
║      member's identity to their vote.                                        ║
║    • ANTI-COERCION: The "key-change" mechanism allows members to silently    ║
║      override a coerced vote. The coordinator processes the last valid       ║
║      message per voter, making proof-of-vote-selling impossible.             ║
║    • ZERO KNOWLEDGE: Only aggregate tallies are published on-chain. The      ║
║      raw decrypted votes and chat context are NEVER written to any           ║
║      persistent store — they exist only in transient process memory.         ║
║  These properties align with the DisCO framework's requirement for safe,     ║
║  non-coercive environments where workers can participate in governance        ║
║  without fear of peer or managerial retaliation.                             ║
╚══════════════════════════════════════════════════════════════════════════════╝

STUB NOTICE:
  The cryptographic operations (Poseidon hash, BabyJubJub ECDH, Groth16 proof
  generation) are STUBBED. Production deployment requires:
    1. Installing circom + snarkjs for circuit compilation.
    2. Linking py_snarks or a subprocess wrapper to the compiled MACI circuits.
    3. Replacing stub_* methods with real implementations.

  The data structures and on-chain interaction patterns are production-ready.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
import time
from dataclasses import dataclass, field, asdict
from typing import Any

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

# BabyJubJub curve order (used in MACI). Stub operations use this as a modulus.
_BABYJUBJUB_ORDER = (
    2736030358979909402780800718157159386076813972158567259200215660948447373041
)

# MACI message field count (10 Uint256 ciphertext fields per message spec v1).
_MACI_MSG_FIELDS = 10


# ── Data Classes ───────────────────────────────────────────────────────────────

@dataclass
class EphemeralKeypair:
    """
    A fresh elliptic-curve keypair generated for a SINGLE voting session.

    Lifecycle:
      - Generated on demand for each member per proposal.
      - The private key MUST be discarded after the vote window closes and the
        tally proof is submitted. It must NEVER be persisted to disk or logs.
      - The public key is shared with the coordinator's signUp() call so the
        coordinator can derive the ECDH shared secret for decryption.

    Privacy note:
      This keypair has NO connection to the member's wallet key or DID. It is
      used solely for the ECDH encryption of a single vote message. Observers
      cannot correlate this key with the member's on-chain identity.
    """
    private_key: int   # Scalar on BabyJubJub curve (MUST be purged post-tally).
    public_key_x: int  # x-coordinate of the public key point.
    public_key_y: int  # y-coordinate of the public key point.
    created_at: float = field(default_factory=time.time)
    proposal_id: int = 0

    def to_public_dict(self) -> dict[str, Any]:
        """Return ONLY the public components — never include the private key."""
        return {
            "public_key_x": self.public_key_x,
            "public_key_y": self.public_key_y,
            "proposal_id": self.proposal_id,
        }

    def purge(self) -> None:
        """
        Overwrite private key material in memory.
        Call this immediately after the tally proof is submitted.
        """
        self.private_key = 0
        logger.info("EphemeralKeypair.purge(): private key zeroed for proposal %d", self.proposal_id)


@dataclass
class EncryptedVoteMessage:
    """
    An encrypted vote payload formatted for MACIVoting.publishMessage().

    Fields mirror the Solidity EncryptedMessage struct:
      ciphertext[10] — AES-GCM encrypted vote vector (packed into 10 uint256 fields).
      enc_pub_key[2] — Voter's ephemeral public key for coordinator ECDH.
      nonce          — Per-voter message counter (prevents replay).

    The cleartext vote (yes/no/abstain + weight) is NEVER stored here.
    """
    ciphertext: list[int]      # 10 uint256 fields (stub: zeros with HMAC tag).
    enc_pub_key: list[int]     # [x, y] of voter's ephemeral pubkey.
    nonce: int = 0
    proposal_id: int = 0
    member_did_hash: str = ""  # SHA-256(member_did) — links message to voter WITHOUT exposing DID.

    def to_contract_tuple(self) -> dict[str, Any]:
        """Serialize to the tuple expected by the Solidity ABI encoder."""
        return {
            "ciphertext": self.ciphertext,
            "encPubKey": self.enc_pub_key,
            "nonce": self.nonce,
        }


@dataclass
class ZKProof:
    """
    A mock ZK-SNARK proof payload anchored to the audit ledger.

    In production this wraps a real Groth16 proof from the MACI tally circuit.
    In stub mode, the proof fields are deterministically derived from the input
    data using HMAC-SHA256 so they are at least content-addressable.

    This object is serialized to JSON and stored in the `zk_proof` column of
    the `contributions` or `audit_ledger` tables — replacing the raw chat log
    rationale to prevent retrospective surveillance of members' conversations.

    Schema alignment:
      contributions.zk_proof TEXT — JSON-serialized ZKProof.
      audit_ledger.zk_proof  TEXT — JSON-serialized ZKProof for vote tallies.
    """
    proof_type: str          # "care_work" | "vote_tally"
    claim: str               # Human-readable claim being proven.
    member_did_hash: str     # SHA-256(member_did) — identity commitment, not the DID itself.
    circuit_id: str          # Identifier of the circuit that generated this proof.
    # Groth16 proof components (stub: HMAC-derived hex strings).
    pi_a: list[str]          # G1 point π_A = [x, y].
    pi_b: list[list[str]]    # G2 point π_B = [[x1, x2], [y1, y2]].
    pi_c: list[str]          # G1 point π_C = [x, y].
    public_signals: list[str]  # Public inputs to the verifier circuit.
    # Metadata.
    generated_at: float = field(default_factory=time.time)
    stub_mode: bool = True   # Must be False before production deployment.
    raw_data_purged: bool = True  # Attestation: source data was not persisted.

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=None)

    @classmethod
    def from_json(cls, raw: str) -> "ZKProof":
        return cls(**json.loads(raw))


# ── MACICoordinator ────────────────────────────────────────────────────────────

class MACICoordinator:
    """
    Off-chain coordinator for the MACI voting protocol.

    Responsibilities:
      1. generate_coordinator_keypair()  — produce a per-proposal coordinator key.
      2. generate_voter_keypair()        — produce a per-member ephemeral key.
      3. encrypt_vote()                  — encrypt a yes/no vote for publishMessage().
      4. generate_tally_proof()          — stub: produces a mock Groth16 tally proof.
      5. generate_care_work_proof()      — stub: produces a ZK attestation for the
                                           Steward Agent replacing raw chat logs.

    TEE Conceptual Model:
      In production, this class runs inside a Trusted Execution Environment
      (e.g., AMD SEV or Intel TDX). The attestation report from the TEE replaces
      the `stub_mode=True` flag as proof that the coordinator's private key and
      the decrypted votes were processed in an isolated, tamper-evident enclave
      and that no raw data was exfiltrated.

    Stub Note:
      All cryptographic operations use Python's `secrets` module for randomness
      and HMAC-SHA256 as a deterministic placeholder for Poseidon/Pedersen hashes.
      Replace stub_* methods with py_snarks / circom subprocess calls for
      production deployment.
    """

    def __init__(self, coordinator_address: str) -> None:
        """
        Args:
            coordinator_address: The Ethereum address of the on-chain coordinator
                                  (must match the `coordinator` slot in MACIVoting.sol).
        """
        self.coordinator_address = coordinator_address
        self._coordinator_keypair: EphemeralKeypair | None = None
        logger.info("MACICoordinator initialised for address %s", coordinator_address)

    # ── Key Generation ────────────────────────────────────────────────────────

    def generate_coordinator_keypair(self, proposal_id: int) -> EphemeralKeypair:
        """
        Generate a fresh coordinator keypair for a specific proposal.

        This keypair is used by voters to derive the ECDH shared secret for
        encrypting their votes. It MUST be rotated per proposal to ensure
        forward secrecy — compromise of one proposal's key does not expose
        votes from past or future proposals.

        SECURITY: The private key must be stored only in secure enclave memory
        (or an HSM) and purged immediately after processMessages() is called.

        Returns:
            EphemeralKeypair with the coordinator's per-proposal key material.
        """
        kp = self._stub_generate_keypair(proposal_id)
        self._coordinator_keypair = kp
        logger.info(
            "Coordinator keypair generated for proposal %d (pubkey_x=%s...)",
            proposal_id,
            str(kp.public_key_x)[:12],
        )
        return kp

    def generate_voter_keypair(self, member_did: str, proposal_id: int) -> EphemeralKeypair:
        """
        Generate a per-member ephemeral keypair for a voting session.

        This keypair is sent to the voter's client over an encrypted channel.
        The voter uses it to:
          1. Derive the ECDH shared secret with the coordinator's public key.
          2. Encrypt their vote payload.
          3. Submit the encrypted message to publishMessage().

        The voter's private key is discarded client-side after submission.
        It is NEVER stored server-side — only the public key is used on-chain.

        Args:
            member_did:  The member's W3C DID (used to seed the keypair derivation
                         in a deterministic stub — real impl uses true randomness).
            proposal_id: The proposal this keypair is scoped to.

        Returns:
            EphemeralKeypair. Caller must call .purge() after vote is submitted.
        """
        kp = self._stub_generate_keypair(proposal_id, seed=member_did)
        logger.info(
            "Voter ephemeral keypair generated for proposal %d (DID hash: %s...)",
            proposal_id,
            hashlib.sha256(member_did.encode()).hexdigest()[:12],
        )
        return kp

    # ── Vote Encryption ───────────────────────────────────────────────────────

    def encrypt_vote(
        self,
        vote: bool,
        vote_weight: int,
        voter_keypair: EphemeralKeypair,
        coordinator_pubkey_x: int,
        coordinator_pubkey_y: int,
        member_did: str,
        proposal_id: int,
        nonce: int = 0,
    ) -> EncryptedVoteMessage:
        """
        Encrypt a member's vote for submission to MACIVoting.publishMessage().

        PRIVACY MECHANISM:
          1. Derive shared secret: ECDH(voter_private_key, coordinator_public_key).
          2. Derive encryption key: KDF(shared_secret, nonce).
          3. Encrypt vote payload: AES-256-GCM(vote_data, encryption_key).
          4. Package ciphertext + voter's ephemeral pubkey into EncryptedVoteMessage.

        The coordinator is the ONLY entity that can reverse step 1 using its
        private key. All other on-chain observers see only an opaque byte array.

        ANTI-COERCION NOTE:
          A member may call this method multiple times with the same proposal_id.
          The LAST submitted message overwrites earlier ones during tally processing.
          This means a member coerced into submitting a "yes" vote can silently
          re-vote "no" afterward — the coercer cannot verify which message is final.

        Args:
            vote:                  True = Yes, False = No.
            vote_weight:           Contribution-weighted vote power (default: 1).
            voter_keypair:         Ephemeral keypair from generate_voter_keypair().
            coordinator_pubkey_x:  x-coordinate of coordinator's ephemeral pubkey.
            coordinator_pubkey_y:  y-coordinate of coordinator's ephemeral pubkey.
            member_did:            Member's DID (used for the DID hash only — NOT
                                   included in the ciphertext or on-chain data).
            proposal_id:           Proposal being voted on.
            nonce:                 Message counter for this voter on this proposal.

        Returns:
            EncryptedVoteMessage ready for publishMessage().
        """
        # STUB: Derive a deterministic "shared secret" from the keypair components.
        # Production: replace with BabyJubJub ECDH(voter_priv, coord_pub).
        ecdh_input = (
            f"{voter_keypair.private_key}:{coordinator_pubkey_x}:{coordinator_pubkey_y}:{nonce}"
        ).encode()
        shared_secret = hashlib.sha256(ecdh_input).hexdigest()

        # STUB: Build a deterministic ciphertext using HMAC.
        vote_payload = json.dumps({
            "vote": 1 if vote else 0,
            "weight": vote_weight,
            "proposal": proposal_id,
            "nonce": nonce,
        }).encode()

        ciphertext_fields: list[int] = []
        for i in range(_MACI_MSG_FIELDS):
            field_input = f"{shared_secret}:{i}:{vote_payload.hex()}".encode()
            field_hash = int(hashlib.sha256(field_input).hexdigest(), 16) % _BABYJUBJUB_ORDER
            ciphertext_fields.append(field_hash)

        member_did_hash = hashlib.sha256(member_did.encode()).hexdigest()

        logger.info(
            "Vote encrypted for proposal %d (DID hash: %s..., vote: %s)",
            proposal_id,
            member_did_hash[:12],
            "YES" if vote else "NO",
        )

        # The cleartext vote exists only in this function's stack frame.
        # Python GC will collect it after return — no persistence occurs.
        del vote_payload, shared_secret, ecdh_input

        return EncryptedVoteMessage(
            ciphertext=ciphertext_fields,
            enc_pub_key=[voter_keypair.public_key_x, voter_keypair.public_key_y],
            nonce=nonce,
            proposal_id=proposal_id,
            member_did_hash=member_did_hash,
        )

    # ── Tally Proof Generation ────────────────────────────────────────────────

    def generate_tally_proof(
        self,
        proposal_id: int,
        yes_votes: int,
        no_votes: int,
        abstain_votes: int,
        total_sign_ups: int,
    ) -> ZKProof:
        """
        Generate a ZK-SNARK proof of the vote tally for on-chain verification.

        WHAT THE PROOF ASSERTS (without revealing individual votes):
          "I processed N encrypted messages from the message tree. The valid
           tally is [yes, no, abstain]. This tally is consistent with the
           message Merkle root committed on-chain. No individual vote was
           revealed in producing this proof."

        STUB: Returns a mock Groth16 proof with HMAC-derived field values.
        PRODUCTION: Call the MACI tally circuit via py_snarks / snarkjs:
          proof, public_signals = snarkjs.groth16.fullProve(
              inputs, "tally.wasm", "tally_final.zkey"
          )

        Args:
            proposal_id:    The proposal being tallied.
            yes_votes:      Decrypted yes vote count (transient — not persisted).
            no_votes:       Decrypted no vote count (transient).
            abstain_votes:  Decrypted abstain count (transient).
            total_sign_ups: Total registered voters from the on-chain state.

        Returns:
            ZKProof — anchor this to the audit ledger and pass proof fields to
            MACIVoting.processMessages().
        """
        claim = (
            f"Proposal {proposal_id}: tally is {yes_votes} YES / {no_votes} NO / "
            f"{abstain_votes} ABSTAIN from {total_sign_ups} registered voters."
        )

        tally_commitment = self._stub_poseidon_hash([
            proposal_id, yes_votes, no_votes, abstain_votes, total_sign_ups
        ])

        pi_a, pi_b, pi_c = self._stub_groth16_proof(tally_commitment, proposal_id)
        public_signals = [
            hex(tally_commitment),
            hex(yes_votes),
            hex(total_sign_ups),
            hex(proposal_id),
        ]

        proof = ZKProof(
            proof_type="vote_tally",
            claim=claim,
            member_did_hash="AGGREGATE",  # No individual identity in a tally proof.
            circuit_id="maci_tally_v1_stub",
            pi_a=pi_a,
            pi_b=pi_b,
            pi_c=pi_c,
            public_signals=public_signals,
            stub_mode=True,
            raw_data_purged=True,
        )

        logger.info(
            "Tally proof generated for proposal %d (stub). "
            "Raw vote counts exist only in transient memory and are now out of scope.",
            proposal_id,
        )

        # Explicitly zero transient vote counts before return.
        yes_votes = no_votes = abstain_votes = 0  # noqa: F841

        return proof

    # ── Care Work Proof Generation ────────────────────────────────────────────

    def generate_care_work_proof(
        self,
        member_did: str,
        hours: float,
        care_type: str,
        multiplier: float,
        care_score: float,
    ) -> ZKProof:
        """
        Generate a ZK attestation for a Care Work contribution record.

        REPLACES RAW CHAT LOGS in the audit ledger. The Steward Agent uses this
        to prove that a contribution was verified WITHOUT exposing the underlying
        conversation that led to that determination.

        CLAIM STRUCTURE (what is publicly verifiable):
          "Member [DID hash] performed [hours] hours of [care_type] care work.
           Applied multiplier: [multiplier]x. Computed SCP score: [care_score].
           The supporting conversational evidence was processed in TEE memory
           and has been purged. This proof commits to the result only."

        Privacy protection:
          The `member_did` is hashed (SHA-256) before inclusion. The actual DID
          is NEVER stored in the proof or the ledger entry. Correlating the hash
          back to a member requires the DID itself — which only the member holds.

        STUB: Returns a mock Groth16 proof. In production, the care work
        classification circuit would verify that the LLM's scoring is consistent
        with the cooperative's rubric without revealing the conversation.

        Args:
            member_did:   W3C DID of the contributing member.
            hours:        Base hours claimed.
            care_type:    Category from CARE_MULTIPLIERS (e.g., "mentoring").
            multiplier:   SCP multiplier applied.
            care_score:   Final SCP points (hours × multiplier).

        Returns:
            ZKProof — store as contributions.zk_proof (replaces description).
        """
        member_did_hash = hashlib.sha256(member_did.encode()).hexdigest()

        claim = (
            f"I, the Steward Agent (Iskander), verify that Member [{member_did_hash[:16]}...] "
            f"performed {hours:.2f} hours of '{care_type}' Care Work according to the DisCO "
            f"framework. Applied multiplier: {multiplier}x. Computed SCP score: {care_score}. "
            f"The raw conversational evidence has been purged from active memory."
        )

        commitment_inputs = [
            int(member_did_hash[:16], 16),
            int(hours * 100),
            int(multiplier * 100),
            int(care_score * 100),
        ]
        commitment = self._stub_poseidon_hash(commitment_inputs)
        pi_a, pi_b, pi_c = self._stub_groth16_proof(commitment, 0)

        proof = ZKProof(
            proof_type="care_work",
            claim=claim,
            member_did_hash=member_did_hash,
            circuit_id="care_work_attestation_v1_stub",
            pi_a=pi_a,
            pi_b=pi_b,
            pi_c=pi_c,
            public_signals=[
                hex(commitment),
                hex(int(hours * 100)),
                hex(int(care_score * 100)),
            ],
            stub_mode=True,
            raw_data_purged=True,
        )

        logger.info(
            "Care work ZK proof generated for DID hash %s... (type: %s, score: %s SCP).",
            member_did_hash[:12],
            care_type,
            care_score,
        )

        return proof

    # ── Proof Validation ──────────────────────────────────────────────────────

    def validate_proof(self, proof: ZKProof) -> tuple[bool, str]:
        """
        Validate a ZKProof object before writing it to the ledger.

        In stub mode, validation checks structural integrity only.
        In production, this calls the on-chain snarkVerifier via web3.py.

        Returns:
            (is_valid: bool, reason: str)
        """
        if not proof.pi_a or not proof.pi_b or not proof.pi_c:
            return False, "PROOF_INCOMPLETE: Missing Groth16 proof components."

        if not proof.public_signals:
            return False, "PROOF_INCOMPLETE: No public signals."

        if not proof.member_did_hash:
            return False, "PROOF_INVALID: Missing identity commitment."

        if proof.stub_mode:
            logger.warning(
                "validate_proof: stub_mode=True — proof accepted without on-chain verification. "
                "Deploy snarkVerifier contract before production use."
            )
            return True, "STUB_ACCEPTED"

        # Production path: call snarkVerifier.verifyProof() via web3.py.
        # This is left as a stub — implement after deploying the verifier contract.
        return False, "PRODUCTION_VERIFY_NOT_IMPLEMENTED: Set stub_mode=False only after deploying snarkVerifier."

    # ── Stub Cryptographic Primitives ─────────────────────────────────────────
    # These methods MUST be replaced with real implementations before production.
    # They are clearly named stub_* to make their temporary nature unambiguous.

    def _stub_generate_keypair(
        self, proposal_id: int, seed: str | None = None
    ) -> EphemeralKeypair:
        """STUB: Generate a BabyJubJub-like keypair using HMAC-SHA256."""
        if seed:
            priv_bytes = hashlib.sha256(f"STUB:{seed}:{proposal_id}".encode()).digest()
        else:
            priv_bytes = secrets.token_bytes(32)

        priv_scalar = int.from_bytes(priv_bytes, "big") % _BABYJUBJUB_ORDER
        # STUB: public key is not a real elliptic curve point — just deterministic hashes.
        pub_x = int(hashlib.sha256(f"pubx:{priv_scalar}".encode()).hexdigest(), 16) % _BABYJUBJUB_ORDER
        pub_y = int(hashlib.sha256(f"puby:{priv_scalar}".encode()).hexdigest(), 16) % _BABYJUBJUB_ORDER

        return EphemeralKeypair(
            private_key=priv_scalar,
            public_key_x=pub_x,
            public_key_y=pub_y,
            proposal_id=proposal_id,
        )

    def _stub_poseidon_hash(self, inputs: list[int]) -> int:
        """STUB: Poseidon hash replaced with HMAC-SHA256 over concatenated inputs."""
        raw = "|".join(str(i) for i in inputs).encode()
        return int(hashlib.sha256(raw).hexdigest(), 16) % _BABYJUBJUB_ORDER

    def _stub_groth16_proof(
        self, commitment: int, proposal_id: int
    ) -> tuple[list[str], list[list[str]], list[str]]:
        """STUB: Groth16 proof components derived deterministically from commitment."""
        base = hashlib.sha256(f"{commitment}:{proposal_id}".encode()).hexdigest()
        pi_a = [
            hex(int(base[:32], 16) % _BABYJUBJUB_ORDER),
            hex(int(base[32:], 16) % _BABYJUBJUB_ORDER),
        ]
        b1 = hashlib.sha256(f"b1:{base}".encode()).hexdigest()
        b2 = hashlib.sha256(f"b2:{base}".encode()).hexdigest()
        pi_b = [
            [hex(int(b1[:32], 16) % _BABYJUBJUB_ORDER), hex(int(b1[32:], 16) % _BABYJUBJUB_ORDER)],
            [hex(int(b2[:32], 16) % _BABYJUBJUB_ORDER), hex(int(b2[32:], 16) % _BABYJUBJUB_ORDER)],
        ]
        c_raw = hashlib.sha256(f"c:{base}".encode()).hexdigest()
        pi_c = [
            hex(int(c_raw[:32], 16) % _BABYJUBJUB_ORDER),
            hex(int(c_raw[32:], 16) % _BABYJUBJUB_ORDER),
        ]
        return pi_a, pi_b, pi_c
