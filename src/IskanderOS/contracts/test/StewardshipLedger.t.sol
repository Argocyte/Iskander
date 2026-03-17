// SPDX-License-Identifier: AGPL-3.0-only
pragma solidity ^0.8.24;

import {Test, console2} from "forge-std/Test.sol";
import {CoopIdentity}       from "../src/CoopIdentity.sol";
import {IskanderEscrow}     from "../src/IskanderEscrow.sol";
import {StewardshipLedger}  from "../src/governance/StewardshipLedger.sol";

contract StewardshipLedgerTest is Test {
    CoopIdentity      internal identity;
    IskanderEscrow    internal escrow;
    StewardshipLedger internal ledger;

    address internal steward  = makeAddr("steward");
    address internal oracleAddr = makeAddr("oracle");
    address internal alice    = makeAddr("alice");
    address internal bob      = makeAddr("bob");
    address internal charlie  = makeAddr("charlie");
    address internal outsider = makeAddr("outsider");

    string  internal constant CID = "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi";
    string  internal constant DID = "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK";
    string  internal constant URI = "ipfs://bafybeifoo";

    uint256 internal constant THRESHOLD_BPS = 2500; // 25%
    uint256 internal constant SOLVENCY_BPS  = 10000; // 1:1

    function setUp() public {
        // Deploy CoopIdentity (no BrightID in test — address(0) disables it).
        identity = new CoopIdentity("Test Co-op", CID, steward, address(0), bytes32(0));

        // Deploy IskanderEscrow (no ArbitrationRegistry wired).
        escrow = new IskanderEscrow(address(identity), address(0));

        // Deploy StewardshipLedger.
        ledger = new StewardshipLedger(
            address(identity),
            address(escrow),
            oracleAddr,
            THRESHOLD_BPS,
            SOLVENCY_BPS
        );

        // Register members via CoopIdentity.
        vm.startPrank(steward);
        identity.attest(alice,   DID, "worker-owner", URI);
        identity.attest(bob,     DID, "worker-owner", URI);
        identity.attest(charlie, DID, "steward",      URI);
        vm.stopPrank();

        // Register members for gSBT weight via oracle.
        vm.startPrank(oracleAddr);
        ledger.registerMember(alice);
        ledger.registerMember(bob);
        ledger.registerMember(charlie);
        vm.stopPrank();
    }

    // ── Delegation Lifecycle ────────────────────────────────────────────────

    function test_delegate_revoke_cycle() public {
        // Set Bob's impact score above threshold.
        address[] memory nodes = new address[](1);
        uint256[] memory scores = new uint256[](1);
        nodes[0] = bob;
        scores[0] = 5000; // 50%

        vm.prank(oracleAddr);
        ledger.updateImpactScores(nodes, scores);

        // Alice delegates to Bob.
        vm.prank(alice);
        ledger.delegate(bob);

        // Check weights.
        assertEq(ledger.getVotingWeight(bob), 2); // 1 self + 1 delegation
        assertEq(ledger.getVotingWeight(alice), 1); // Still has self-weight
        assertEq(ledger.delegation(alice), bob);

        // Alice revokes.
        vm.prank(alice);
        ledger.revoke();

        assertEq(ledger.getVotingWeight(bob), 1); // Back to self only
        assertEq(ledger.delegation(alice), address(0));
    }

    function test_delegate_requires_membership() public {
        // Set Bob's score above threshold.
        address[] memory nodes = new address[](1);
        uint256[] memory scores = new uint256[](1);
        nodes[0] = bob;
        scores[0] = 5000;

        vm.prank(oracleAddr);
        ledger.updateImpactScores(nodes, scores);

        // Outsider (no SBT) tries to delegate — should revert.
        vm.prank(outsider);
        vm.expectRevert(abi.encodeWithSelector(StewardshipLedger.NotAMember.selector, outsider));
        ledger.delegate(bob);
    }

    function test_delegate_requires_threshold() public {
        // Bob's score is 0 (below threshold).
        vm.prank(alice);
        vm.expectRevert(
            abi.encodeWithSelector(
                StewardshipLedger.StewardBelowThreshold.selector,
                bob, 0, THRESHOLD_BPS
            )
        );
        ledger.delegate(bob);
    }

    function test_revoke_always_succeeds() public {
        // Set Bob's score above threshold.
        address[] memory nodes = new address[](1);
        uint256[] memory scores = new uint256[](1);
        nodes[0] = bob;
        scores[0] = 5000;

        vm.prank(oracleAddr);
        ledger.updateImpactScores(nodes, scores);

        // Alice delegates then revokes — must always succeed.
        vm.startPrank(alice);
        ledger.delegate(bob);
        ledger.revoke();
        vm.stopPrank();

        // Verify state is clean.
        assertEq(ledger.receivedDelegations(bob), 0);
        assertEq(ledger.delegation(alice), address(0));
    }

    function test_revoke_no_delegation_reverts() public {
        // Alice hasn't delegated — revoke should revert.
        vm.prank(alice);
        vm.expectRevert(StewardshipLedger.NoDelegationToRevoke.selector);
        ledger.revoke();
    }

    // ── Impact Score Updates ────────────────────────────────────────────────

    function test_batch_impact_update() public {
        address[] memory nodes = new address[](2);
        uint256[] memory scores = new uint256[](2);
        nodes[0] = alice;   scores[0] = 3000;
        nodes[1] = bob;     scores[1] = 7000;

        vm.prank(oracleAddr);
        ledger.updateImpactScores(nodes, scores);

        assertEq(ledger.impactScores(alice), 3000);
        assertEq(ledger.impactScores(bob), 7000);
        assertTrue(ledger.isStewardEligible(bob));
        assertTrue(ledger.isStewardEligible(alice)); // 3000 >= 2500
    }

    function test_batch_update_emits_eligibility_lost() public {
        // Bob starts above threshold with a delegation.
        address[] memory nodes = new address[](1);
        uint256[] memory scores = new uint256[](1);
        nodes[0] = bob;
        scores[0] = 5000;

        vm.prank(oracleAddr);
        ledger.updateImpactScores(nodes, scores);

        vm.prank(alice);
        ledger.delegate(bob);

        // Now drop Bob's score below threshold.
        scores[0] = 1000; // Below 2500

        vm.prank(oracleAddr);
        vm.expectEmit(true, false, false, false);
        emit StewardshipLedger.StewardEligibilityLost(bob);
        ledger.updateImpactScores(nodes, scores);
    }

    function test_update_scores_array_mismatch_reverts() public {
        address[] memory nodes = new address[](2);
        uint256[] memory scores = new uint256[](1);
        nodes[0] = alice;
        nodes[1] = bob;
        scores[0] = 5000;

        vm.prank(oracleAddr);
        vm.expectRevert(StewardshipLedger.ArrayLengthMismatch.selector);
        ledger.updateImpactScores(nodes, scores);
    }

    function test_update_scores_only_oracle() public {
        address[] memory nodes = new address[](1);
        uint256[] memory scores = new uint256[](1);
        nodes[0] = alice;
        scores[0] = 5000;

        vm.prank(alice);
        vm.expectRevert(StewardshipLedger.NotOracle.selector);
        ledger.updateImpactScores(nodes, scores);
    }

    // ── Emergency Veto ──────────────────────────────────────────────────────

    function test_emergency_veto_emits_event() public {
        string memory rationale = "bafybeiveto123";

        vm.prank(alice);
        vm.expectEmit(true, true, false, true);
        emit IStewardshipLedger.EmergencyVetoFiled(42, alice, rationale);
        ledger.emergencyVeto(42, rationale);

        assertEq(ledger.vetoCount(), 1);
        (address vetoer, uint256 proposalId, , uint256 filedAt) = ledger.vetos(0);
        assertEq(vetoer, alice);
        assertEq(proposalId, 42);
        assertGt(filedAt, 0);
    }

    function test_veto_requires_rationale() public {
        vm.prank(alice);
        vm.expectRevert(StewardshipLedger.EmptyRationale.selector);
        ledger.emergencyVeto(42, "");
    }

    function test_veto_requires_membership() public {
        vm.prank(outsider);
        vm.expectRevert(abi.encodeWithSelector(StewardshipLedger.NotAMember.selector, outsider));
        ledger.emergencyVeto(42, "bafybeiveto123");
    }

    // ── Circuit Breaker ─────────────────────────────────────────────────────

    function test_circuit_breaker_prevents_delegation() public {
        // Set Bob eligible.
        address[] memory nodes = new address[](1);
        uint256[] memory scores = new uint256[](1);
        nodes[0] = bob;
        scores[0] = 5000;

        vm.startPrank(oracleAddr);
        ledger.updateImpactScores(nodes, scores);
        // Set reserve to 1000, escrow to 1500 — exceeds 1:1 ratio.
        ledger.updateFiatReserve(1000);
        ledger.updateTotalEscrow(1500);
        vm.stopPrank();

        vm.prank(alice);
        vm.expectRevert(
            abi.encodeWithSelector(StewardshipLedger.CircuitBreakerActive.selector, 1500, 1000)
        );
        ledger.delegate(bob);
    }

    function test_circuit_breaker_skips_when_no_reserve() public {
        // No reserve set — circuit breaker should not fire.
        address[] memory nodes = new address[](1);
        uint256[] memory scores = new uint256[](1);
        nodes[0] = bob;
        scores[0] = 5000;

        vm.prank(oracleAddr);
        ledger.updateImpactScores(nodes, scores);

        // Delegation should succeed even with totalEscrow > 0 (no reserve set).
        vm.prank(alice);
        ledger.delegate(bob);
        assertEq(ledger.delegation(alice), bob);
    }

    // ── Voting Weight ───────────────────────────────────────────────────────

    function test_getVotingWeight_accurate() public {
        // Set Bob and Charlie above threshold.
        address[] memory nodes = new address[](2);
        uint256[] memory scores = new uint256[](2);
        nodes[0] = bob;     scores[0] = 5000;
        nodes[1] = charlie; scores[1] = 6000;

        vm.prank(oracleAddr);
        ledger.updateImpactScores(nodes, scores);

        // Alice and Charlie both delegate to Bob.
        vm.prank(alice);
        ledger.delegate(bob);
        vm.prank(charlie);
        ledger.delegate(bob);

        // Bob: 1 (self) + 2 (delegations) = 3
        assertEq(ledger.getVotingWeight(bob), 3);
        // Alice: 1 (self) + 0 (no delegations) = 1
        assertEq(ledger.getVotingWeight(alice), 1);
    }

    function test_getVotingWeight_unregistered_is_zero() public {
        assertEq(ledger.getVotingWeight(outsider), 0);
    }

    // ── Re-delegation ───────────────────────────────────────────────────────

    function test_redelegate_to_different_steward() public {
        // Set Bob and Charlie above threshold.
        address[] memory nodes = new address[](2);
        uint256[] memory scores = new uint256[](2);
        nodes[0] = bob;     scores[0] = 5000;
        nodes[1] = charlie; scores[1] = 6000;

        vm.prank(oracleAddr);
        ledger.updateImpactScores(nodes, scores);

        // Alice delegates to Bob.
        vm.prank(alice);
        ledger.delegate(bob);
        assertEq(ledger.receivedDelegations(bob), 1);

        // Alice re-delegates to Charlie (auto-revokes Bob).
        vm.prank(alice);
        ledger.delegate(charlie);
        assertEq(ledger.receivedDelegations(bob), 0);
        assertEq(ledger.receivedDelegations(charlie), 1);
        assertEq(ledger.delegation(alice), charlie);
    }

    // ── Oracle Admin ────────────────────────────────────────────────────────

    function test_setThreshold() public {
        vm.prank(oracleAddr);
        ledger.setThreshold(5000);
        assertEq(ledger.stewardThresholdBps(), 5000);
    }

    // ── Oracle Timelock ──────────────────────────────────────────────────────

    function test_proposeOracle_sets_pending() public {
        address newOracle = makeAddr("newOracle");

        vm.prank(oracleAddr);
        ledger.proposeOracle(newOracle);

        assertEq(ledger.pendingOracle(), newOracle);
        assertEq(ledger.pendingOracleActivation(), block.timestamp + 48 hours);
    }

    function test_acceptOracle_before_timelock_reverts() public {
        address newOracle = makeAddr("newOracle");

        vm.prank(oracleAddr);
        ledger.proposeOracle(newOracle);

        // Try to accept immediately — should revert with TimelockActive.
        vm.prank(newOracle);
        vm.expectRevert(
            abi.encodeWithSelector(
                StewardshipLedger.TimelockActive.selector,
                block.timestamp + 48 hours
            )
        );
        ledger.acceptOracle();
    }

    function test_acceptOracle_wrong_sender_reverts() public {
        address newOracle = makeAddr("newOracle");

        vm.prank(oracleAddr);
        ledger.proposeOracle(newOracle);

        // Warp past timelock, but wrong sender tries to accept.
        vm.warp(block.timestamp + 48 hours);
        vm.prank(alice);
        vm.expectRevert(StewardshipLedger.NotPendingOracle.selector);
        ledger.acceptOracle();
    }

    function test_proposeOracle_then_accept_after_timelock() public {
        address newOracle = makeAddr("newOracle");

        vm.prank(oracleAddr);
        ledger.proposeOracle(newOracle);

        // Warp past the 48-hour timelock.
        vm.warp(block.timestamp + 48 hours);

        vm.prank(newOracle);
        ledger.acceptOracle();

        assertEq(ledger.oracle(), newOracle);
        assertEq(ledger.pendingOracle(), address(0));
        assertEq(ledger.pendingOracleActivation(), 0);
    }

    // ── Emergency Circuit Breaker ────────────────────────────────────────────

    function test_emergencyCircuitBreaker_trips() public {
        // Set Bob eligible so we can test delegation blocking.
        address[] memory nodes = new address[](1);
        uint256[] memory scores = new uint256[](1);
        nodes[0] = bob;
        scores[0] = 5000;

        vm.startPrank(oracleAddr);
        ledger.updateImpactScores(nodes, scores);
        // Set a non-zero reserve so circuit breaker logic is active.
        ledger.updateFiatReserve(1000);
        // Trip the emergency circuit breaker.
        ledger.triggerEmergencyCircuitBreaker();
        vm.stopPrank();

        // totalEscrowValue should be max uint256.
        assertEq(ledger.totalEscrowValue(), type(uint256).max);

        // Delegation should be blocked.
        vm.prank(alice);
        vm.expectRevert();
        ledger.delegate(bob);
    }

    function test_resetEmergencyCircuitBreaker() public {
        // Set Bob eligible.
        address[] memory nodes = new address[](1);
        uint256[] memory scores = new uint256[](1);
        nodes[0] = bob;
        scores[0] = 5000;

        vm.startPrank(oracleAddr);
        ledger.updateImpactScores(nodes, scores);
        ledger.updateFiatReserve(1000);
        // Trip the emergency circuit breaker.
        ledger.triggerEmergencyCircuitBreaker();
        // Reset with a value within solvency limits (500 <= 1000 at 1:1).
        ledger.resetEmergencyCircuitBreaker(500);
        vm.stopPrank();

        // totalEscrowValue should be reset.
        assertEq(ledger.totalEscrowValue(), 500);

        // Delegation should now succeed.
        vm.prank(alice);
        ledger.delegate(bob);
        assertEq(ledger.delegation(alice), bob);
    }
}
