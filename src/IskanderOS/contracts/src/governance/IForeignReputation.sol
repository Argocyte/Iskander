// SPDX-License-Identifier: AGPL-3.0-only
pragma solidity ^0.8.24;

/**
 * @title  IForeignReputation
 * @notice Interface for the Foreign Reputation System (FRS).
 *
 * Manages exponential-decay reputation scores for foreign Sovereign Data
 * Containers (SDCs) interacting with the local cooperative. Scores decay
 * toward a baseline over time unless refreshed by new Valueflows transactions.
 *
 * Tier-based access:
 *   Tier 0  (Quarantine)  : score < quarantineThreshold  — sandbox only
 *   Tier 1  (Provisional) : score < provisionalThreshold  — read + limited write
 *   Tier 2  (Trusted)     : score < trustedThreshold      — full federation
 *   Tier 3  (Allied)      : score >= trustedThreshold      — deep integration
 *
 * @dev    Scores stored as basis points (0–10000). Decay is lazy-evaluated:
 *         computed on read, not via cron. See ForeignReputation.sol.
 */
interface IForeignReputation {

    // ── Events ──────────────────────────────────────────────────────────────

    /// @notice Emitted when a foreign SDC is first registered.
    event SDCRegistered(bytes32 indexed sdcId, address indexed registeredBy);

    /// @notice Emitted when a Valueflows transaction updates an SDC's score.
    event ScoreUpdated(
        bytes32 indexed sdcId,
        uint256 previousScore,
        uint256 newScore,
        string  txCid
    );

    /// @notice Emitted when an SDC's tier changes after a score update.
    event TierChanged(
        bytes32 indexed sdcId,
        uint8   previousTier,
        uint8   newTier
    );

    /// @notice Emitted when the oracle is rotated via timelock.
    event OracleProposed(address indexed newOracle, uint256 activationTime);
    event OracleAccepted(address indexed newOracle);

    /// @notice Emitted when an SDC is manually quarantined by the council.
    event SDCForceQuarantined(bytes32 indexed sdcId, string rationaleIpfsCid);

    /// @notice Emitted when a quarantine is lifted.
    event SDCQuarantineLifted(bytes32 indexed sdcId);

    // ── Registration ────────────────────────────────────────────────────────

    /// @notice Register a new foreign SDC with an initial score.
    /// @param  sdcId       Keccak256 hash of the SDC's DID.
    /// @param  initialScore Starting reputation in basis points (0–10000).
    function registerSDC(bytes32 sdcId, uint256 initialScore) external;

    // ── Score Updates ───────────────────────────────────────────────────────

    /// @notice Record a Valueflows transaction outcome and update the SDC's score.
    /// @param  sdcId       The SDC being scored.
    /// @param  scoreDelta  Signed delta in basis points (positive = reward, negative = penalty).
    /// @param  txCid       IPFS CID of the Valueflows EconomicEvent.
    function recordTransaction(bytes32 sdcId, int256 scoreDelta, string calldata txCid) external;

    // ── Queries ─────────────────────────────────────────────────────────────

    /// @notice Get the current score after applying exponential decay.
    /// @param  sdcId The SDC to query.
    /// @return score The decayed score in basis points.
    function getCurrentScore(bytes32 sdcId) external view returns (uint256 score);

    /// @notice Get the current access tier (0–3) after applying decay.
    /// @param  sdcId The SDC to query.
    /// @return tier  The access tier.
    function getCurrentTier(bytes32 sdcId) external view returns (uint8 tier);

    /// @notice Get the raw (un-decayed) score and last-update timestamp.
    /// @param  sdcId The SDC to query.
    /// @return rawScore     The stored score before decay.
    /// @return lastUpdated  The block.timestamp of the last score update.
    /// @return forceQuarantined Whether the SDC is manually quarantined.
    function getSDCProfile(bytes32 sdcId) external view returns (
        uint256 rawScore,
        uint256 lastUpdated,
        bool    forceQuarantined
    );

    // ── Council Actions ─────────────────────────────────────────────────────

    /// @notice Force-quarantine an SDC (council override). Tier locked to 0.
    /// @param  sdcId             The SDC to quarantine.
    /// @param  rationaleIpfsCid  IPFS CID of the Glass Box rationale.
    function forceQuarantine(bytes32 sdcId, string calldata rationaleIpfsCid) external;

    /// @notice Lift a force-quarantine. Score resumes normal decay.
    /// @param  sdcId The SDC to un-quarantine.
    function liftQuarantine(bytes32 sdcId) external;

    // ── Oracle Timelock ─────────────────────────────────────────────────────

    /// @notice Propose a new oracle address with a timelock.
    function proposeOracle(address newOracle) external;

    /// @notice Accept the oracle role after the timelock has expired.
    function acceptOracle() external;

    // ── Configuration ───────────────────────────────────────────────────────

    /// @notice Update tier thresholds. Only callable by oracle.
    function setTierThresholds(
        uint256 quarantine,
        uint256 provisional,
        uint256 trusted
    ) external;

    /// @notice Update the decay rate. Only callable by oracle.
    /// @param  newHalfLifeSeconds New half-life for exponential decay.
    function setDecayHalfLife(uint256 newHalfLifeSeconds) external;
}
