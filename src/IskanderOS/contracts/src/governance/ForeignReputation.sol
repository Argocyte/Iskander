// SPDX-License-Identifier: AGPL-3.0-only
pragma solidity ^0.8.24;

/**
 * @title  ForeignReputation
 * @notice Foreign Reputation System (FRS) — exponential-decay scoring for
 *         foreign Sovereign Data Containers (SDCs) interacting with the
 *         local cooperative.
 *
 * DESIGN PRINCIPLES:
 *   - Lazy Decay: Scores decay exponentially toward zero based on elapsed
 *     time since last update. Decay is computed on-read (getCurrentScore),
 *     not via cron or keeper. This means storage writes only happen on
 *     actual transactions, keeping gas costs proportional to real activity.
 *
 *   - Tier-Based Access: Four tiers (Quarantine → Provisional → Trusted →
 *     Allied) derived from the decayed score. The Python AccessMiddleware
 *     queries getCurrentTier() to gate IPFS reads and federation endpoints.
 *
 *   - Valueflows Anchoring: Every score update references an IPFS CID of the
 *     Valueflows EconomicEvent that triggered it. This creates an auditable
 *     chain linking on-chain reputation to off-chain cooperative transactions.
 *
 *   - Council Override: StewardshipCouncil can force-quarantine any SDC
 *     regardless of score (e.g., during a governance crisis). Force-quarantine
 *     locks the tier to 0 until explicitly lifted.
 *
 *   - Oracle Timelock: Oracle rotation uses the same 48h timelock pattern as
 *     StewardshipLedger, preventing instant takeover of the scoring oracle.
 *
 * EXPONENTIAL DECAY FORMULA:
 *   decayedScore = rawScore * 2^(-elapsed / halfLife)
 *
 *   Implemented via fixed-point arithmetic to avoid floating-point:
 *     decayedScore = rawScore >> (elapsed / halfLife)
 *     with linear interpolation for fractional half-lives.
 *
 * RED TEAM MITIGATIONS:
 *   - VULN-FRS-1 (Score Inflation): scoreDelta capped at ±MAX_DELTA_PER_TX.
 *     No single transaction can move the score by more than 500 bps (5%).
 *   - VULN-FRS-2 (Oracle Takeover): 48h timelock on oracle rotation.
 *   - VULN-FRS-3 (Quarantine Bypass): forceQuarantined flag checked BEFORE
 *     score-based tier computation. Cannot be overridden by high scores.
 *   - VULN-FRS-4 (Stale Score Exploitation): Decay is always applied on read.
 *     An SDC that stops transacting will naturally decay to Quarantine tier.
 *
 * @dev    Scores stored as basis points (0–10000). Half-life default: 30 days.
 */

import {CoopIdentity}       from "../CoopIdentity.sol";
import {IForeignReputation}  from "./IForeignReputation.sol";

