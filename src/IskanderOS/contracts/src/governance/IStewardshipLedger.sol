// SPDX-License-Identifier: AGPL-3.0-only
pragma solidity ^0.8.24;

/**
 * @title  IStewardshipLedger
 * @notice Interface for the Stewardship Council delegation ledger.
 *
 * Defines the public API for gSBT-weighted liquid delegation, Impact Score
 * oracle updates, emergency veto, and solvency circuit breaker.
 *
 * @dev    See StewardshipLedger.sol for the full implementation.
 */
interface IStewardshipLedger {

    // ── Events ──────────────────────────────────────────────────────────────

    /// @notice Emitted when a member delegates their gSBT weight to a steward.
    event Delegated(address indexed delegator, address indexed steward);

    /// @notice Emitted when a member revokes their delegation (weight returns to self).
    event Revoked(address indexed delegator);

    /// @notice Emitted when a member files an emergency veto citing ICA Cooperative Principles.
    event EmergencyVetoFiled(
        uint256 indexed proposalId,
        address indexed vetoer,
        string  rationaleIpfsCid
    );

    /// @notice Emitted after a batch of Impact Scores is updated by the oracle.
    event ImpactScoresUpdated(uint256 batchSize);

    /// @notice Emitted when a steward's score drops below threshold, signalling
    ///         that off-chain delegation revocations should be processed.
    event StewardEligibilityLost(address indexed steward);

    /// @notice Emitted when the circuit breaker trips (total escrow > reserve limit).
    event CircuitBreakerTripped(uint256 totalEscrowValue, uint256 fiatReserveThreshold);

    /// @notice Emitted when a new oracle is proposed with a timelock.
    event OracleProposed(address indexed newOracle, uint256 activationTime);

    /// @notice Emitted when the pending oracle accepts the role after timelock.
    event OracleAccepted(address indexed newOracle);

    /// @notice Emitted when the emergency circuit breaker is manually activated.
    event EmergencyCircuitBreakerActivated(address indexed triggeredBy, uint256 timestamp);

    /// @notice Emitted when the emergency circuit breaker is reset.
    event EmergencyCircuitBreakerReset(address indexed triggeredBy, uint256 actualEscrow);

    // ── Core Delegation ─────────────────────────────────────────────────────

    /// @notice Delegate gSBT voting weight to an eligible steward.
    /// @param  steward The address of the steward to delegate to.
    function delegate(address steward) external;

    /// @notice Revoke delegation, returning gSBT weight to self.
    ///         MUST always be executable regardless of network congestion.
    function revoke() external;

    /// @notice Returns the current voting weight (self + received delegations).
    /// @param  node The address to query.
    function getVotingWeight(address node) external view returns (uint256);

    // ── Emergency Veto ──────────────────────────────────────────────────────

    /// @notice File an emergency veto against a Council decision.
    /// @param  proposalId       The ID of the proposal being vetoed.
    /// @param  rationaleIpfsCid IPFS CID of the Glass Box rationale document.
    function emergencyVeto(uint256 proposalId, string calldata rationaleIpfsCid) external;

    // ── Oracle Functions ────────────────────────────────────────────────────

    /// @notice Batch-update Impact Scores for multiple nodes.
    /// @param  nodes  Array of node addresses.
    /// @param  scores Array of scores in basis points (0–10000).
    function updateImpactScores(address[] calldata nodes, uint256[] calldata scores) external;

    /// @notice Update the fiat reserve value for circuit breaker calculations.
    /// @param  newReserveValue The new reserve value (in token smallest unit).
    function updateFiatReserve(uint256 newReserveValue) external;

    /// @notice Update the total on-chain escrow value for circuit breaker.
    /// @param  newTotalEscrow The new total escrow value.
    function updateTotalEscrow(uint256 newTotalEscrow) external;

    // ── Oracle Timelock ──────────────────────────────────────────────────

    /// @notice Propose a new oracle address with a 48-hour timelock.
    /// @param  newOracle The proposed new oracle address.
    function proposeOracle(address newOracle) external;

    /// @notice Accept the oracle role after the timelock has expired.
    function acceptOracle() external;

    // ── Emergency Circuit Breaker ────────────────────────────────────────

    /// @notice Immediately trip the circuit breaker, blocking all delegations.
    function triggerEmergencyCircuitBreaker() external;

    /// @notice Reset the circuit breaker with the corrected escrow value.
    /// @param  actualEscrow The corrected total escrow value.
    function resetEmergencyCircuitBreaker(uint256 actualEscrow) external;

    // ── View Functions ──────────────────────────────────────────────────────

    /// @notice Check if a node is eligible to receive delegations.
    /// @param  node The address to check.
    function isStewardEligible(address node) external view returns (bool);
}
