// SPDX-License-Identifier: AGPL-3.0-only
pragma solidity ^0.8.24;

/**
 * @title  TrustRegistry
 * @notice Credential Embassy Trust Registry — curated set of issuer public
 *         keys trusted for W3C Verifiable Credential signature verification.
 *
 * DESIGN PRINCIPLES:
 *   - Offline Verification: The node never pings an issuer's server. All
 *     signature checks are done against keys cached in this registry.
 *   - Council-Gated: Only cooperative members (SBT holders) can add or
 *     remove issuer keys, ensuring democratic control over trust anchors.
 *   - Tombstone Propagation: When an issuer is revoked, the IssuerRevoked
 *     event triggers off-chain agents to tombstone all credentials derived
 *     from that key. This is the on-chain signal for the Curator Network.
 *   - Immutable Audit: Every registration and revocation is logged on-chain
 *     with timestamps and rationale CIDs for Glass Box compliance.
 *
 * RED TEAM MITIGATIONS:
 *   - VULN-TR-1 (Key Squatting): Only SBT members can register keys.
 *     Re-registration of a revoked key requires explicit re-registration.
 *   - VULN-TR-2 (Mass Revocation DoS): Revocation only sets a flag; it does
 *     not iterate over credentials. Off-chain tombstoning is asynchronous.
 *   - VULN-TR-3 (Phantom Issuer): getIssuer() returns registeredAt timestamp,
 *     enabling clients to reject keys registered after a credential was issued.
 *
 * @dev    Key fingerprints are bytes32 = keccak256(DER-encoded public key).
 *         This is gas-efficient and collision-resistant for registry lookups.
 */

import {CoopIdentity} from "../CoopIdentity.sol";
import {ITrustRegistry} from "./ITrustRegistry.sol";

contract TrustRegistry is ITrustRegistry {

    // ── Immutable References ────────────────────────────────────────────────

    /// @notice CoopIdentity contract — membership gating.
    CoopIdentity public immutable coopIdentity;

    // ── Issuer Registry ─────────────────────────────────────────────────────

    struct IssuerRecord {
        string  issuerDid;        // W3C DID (e.g., did:web:university.edu)
        string  issuerName;       // Human-readable name
        string  keyType;          // "Ed25519", "ES256", "RSA2048"
        uint256 registeredAt;     // block.timestamp of registration
        uint256 revokedAt;        // 0 if active; block.timestamp if revoked
        bool    active;           // True if key is currently trusted
        address registeredBy;     // SBT member who added this key
    }

    /// @notice Issuer records indexed by key fingerprint.
    mapping(bytes32 => IssuerRecord) public issuers;

    /// @notice All registered key fingerprints (including revoked).
    bytes32[] public allFingerprints;

    /// @notice Count of currently active issuers.
    uint256 public activeCount;

    // ── Errors ──────────────────────────────────────────────────────────────

    error NotMember(address account);
    error IssuerAlreadyRegistered(bytes32 keyFingerprint);
    error IssuerNotFound(bytes32 keyFingerprint);
    error IssuerAlreadyRevoked(bytes32 keyFingerprint);
    error EmptyDid();
    error EmptyName();
    error EmptyKeyType();
    error EmptyRationale();
    error ZeroFingerprint();

    // ── Modifiers ───────────────────────────────────────────────────────────

    modifier onlyMember() {
        if (coopIdentity.balanceOf(msg.sender) == 0) revert NotMember(msg.sender);
        _;
    }

    // ── Constructor ─────────────────────────────────────────────────────────

    /**
     * @param _coopIdentity CoopIdentity contract address for membership gating.
     */
    constructor(address _coopIdentity) {
        coopIdentity = CoopIdentity(_coopIdentity);
    }

    // ── Registration ────────────────────────────────────────────────────────

    /// @inheritdoc ITrustRegistry
    function registerIssuer(
        bytes32 keyFingerprint,
        string calldata issuerDid,
        string calldata issuerName,
        string calldata keyType
    ) external onlyMember {
        if (keyFingerprint == bytes32(0)) revert ZeroFingerprint();
        if (bytes(issuerDid).length == 0) revert EmptyDid();
        if (bytes(issuerName).length == 0) revert EmptyName();
        if (bytes(keyType).length == 0) revert EmptyKeyType();

        IssuerRecord storage record = issuers[keyFingerprint];

        // Allow re-registration of a revoked issuer (new trust decision)
        if (record.registeredAt > 0 && record.active) {
            revert IssuerAlreadyRegistered(keyFingerprint);
        }

        bool isNew = (record.registeredAt == 0);

        issuers[keyFingerprint] = IssuerRecord({
            issuerDid:    issuerDid,
            issuerName:   issuerName,
            keyType:      keyType,
            registeredAt: block.timestamp,
            revokedAt:    0,
            active:       true,
            registeredBy: msg.sender
        });

        if (isNew) {
            allFingerprints.push(keyFingerprint);
        }
        activeCount += 1;

        emit IssuerRegistered(keyFingerprint, issuerDid, issuerName, msg.sender);
    }

    /// @inheritdoc ITrustRegistry
    function revokeIssuer(
        bytes32 keyFingerprint,
        string calldata rationaleIpfsCid
    ) external onlyMember {
        if (bytes(rationaleIpfsCid).length == 0) revert EmptyRationale();

        IssuerRecord storage record = issuers[keyFingerprint];
        if (record.registeredAt == 0) revert IssuerNotFound(keyFingerprint);
        if (!record.active) revert IssuerAlreadyRevoked(keyFingerprint);

        record.active = false;
        record.revokedAt = block.timestamp;
        activeCount -= 1;

        emit IssuerRevoked(
            keyFingerprint,
            record.issuerDid,
            msg.sender,
            rationaleIpfsCid
        );
    }

    // ── Queries ─────────────────────────────────────────────────────────────

    /// @inheritdoc ITrustRegistry
    function isIssuerTrusted(bytes32 keyFingerprint) external view returns (bool) {
        return issuers[keyFingerprint].active;
    }

    /// @inheritdoc ITrustRegistry
    function getIssuer(bytes32 keyFingerprint) external view returns (
        string memory issuerDid,
        string memory issuerName,
        string memory keyType,
        uint256 registeredAt,
        bool active
    ) {
        IssuerRecord storage record = issuers[keyFingerprint];
        if (record.registeredAt == 0) revert IssuerNotFound(keyFingerprint);

        return (
            record.issuerDid,
            record.issuerName,
            record.keyType,
            record.registeredAt,
            record.active
        );
    }

    /// @inheritdoc ITrustRegistry
    function issuerCount() external view returns (uint256) {
        return allFingerprints.length;
    }

    /// @inheritdoc ITrustRegistry
    function getActiveIssuers() external view returns (bytes32[] memory) {
        bytes32[] memory active = new bytes32[](activeCount);
        uint256 idx = 0;

        for (uint256 i = 0; i < allFingerprints.length; i++) {
            if (issuers[allFingerprints[i]].active) {
                active[idx] = allFingerprints[i];
                idx++;
            }
        }

        return active;
    }
}