contract ForeignReputation is IForeignReputation {

    // ── Constants ────────────────────────────────────────────────────────────

    /// @notice Maximum score in basis points.
    uint256 public constant MAX_SCORE = 10000;

    /// @notice Maximum absolute delta per transaction (VULN-FRS-1 mitigation).
    uint256 public constant MAX_DELTA_PER_TX = 500;

    /// @notice Oracle rotation timelock (48 hours, matching StewardshipLedger).
    uint256 public constant ORACLE_TIMELOCK = 48 hours;

    /// @notice Default half-life for exponential decay (30 days).
    uint256 public constant DEFAULT_HALF_LIFE = 30 days;

    // ── Immutable References ────────────────────────────────────────────────

    /// @notice CoopIdentity contract — membership gating.
    CoopIdentity public immutable coopIdentity;

    // ── Oracle ──────────────────────────────────────────────────────────────

    /// @notice Address authorised to record transactions and update config.
    address public oracle;

    /// @notice Pending oracle address awaiting timelock expiry.
    address public pendingOracle;

    /// @notice Timestamp after which the pending oracle can accept the role.
    uint256 public pendingOracleActivation;

    // ── Tier Thresholds (basis points) ──────────────────────────────────────

    /// @notice Score below which an SDC is in Quarantine (tier 0).
    uint256 public quarantineThreshold;

    /// @notice Score below which an SDC is Provisional (tier 1).
    uint256 public provisionalThreshold;

    /// @notice Score at or above which an SDC is Allied (tier 3).
    uint256 public trustedThreshold;

    // ── Decay Configuration ─────────────────────────────────────────────────

    /// @notice Half-life for exponential decay in seconds.
    uint256 public decayHalfLife;

    // ── SDC Profiles ────────────────────────────────────────────────────────

    struct SDCProfile {
        uint256 rawScore;          // Score before decay (basis points)
        uint256 lastUpdated;       // block.timestamp of last score update
        bool    registered;        // True once registerSDC has been called
        bool    forceQuarantined;  // Council override — locks tier to 0
        uint256 txCount;           // Total Valueflows transactions recorded
    }

    /// @notice Per-SDC reputation profiles. Key = keccak256(DID).
    mapping(bytes32 => SDCProfile) public profiles;

    // ── Errors ──────────────────────────────────────────────────────────────

    error NotOracle();
    error NotMember(address account);
    error NotPendingOracle();
    error TimelockActive(uint256 activationTime);
    error ZeroAddress();
    error SDCAlreadyRegistered(bytes32 sdcId);
    error SDCNotRegistered(bytes32 sdcId);
    error DeltaExceedsLimit(int256 delta, uint256 maxDelta);
    error ScoreExceedsMax(uint256 score);
    error InvalidThresholds();
    error ZeroHalfLife();
    error EmptyRationale();

    // ── Modifiers ───────────────────────────────────────────────────────────

    modifier onlyOracle() {
        if (msg.sender != oracle) revert NotOracle();
        _;
    }

    modifier onlyMember() {
        if (coopIdentity.balanceOf(msg.sender) == 0) revert NotMember(msg.sender);
        _;
    }

    // ── Constructor ─────────────────────────────────────────────────────────

    /**
     * @param _coopIdentity        CoopIdentity contract address.
     * @param _oracle              Initial oracle address.
     * @param _quarantineThreshold Score below this = Quarantine (tier 0).
     * @param _provisionalThreshold Score below this = Provisional (tier 1).
     * @param _trustedThreshold    Score at/above this = Allied (tier 3).
     */
    constructor(
        address _coopIdentity,
        address _oracle,
        uint256 _quarantineThreshold,
        uint256 _provisionalThreshold,
        uint256 _trustedThreshold
    ) {
        if (_coopIdentity == address(0)) revert ZeroAddress();
        if (_oracle == address(0)) revert ZeroAddress();
        if (_quarantineThreshold >= _provisionalThreshold ||
            _provisionalThreshold >= _trustedThreshold ||
            _trustedThreshold > MAX_SCORE) {
            revert InvalidThresholds();
        }

        coopIdentity = CoopIdentity(_coopIdentity);
        oracle = _oracle;
        quarantineThreshold = _quarantineThreshold;
        provisionalThreshold = _provisionalThreshold;
        trustedThreshold = _trustedThreshold;
        decayHalfLife = DEFAULT_HALF_LIFE;
    }

    // ── Registration ────────────────────────────────────────────────────────

    /// @inheritdoc IForeignReputation
    function registerSDC(bytes32 sdcId, uint256 initialScore) external onlyOracle {
        if (profiles[sdcId].registered) revert SDCAlreadyRegistered(sdcId);
        if (initialScore > MAX_SCORE) revert ScoreExceedsMax(initialScore);

        profiles[sdcId] = SDCProfile({
            rawScore:         initialScore,
            lastUpdated:      block.timestamp,
            registered:       true,
            forceQuarantined: false,
            txCount:          0
        });

        emit SDCRegistered(sdcId, msg.sender);
    }

    // ── Score Updates ───────────────────────────────────────────────────────

    /// @inheritdoc IForeignReputation
    function recordTransaction(
        bytes32 sdcId,
        int256  scoreDelta,
        string calldata txCid
    ) external onlyOracle {
        SDCProfile storage profile = profiles[sdcId];
        if (!profile.registered) revert SDCNotRegistered(sdcId);

        // VULN-FRS-1: Cap delta magnitude
        uint256 absDelta = scoreDelta >= 0 ? uint256(scoreDelta) : uint256(-scoreDelta);
        if (absDelta > MAX_DELTA_PER_TX) revert DeltaExceedsLimit(scoreDelta, MAX_DELTA_PER_TX);

        // Apply decay to get current effective score, then apply delta
        uint256 currentScore = _computeDecayedScore(
            profile.rawScore,
            profile.lastUpdated
        );

        uint256 previousScore = currentScore;
        uint8 previousTier = _scoreTier(currentScore, profile.forceQuarantined);

        // Apply delta with clamping
        if (scoreDelta >= 0) {
            currentScore += uint256(scoreDelta);
            if (currentScore > MAX_SCORE) currentScore = MAX_SCORE;
        } else {
            uint256 penalty = uint256(-scoreDelta);
            if (penalty > currentScore) {
                currentScore = 0;
            } else {
                currentScore -= penalty;
            }
        }

        // Store the new score as the new raw score (decay resets from now)
        profile.rawScore = currentScore;
        profile.lastUpdated = block.timestamp;
        profile.txCount += 1;

        emit ScoreUpdated(sdcId, previousScore, currentScore, txCid);

        // Check for tier change
        uint8 newTier = _scoreTier(currentScore, profile.forceQuarantined);
        if (newTier != previousTier) {
            emit TierChanged(sdcId, previousTier, newTier);
        }
    }

    // ── Queries ─────────────────────────────────────────────────────────────

    /// @inheritdoc IForeignReputation
    function getCurrentScore(bytes32 sdcId) external view returns (uint256) {
        SDCProfile storage profile = profiles[sdcId];
        if (!profile.registered) revert SDCNotRegistered(sdcId);
        return _computeDecayedScore(profile.rawScore, profile.lastUpdated);
    }

    /// @inheritdoc IForeignReputation
    function getCurrentTier(bytes32 sdcId) external view returns (uint8) {
        SDCProfile storage profile = profiles[sdcId];
        if (!profile.registered) revert SDCNotRegistered(sdcId);
        uint256 score = _computeDecayedScore(profile.rawScore, profile.lastUpdated);
        return _scoreTier(score, profile.forceQuarantined);
    }

    /// @inheritdoc IForeignReputation
    function getSDCProfile(bytes32 sdcId) external view returns (
        uint256 rawScore,
        uint256 lastUpdated,
        bool    forceQuarantined
    ) {
        SDCProfile storage profile = profiles[sdcId];
        if (!profile.registered) revert SDCNotRegistered(sdcId);
        return (profile.rawScore, profile.lastUpdated, profile.forceQuarantined);
    }

    // ── Council Actions ─────────────────────────────────────────────────────

    /// @inheritdoc IForeignReputation
    function forceQuarantine(
        bytes32 sdcId,
        string calldata rationaleIpfsCid
    ) external onlyMember {
        SDCProfile storage profile = profiles[sdcId];
        if (!profile.registered) revert SDCNotRegistered(sdcId);
        if (bytes(rationaleIpfsCid).length == 0) revert EmptyRationale();

        profile.forceQuarantined = true;

        emit SDCForceQuarantined(sdcId, rationaleIpfsCid);
    }

    /// @inheritdoc IForeignReputation
    function liftQuarantine(bytes32 sdcId) external onlyOracle {
        SDCProfile storage profile = profiles[sdcId];
        if (!profile.registered) revert SDCNotRegistered(sdcId);

        profile.forceQuarantined = false;

        emit SDCQuarantineLifted(sdcId);
    }

    // ── Oracle Timelock ─────────────────────────────────────────────────────

    /// @inheritdoc IForeignReputation
    function proposeOracle(address newOracle) external onlyOracle {
        if (newOracle == address(0)) revert ZeroAddress();
        pendingOracle = newOracle;
        pendingOracleActivation = block.timestamp + ORACLE_TIMELOCK;
        emit OracleProposed(newOracle, pendingOracleActivation);
    }

    /// @inheritdoc IForeignReputation
    function acceptOracle() external {
        if (msg.sender != pendingOracle) revert NotPendingOracle();
        if (block.timestamp < pendingOracleActivation) revert TimelockActive(pendingOracleActivation);
        oracle = pendingOracle;
        pendingOracle = address(0);
        pendingOracleActivation = 0;
        emit OracleAccepted(oracle);
    }

    // ── Configuration ───────────────────────────────────────────────────────

    /// @inheritdoc IForeignReputation
    function setTierThresholds(
        uint256 quarantine,
        uint256 provisional,
        uint256 trusted
    ) external onlyOracle {
        if (quarantine >= provisional ||
            provisional >= trusted ||
            trusted > MAX_SCORE) {
            revert InvalidThresholds();
        }
        quarantineThreshold = quarantine;
        provisionalThreshold = provisional;
        trustedThreshold = trusted;
    }

    /// @inheritdoc IForeignReputation
    function setDecayHalfLife(uint256 newHalfLifeSeconds) external onlyOracle {
        if (newHalfLifeSeconds == 0) revert ZeroHalfLife();
        decayHalfLife = newHalfLifeSeconds;
    }

    // ── Internal: Exponential Decay ─────────────────────────────────────────

    /**
     * @dev Compute decayed score using bit-shift approximation of 2^(-t/halfLife).
     *
     *      Full half-lives are handled by right-shifting (dividing by 2).
     *      The fractional remainder is linearly interpolated between the
     *      two nearest half-life boundaries for gas-efficient approximation.
     *
     *      For example, with halfLife = 30 days:
     *        - At t = 0 days:  score = rawScore
     *        - At t = 30 days: score = rawScore / 2
     *        - At t = 60 days: score = rawScore / 4
     *        - At t = 45 days: score ≈ rawScore * 0.354 (interpolated)
     *
     *      After 13 full half-lives, score is guaranteed to be 0 (2^13 > 10000).
     */
    function _computeDecayedScore(
        uint256 rawScore,
        uint256 lastUpdated
    ) internal view returns (uint256) {
        if (rawScore == 0) return 0;
        if (block.timestamp <= lastUpdated) return rawScore;

        uint256 elapsed = block.timestamp - lastUpdated;
        uint256 fullHalfLives = elapsed / decayHalfLife;

        // After 13 half-lives, any score ≤ 10000 becomes 0
        if (fullHalfLives >= 13) return 0;

        // Apply full half-lives via bit shift
        uint256 decayed = rawScore >> fullHalfLives;
        if (decayed == 0) return 0;

        // Linear interpolation for fractional half-life
        uint256 remainder = elapsed % decayHalfLife;
        if (remainder > 0) {
            // Interpolate: decayed - (decayed * remainder) / (2 * halfLife)
            // This approximates the curve between two half-life points
            uint256 nextHalfLife = decayed >> 1; // score at next full half-life
            uint256 fractionalDecay = ((decayed - nextHalfLife) * remainder) / decayHalfLife;
            decayed -= fractionalDecay;
        }

        return decayed;
    }

    /**
     * @dev Compute access tier from a (already-decayed) score.
     *      Force-quarantine overrides all tiers to 0.
     */
    function _scoreTier(
        uint256 score,
        bool    forceQuarantined
    ) internal view returns (uint8) {
        // VULN-FRS-3: Force-quarantine checked BEFORE score-based tier
        if (forceQuarantined) return 0;

        if (score < quarantineThreshold)  return 0; // Quarantine
        if (score < provisionalThreshold) return 1; // Provisional
        if (score < trustedThreshold)     return 2; // Trusted
        return 3;                                    // Allied
    }
}
