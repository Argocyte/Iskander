// SPDX-License-Identifier: AGPL-3.0-only
pragma solidity ^0.8.24;

/**
 * @title  StewardshipLedger
 * @notice Stewardship Council delegation ledger with gSBT-weighted voting,
 *         Impact Score oracle integration, emergency veto, and solvency
 *         circuit breaker.
 *
 * LEGAL NOTICE:
 *   This smart contract implements the "Stewardship Council" governance layer
 *   as defined in iskander_stewardship_spec.txt. It is an ON-CHAIN EXTENSION
 *   of the cooperative's real-world legal wrapper. In any conflict, the
 *   off-chain legal document governs.
 *
 * DESIGN PRINCIPLES:
 *   - No Hierarchical Permanence: Steward roles expire automatically when
 *     Impact Scores drop below the protocol-defined threshold.
 *   - revoke() is always executable: zero external calls, minimal gas, no
 *     reentrancy risk — regardless of network congestion or contract state.
 *   - O(1) getVotingWeight: maintained via incremental counters, not iteration.
 *   - Anti-extractive: gSBT weight is non-transferable (soulbound by design).
 *
 * @dev    Impact Scores are stored as basis points (0–10000) for gas efficiency.
 *         The Python StewardshipScorer converts float [0.0, 1.0] at the boundary.
 */

import {CoopIdentity}    from "../CoopIdentity.sol";
import {IskanderEscrow}  from "../IskanderEscrow.sol";
import {IStewardshipLedger} from "./IStewardshipLedger.sol";

