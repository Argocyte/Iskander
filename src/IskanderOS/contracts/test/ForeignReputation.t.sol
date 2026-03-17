// SPDX-License-Identifier: AGPL-3.0-only
pragma solidity ^0.8.24;

import {Test, console2} from "forge-std/Test.sol";
import {CoopIdentity}       from "../src/CoopIdentity.sol";
import {ForeignReputation}   from "../src/governance/ForeignReputation.sol";

contract ForeignReputationTest is Test {
    CoopIdentity     internal identity;
    ForeignReputation internal frs;

    address internal steward   = makeAddr("steward");
    address internal oracleAddr = makeAddr("oracle");
    address internal alice     = makeAddr("alice");
    address internal outsider  = makeAddr("outsider");

    string  internal constant CID = "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi";
    string  internal constant DID = "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK";
    string  internal constant URI = "ipfs://bafybeifoo";

    // Tier thresholds (basis points)
    uint256 internal constant QUARANTINE_BPS  = 1000; // 10%
    uint256 internal constant PROVISIONAL_BPS = 3000; // 30%
    uint256 internal constant TRUSTED_BPS     = 7000; // 70%

    bytes32 internal sdcA = keccak256(abi.encodePacked("did:web:coop-a.example"));
    bytes32 internal sdcB = keccak256(abi.encodePacked("did:web:coop-b.example"));

    function setUp() public {
        // Deploy CoopIdentity (no BrightID in test).
        identity = new CoopIdentity("Test Co-op", CID, steward, address(0), bytes32(0));

        // Deploy ForeignReputation.
        frs = new ForeignReputation(
            address(identity),
            oracleAddr,
            QUARANTINE_BPS,
            PROVISIONAL_BPS,
            TRUSTED_BPS
        );

        // Register member via CoopIdentity.
        vm.startPrank(steward);
        identity.attest(alice, DID, "steward", URI);
        vm.stopPrank();
    }

    // ── Registration ────────────────────────────────────────────────────────

    function test_registerSDC() public {
        vm.prank(oracleAddr);
        frs.registerSDC(sdcA, 5000);

        (uint256 raw, uint256 lastUpdated, bool quarantined) = frs.getSDCProfile(sdcA);
        assertEq(raw, 5000);
        assertGt(lastUpdated, 0);
        assertFalse(quarantined);
    }

    function test_registerSDC_duplicate_reverts() public {
        vm.startPrank(oracleAddr);
        frs.registerSDC(sdcA, 5000);
        vm.expectRevert(abi.encodeWithSelector(ForeignReputation.SDCAlreadyRegistered.selector, sdcA));
        frs.registerSDC(sdcA, 3000);
        vm.stopPrank();
    }

    function test_registerSDC_score_exceeds_max_reverts() public {
        vm.prank(oracleAddr);
        vm.expectRevert(abi.encodeWithSelector(ForeignReputation.ScoreExceedsMax.selector, 10001));
        frs.registerSDC(sdcA, 10001);
    }

    function test_registerSDC_only_oracle() public {
        vm.prank(alice);
        vm.expectRevert(ForeignReputation.NotOracle.selector);
        frs.registerSDC(sdcA, 5000);
    }

    // ── Score Updates ───────────────────────────────────────────────────────

    function test_recordTransaction_positive() public {
        vm.startPrank(oracleAddr);
        frs.registerSDC(sdcA, 5000);
        frs.recordTransaction(sdcA, 300, "bafyTxCid1");
        vm.stopPrank();

        assertEq(frs.getCurrentScore(sdcA), 5300);
    }

    function test_recordTransaction_negative() public {
        vm.startPrank(oracleAddr);
        frs.registerSDC(sdcA, 5000);
        frs.recordTransaction(sdcA, -200, "bafyTxCid2");
        vm.stopPrank();

        assertEq(frs.getCurrentScore(sdcA), 4800);
    }

    function test_recordTransaction_clamps_to_zero() public {
        vm.startPrank(oracleAddr);
        frs.registerSDC(sdcA, 100);
        frs.recordTransaction(sdcA, -500, "bafyTxCid3");
        vm.stopPrank();

        assertEq(frs.getCurrentScore(sdcA), 0);
    }

    function test_recordTransaction_clamps_to_max() public {
        vm.startPrank(oracleAddr);
        frs.registerSDC(sdcA, 9900);
        frs.recordTransaction(sdcA, 500, "bafyTxCid4");
        vm.stopPrank();

        assertEq(frs.getCurrentScore(sdcA), 10000);
    }

    function test_recordTransaction_delta_exceeds_limit_reverts() public {
        vm.startPrank(oracleAddr);
        frs.registerSDC(sdcA, 5000);
        vm.expectRevert(abi.encodeWithSelector(
            ForeignReputation.DeltaExceedsLimit.selector, int256(501), 500
        ));
        frs.recordTransaction(sdcA, 501, "bafyTxCid5");
        vm.stopPrank();
    }

    function test_recordTransaction_unregistered_reverts() public {
        vm.prank(oracleAddr);
        vm.expectRevert(abi.encodeWithSelector(ForeignReputation.SDCNotRegistered.selector, sdcA));
        frs.recordTransaction(sdcA, 100, "bafyTxCid6");
    }

    // ── Tier Computation ────────────────────────────────────────────────────

    function test_tier_quarantine() public {
        vm.prank(oracleAddr);
        frs.registerSDC(sdcA, 500); // Below quarantineThreshold (1000)

        assertEq(frs.getCurrentTier(sdcA), 0);
    }

    function test_tier_provisional() public {
        vm.prank(oracleAddr);
        frs.registerSDC(sdcA, 2000); // Between 1000 and 3000

        assertEq(frs.getCurrentTier(sdcA), 1);
    }

    function test_tier_trusted() public {
        vm.prank(oracleAddr);
        frs.registerSDC(sdcA, 5000); // Between 3000 and 7000

        assertEq(frs.getCurrentTier(sdcA), 2);
    }

    function test_tier_allied() public {
        vm.prank(oracleAddr);
        frs.registerSDC(sdcA, 8000); // At or above 7000

        assertEq(frs.getCurrentTier(sdcA), 3);
    }

    // ── Exponential Decay ───────────────────────────────────────────────────

    function test_decay_after_one_half_life() public {
        vm.prank(oracleAddr);
        frs.registerSDC(sdcA, 10000);

        // Warp forward by one half-life (30 days)
        vm.warp(block.timestamp + 30 days);

        // Score should be approximately 5000 (10000 / 2)
        uint256 score = frs.getCurrentScore(sdcA);
        assertEq(score, 5000);
    }

    function test_decay_after_two_half_lives() public {
        vm.prank(oracleAddr);
        frs.registerSDC(sdcA, 10000);

        vm.warp(block.timestamp + 60 days);

        // Score should be approximately 2500 (10000 / 4)
        uint256 score = frs.getCurrentScore(sdcA);
        assertEq(score, 2500);
    }

    function test_decay_after_thirteen_half_lives_is_zero() public {
        vm.prank(oracleAddr);
        frs.registerSDC(sdcA, 10000);

        vm.warp(block.timestamp + 390 days); // 13 * 30 days

        assertEq(frs.getCurrentScore(sdcA), 0);
    }

    function test_decay_tier_drops_over_time() public {
        vm.prank(oracleAddr);
        frs.registerSDC(sdcA, 8000); // Allied (tier 3)

        assertEq(frs.getCurrentTier(sdcA), 3);

        // After 1 half-life: 4000 → Trusted (tier 2)
        vm.warp(block.timestamp + 30 days);
        assertEq(frs.getCurrentTier(sdcA), 2);

        // After 2 half-lives: 2000 → Provisional (tier 1)
        vm.warp(block.timestamp + 30 days);
        assertEq(frs.getCurrentTier(sdcA), 1);
    }

    function test_transaction_resets_decay() public {
        vm.startPrank(oracleAddr);
        frs.registerSDC(sdcA, 8000);

        // Warp 30 days — score decays to 4000
        vm.warp(block.timestamp + 30 days);
        assertEq(frs.getCurrentScore(sdcA), 4000);

        // Record transaction — adds 500 to decayed score, resets decay timer
        frs.recordTransaction(sdcA, 500, "bafyRefresh");
        assertEq(frs.getCurrentScore(sdcA), 4500);

        // Warp 30 more days — decays from 4500, not from 8000
        vm.warp(block.timestamp + 30 days);
        assertEq(frs.getCurrentScore(sdcA), 2250);

        vm.stopPrank();
    }

    // ── Force Quarantine ────────────────────────────────────────────────────

    function test_forceQuarantine_overrides_tier() public {
        vm.prank(oracleAddr);
        frs.registerSDC(sdcA, 9000); // Allied (tier 3)

        assertEq(frs.getCurrentTier(sdcA), 3);

        // Council member force-quarantines
        vm.prank(alice);
        frs.forceQuarantine(sdcA, CID);

        // Tier locked to 0 despite high score
        assertEq(frs.getCurrentTier(sdcA), 0);
        // Score still readable
        assertEq(frs.getCurrentScore(sdcA), 9000);
    }

    function test_forceQuarantine_only_member() public {
        vm.prank(oracleAddr);
        frs.registerSDC(sdcA, 9000);

        vm.prank(outsider);
        vm.expectRevert(abi.encodeWithSelector(ForeignReputation.NotMember.selector, outsider));
        frs.forceQuarantine(sdcA, CID);
    }

    function test_liftQuarantine_restores_tier() public {
        vm.prank(oracleAddr);
        frs.registerSDC(sdcA, 9000);

        vm.prank(alice);
        frs.forceQuarantine(sdcA, CID);
        assertEq(frs.getCurrentTier(sdcA), 0);

        vm.prank(oracleAddr);
        frs.liftQuarantine(sdcA);
        assertEq(frs.getCurrentTier(sdcA), 3);
    }

    // ── Oracle Timelock ─────────────────────────────────────────────────────

    function test_oracle_timelock() public {
        address newOracle = makeAddr("newOracle");

        vm.prank(oracleAddr);
        frs.proposeOracle(newOracle);

        // Cannot accept before timelock
        vm.prank(newOracle);
        vm.expectRevert();
        frs.acceptOracle();

        // Warp past timelock
        vm.warp(block.timestamp + 48 hours + 1);
        vm.prank(newOracle);
        frs.acceptOracle();

        assertEq(frs.oracle(), newOracle);
    }

    // ── Configuration ───────────────────────────────────────────────────────

    function test_setTierThresholds() public {
        vm.prank(oracleAddr);
        frs.setTierThresholds(500, 2000, 6000);

        assertEq(frs.quarantineThreshold(), 500);
        assertEq(frs.provisionalThreshold(), 2000);
        assertEq(frs.trustedThreshold(), 6000);
    }

    function test_setTierThresholds_invalid_reverts() public {
        vm.prank(oracleAddr);
        vm.expectRevert(ForeignReputation.InvalidThresholds.selector);
        frs.setTierThresholds(5000, 3000, 7000); // quarantine > provisional
    }

    function test_setDecayHalfLife() public {
        vm.prank(oracleAddr);
        frs.setDecayHalfLife(15 days);

        assertEq(frs.decayHalfLife(), 15 days);

        // Verify decay now uses new half-life
        vm.prank(oracleAddr);
        frs.registerSDC(sdcA, 10000);

        vm.warp(block.timestamp + 15 days);
        assertEq(frs.getCurrentScore(sdcA), 5000);
    }

    function test_setDecayHalfLife_zero_reverts() public {
        vm.prank(oracleAddr);
        vm.expectRevert(ForeignReputation.ZeroHalfLife.selector);
        frs.setDecayHalfLife(0);
    }

    // ── Tier Change Events ──────────────────────────────────────────────────

    function test_tier_change_emits_event() public {
        vm.startPrank(oracleAddr);
        frs.registerSDC(sdcA, 2500); // Provisional (tier 1)

        // Push into Trusted (tier 2)
        vm.expectEmit(true, false, false, true);
        emit ForeignReputation.TierChanged(sdcA, 1, 2);
        frs.recordTransaction(sdcA, 500, "bafyUpgrade");

        vm.stopPrank();
    }
}
