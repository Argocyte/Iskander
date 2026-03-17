// SPDX-License-Identifier: AGPL-3.0-only
pragma solidity ^0.8.24;

/**
 * @title  ITrustRegistry
 * @notice Interface for the Credential Embassy Trust Registry.
 *
 * Manages a curated set of issuer public keys (e.g., University root keys,
 * cooperative federation signing keys) that the local node trusts for
 * W3C Verifiable Credential signature verification.
 *
 * DESIGN:
 *   - Only StewardshipCouncil members can add/remove issuer keys.
 *   - Issuer keys are stored as bytes32 fingerprints (keccak256 of the DER-
 *     encoded public key) to keep storage costs minimal.
 *   - When an issuer key is removed, the contract emits IssuerRevoked so
 *     off-chain agents can tombstone any credentials derived from that key.
 *   - No live connection to issuers is required — verification is purely
 *     signature-based against the cached registry.
 *
 * @dev    See TrustRegistry.sol for the full implementation.
 */
interface ITrustRegistry {

    // ── Events ──────────────────────────────────────────────────────────────

    /// @notice Emitted when a new issuer key is registered.
    event IssuerRegistered(
        bytes32 indexed keyFingerprint,
        string  issuerDid,
        string  issuerName,
        address indexed registeredBy
    );

    /// @notice Emitted when an issuer key is revoked/removed.
    event IssuerRevoked(
        bytes32 indexed keyFingerprint,
        string  issuerDid,
        address indexed revokedBy,
        string  rationaleIpfsCid
    );

    /// @notice Emitted when an issuer's metadata is updated.
    event IssuerUpdated(
        bytes32 indexed keyFingerprint,
        string  issuerDid,
        address indexed updatedBy
    );

    // ── Registration ────────────────────────────────────────────────────────

    /// @notice Register a trusted issuer public key.
    /// @param  keyFingerprint  keccak256 hash of the issuer's DER-encoded public key.
    /// @param  issuerDid       W3C DID of the issuer (e.g., did:web:university.edu).
    /// @param  issuerName      Human-readable name (e.g., "University of Mondragon").
    /// @param  keyType         Key algorithm identifier (e.g., "Ed25519", "ES256").
    function registerIssuer(
        bytes32 keyFingerprint,
        string calldata issuerDid,
        string calldata issuerName,
        string calldata keyType
    ) external;

    /// @notice Revoke an issuer key. Emits IssuerRevoked for tombstone processing.
    /// @param  keyFingerprint    The key to revoke.
    /// @param  rationaleIpfsCid  IPFS CID of the Glass Box rationale document.
    function revokeIssuer(
        bytes32 keyFingerprint,
        string calldata rationaleIpfsCid
    ) external;

    // ── Queries ─────────────────────────────────────────────────────────────

    /// @notice Check if an issuer key is currently trusted.
    /// @param  keyFingerprint The key fingerprint to check.
    /// @return trusted        True if the key is registered and not revoked.
    function isIssuerTrusted(bytes32 keyFingerprint) external view returns (bool trusted);

    /// @notice Get issuer metadata by key fingerprint.
    /// @param  keyFingerprint The key to query.
    /// @return issuerDid      W3C DID of the issuer.
    /// @return issuerName     Human-readable name.
    /// @return keyType        Key algorithm identifier.
    /// @return registeredAt   Timestamp of registration.
    /// @return active         Whether the key is currently trusted.
    function getIssuer(bytes32 keyFingerprint) external view returns (
        string memory issuerDid,
        string memory issuerName,
        string memory keyType,
        uint256 registeredAt,
        bool active
    );

    /// @notice Get the total number of registered issuers (including revoked).
    function issuerCount() external view returns (uint256);

    // ── Bulk Queries ────────────────────────────────────────────────────────

    /// @notice Get all currently active issuer key fingerprints.
    /// @return fingerprints Array of active key fingerprints.
    function getActiveIssuers() external view returns (bytes32[] memory fingerprints);
}