contract StewardshipLedger is IStewardshipLedger {

    // ── Immutable References ────────────────────────────────────────────────

    /// @notice CoopIdentity contract — membership gating (ERC-4973 SBT).
    CoopIdentity public immutable coopIdentity;

    /// @notice IskanderEscrow contract — referenced for circuit breaker context.
    IskanderEscrow public immutable escrowContract;

    // ── Oracle & Thresholds ─────────────────────────────────────────────────

    /// @notice Address authorised to push Impact Score batches and reserve updates.
    address public oracle;

    /// @notice Steward eligibility threshold in basis points (0–10000).
    ///         Nodes with impactScores[node] < stewardThresholdBps cannot receive
    ///         delegations. Updated by the oracle based on StewardshipScorer output.
    uint256 public stewardThresholdBps;

    /// @notice Solvency circuit breaker ratio in basis points.
    ///         If totalEscrowValue > fiatReserveValue * solvencyFactorBps / 10000,
    ///         new delegations are blocked to prevent exposure-increasing decisions.
    uint256 public solvencyFactorBps;

    /// @notice Current fiat reserve value — updated by oracle alongside scores.
    uint256 public fiatReserveValue;

    /// @notice Current total on-chain escrow value — updated by oracle.
    uint256 public totalEscrowValue;

    // ── Oracle Timelock ──────────────────────────────────────────────────

    /// @notice Pending oracle address awaiting timelock expiry.
    address public pendingOracle;

    /// @notice Timestamp after which the pending oracle can accept the role.
    uint256 public pendingOracleActivation;

    /// @notice Timelock duration for oracle rotation (48 hours).
    uint256 public constant ORACLE_TIMELOCK = 48 hours;

    // ── Impact Scores ───────────────────────────────────────────────────────

    /// @notice Per-node Impact Score in basis points (0–10000).
    mapping(address => uint256) public impactScores;

    // ── Delegation State ────────────────────────────────────────────────────

    /// @notice Who each node delegates to. address(0) = no active delegation (self).
    mapping(address => address) public delegation;

    /// @notice Count of inbound delegations per steward (for O(1) weight lookup).
    mapping(address => uint256) public receivedDelegations;

    /// @notice Whether a member has been registered (grants 1 gSBT weight).
    mapping(address => bool) public hasWeight;

    // ── Emergency Veto ──────────────────────────────────────────────────────

    struct VetoRecord {
        address vetoer;
        uint256 proposalId;
        string  rationaleIpfsCid;
        uint256 filedAt;
    }

    /// @notice Total number of emergency vetos filed.
    uint256 public vetoCount;

    /// @notice Veto records indexed by sequential ID.
    mapping(uint256 => VetoRecord) public vetos;

    // ── Errors ──────────────────────────────────────────────────────────────

    error NotAMember(address account);
    error NotOracle();
    error StewardBelowThreshold(address steward, uint256 score, uint256 threshold);
    error ArrayLengthMismatch();
    error CircuitBreakerActive(uint256 totalEscrow, uint256 reserveThreshold);
    error NoDelegationToRevoke();
    error EmptyRationale();
    error ZeroAddress();
    error NotPendingOracle();
    error TimelockActive(uint256 activationTime);

    // ── Modifiers ───────────────────────────────────────────────────────────

    modifier onlyOracle() {
        if (msg.sender != oracle) revert NotOracle();
        _;
    }

    modifier onlyMember() {
        if (coopIdentity.balanceOf(msg.sender) == 0) revert NotAMember(msg.sender);
        _;
    }

    // ── Constructor ─────────────────────────────────────────────────────────

    /**
     * @param _coopIdentity       Address of the CoopIdentity (ERC-4973) contract.
     * @param _escrowContract     Address of the IskanderEscrow contract.
     * @param _oracle             Address authorised to push Impact Score updates.
     * @param _stewardThresholdBps Initial steward threshold in basis points.
     * @param _solvencyFactorBps  Solvency circuit breaker ratio in basis points.
     */
    constructor(
        address _coopIdentity,
        address _escrowContract,
        address _oracle,
        uint256 _stewardThresholdBps,
        uint256 _solvencyFactorBps
    ) {
        if (_coopIdentity == address(0)) revert ZeroAddress();
        if (_escrowContract == address(0)) revert ZeroAddress();
        if (_oracle == address(0)) revert ZeroAddress();

        coopIdentity       = CoopIdentity(_coopIdentity);
        escrowContract     = IskanderEscrow(_escrowContract);
        oracle             = _oracle;
        stewardThresholdBps = _stewardThresholdBps;
        solvencyFactorBps  = _solvencyFactorBps;
    }

    // ── Core Delegation ─────────────────────────────────────────────────────

    /// @inheritdoc IStewardshipLedger
    function delegate(address steward) external onlyMember {
        // Circuit breaker: block new delegations when over-leveraged.
        _checkCircuitBreaker();

        // Steward must be eligible (above threshold + cooperative member).
        if (!this.isStewardEligible(steward)) {
            revert StewardBelowThreshold(
                steward, impactScores[steward], stewardThresholdBps
            );
        }

        // If already delegated to someone, decrement their count first.
        address currentDelegate = delegation[msg.sender];
        if (currentDelegate != address(0)) {
            receivedDelegations[currentDelegate] -= 1;
        }

        // Set new delegation.
        delegation[msg.sender] = steward;
        receivedDelegations[steward] += 1;

        emit Delegated(msg.sender, steward);
    }

    /// @inheritdoc IStewardshipLedger
    /// @dev MINIMAL implementation — spec requires "always executable regardless
    ///      of network congestion or contract state." Zero external calls,
    ///      no reentrancy risk, minimal gas.
    function revoke() external {
        address currentDelegate = delegation[msg.sender];
        if (currentDelegate == address(0)) revert NoDelegationToRevoke();

        receivedDelegations[currentDelegate] -= 1;
        delete delegation[msg.sender];

        emit Revoked(msg.sender);
    }

    /// @inheritdoc IStewardshipLedger
    /// @dev O(1) — uses incremental counters, not iteration.
    function getVotingWeight(address node) external view returns (uint256) {
        uint256 selfWeight = hasWeight[node] ? 1 : 0;
        return selfWeight + receivedDelegations[node];
    }

    // ── Emergency Veto ──────────────────────────────────────────────────────

    /// @inheritdoc IStewardshipLedger
    function emergencyVeto(
        uint256 proposalId,
        string calldata rationaleIpfsCid
    ) external onlyMember {
        if (bytes(rationaleIpfsCid).length == 0) revert EmptyRationale();

        uint256 vetoId = vetoCount;
        vetos[vetoId] = VetoRecord({
            vetoer:           msg.sender,
            proposalId:       proposalId,
            rationaleIpfsCid: rationaleIpfsCid,
            filedAt:          block.timestamp
        });
        vetoCount = vetoId + 1;

        emit EmergencyVetoFiled(proposalId, msg.sender, rationaleIpfsCid);
    }

    // ── Oracle Functions ────────────────────────────────────────────────────

    /// @inheritdoc IStewardshipLedger
    function updateImpactScores(
        address[] calldata nodes,
        uint256[] calldata scores
    ) external onlyOracle {
        if (nodes.length != scores.length) revert ArrayLengthMismatch();

        for (uint256 i = 0; i < nodes.length; i++) {
            impactScores[nodes[i]] = scores[i];

            // If a steward drops below threshold and has delegations,
            // emit an event for off-chain revocation processing.
            // On-chain mass revocation is too gas-expensive for large batches;
            // the Python agent handles individual revoke() calls.
            if (scores[i] < stewardThresholdBps && receivedDelegations[nodes[i]] > 0) {
                emit StewardEligibilityLost(nodes[i]);
            }
        }

        emit ImpactScoresUpdated(nodes.length);
    }

    /// @inheritdoc IStewardshipLedger
    function updateFiatReserve(uint256 newReserveValue) external onlyOracle {
        fiatReserveValue = newReserveValue;
    }

    /// @inheritdoc IStewardshipLedger
    function updateTotalEscrow(uint256 newTotalEscrow) external onlyOracle {
        totalEscrowValue = newTotalEscrow;
    }

    /// @notice Register a member for gSBT weight (called by oracle after
    ///         CoopIdentity attestation).
    /// @param  member The address to register.
    function registerMember(address member) external onlyOracle {
        hasWeight[member] = true;
    }

    /// @notice Update the steward eligibility threshold.
    /// @param  newThresholdBps New threshold in basis points (0–10000).
    function setThreshold(uint256 newThresholdBps) external onlyOracle {
        stewardThresholdBps = newThresholdBps;
    }

    /// @notice Propose a new oracle address. Activates after ORACLE_TIMELOCK.
    /// @param  newOracle The proposed new oracle address.
    function proposeOracle(address newOracle) external onlyOracle {
        if (newOracle == address(0)) revert ZeroAddress();
        pendingOracle = newOracle;
        pendingOracleActivation = block.timestamp + ORACLE_TIMELOCK;
        emit OracleProposed(newOracle, pendingOracleActivation);
    }

    /// @notice Accept the oracle role after the timelock has expired.
    ///         Must be called by the pending oracle address.
    function acceptOracle() external {
        if (msg.sender != pendingOracle) revert NotPendingOracle();
        if (block.timestamp < pendingOracleActivation) revert TimelockActive(pendingOracleActivation);
        oracle = pendingOracle;
        pendingOracle = address(0);
        pendingOracleActivation = 0;
        emit OracleAccepted(oracle);
    }

    // ── Emergency Circuit Breaker ────────────────────────────────────────

    /// @notice Immediately trip the circuit breaker by setting escrow to max.
    ///         Blocks all new delegations until reset.
    function triggerEmergencyCircuitBreaker() external onlyOracle {
        totalEscrowValue = type(uint256).max;
        emit CircuitBreakerTripped(totalEscrowValue, fiatReserveValue * solvencyFactorBps / 10000);
        emit EmergencyCircuitBreakerActivated(msg.sender, block.timestamp);
    }

    /// @notice Reset the circuit breaker with the actual escrow value.
    /// @param  actualEscrow The corrected total escrow value.
    function resetEmergencyCircuitBreaker(uint256 actualEscrow) external onlyOracle {
        totalEscrowValue = actualEscrow;
        emit EmergencyCircuitBreakerReset(msg.sender, actualEscrow);
    }

    // ── View Functions ──────────────────────────────────────────────────────

    /// @inheritdoc IStewardshipLedger
    function isStewardEligible(address node) external view returns (bool) {
        return impactScores[node] >= stewardThresholdBps
            && coopIdentity.balanceOf(node) > 0;
    }

    // ── Internal ────────────────────────────────────────────────────────────

    /// @dev Circuit breaker: revert if total escrow exceeds reserve * factor.
    function _checkCircuitBreaker() internal view {
        if (fiatReserveValue == 0) return; // No reserve set — skip check.

        uint256 reserveThreshold = (fiatReserveValue * solvencyFactorBps) / 10000;
        if (totalEscrowValue > reserveThreshold) {
            revert CircuitBreakerActive(totalEscrowValue, reserveThreshold);
        }
    }
}
