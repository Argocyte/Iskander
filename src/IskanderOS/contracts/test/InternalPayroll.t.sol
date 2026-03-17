// SPDX-License-Identifier: AGPL-3.0-only
pragma solidity ^0.8.24;

import {Test, console2}  from "forge-std/Test.sol";
import {CoopIdentity}    from "../src/CoopIdentity.sol";
import {InternalPayroll} from "../src/InternalPayroll.sol";
import {ERC20}           from "@openzeppelin/contracts/token/ERC20/ERC20.sol";

/// @dev Minimal ERC-20 for testing
contract MockToken is ERC20 {
    constructor() ERC20("Mock USDC", "mUSDC") {
        _mint(msg.sender, 1_000_000 * 1e6);
    }
    function decimals() public pure override returns (uint8) { return 6; }
}

contract InternalPayrollTest is Test {
    CoopIdentity    internal identity;
    InternalPayroll internal payroll;
    MockToken       internal token;

    address internal steward = makeAddr("steward");
    address internal alice   = makeAddr("alice");   // lowest paid
    address internal bob     = makeAddr("bob");     // highest paid
    address internal carol   = makeAddr("carol");   // non-member

    string  internal constant CID = "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi";

    // Annualised base pay in mUSDC (6 decimals)
    uint256 internal constant ALICE_BASE = 30_000 * 1e6;  // $30k
    uint256 internal constant BOB_BASE   = 60_000 * 1e6;  // $60k

    function setUp() public {
        token    = new MockToken();
        identity = new CoopIdentity("Test Co-op", CID, steward);
        payroll  = new InternalPayroll(address(identity), steward, 600); // 6:1

        // Grant membership
        vm.startPrank(steward);
        identity.attest(alice, "did:key:alice", "worker-owner", "ipfs://alice");
        identity.attest(bob,   "did:key:bob",   "steward",      "ipfs://bob");
        payroll.registerMember(alice, ALICE_BASE);
        payroll.registerMember(bob,   BOB_BASE);
        vm.stopPrank();

        // Fund steward with tokens for pay()
        token.transfer(steward, 500_000 * 1e6);
        vm.prank(steward);
        token.approve(address(payroll), type(uint256).max);
    }

    // ── Pay ceiling ───────────────────────────────────────────────────────────
    function test_PayCeiling() public view {
        // lowest = alice $30k, ratio 6:1, ceiling = $180k
        uint256 ceiling = payroll.currentPayCeiling();
        assertEq(ceiling, 180_000 * 1e6);
    }

    // ── Valid payment ─────────────────────────────────────────────────────────
    function test_ValidPayment() public {
        vm.prank(steward);
        payroll.pay(alice, address(token), ALICE_BASE);
        assertEq(token.balanceOf(alice), ALICE_BASE);
    }

    // ── Pay ratio violation ───────────────────────────────────────────────────
    function test_PayRatioExceeded() public {
        uint256 overCeiling = 181_000 * 1e6; // $181k > $180k ceiling
        vm.prank(steward);
        vm.expectRevert(
            abi.encodeWithSelector(
                InternalPayroll.PayRatioExceeded.selector,
                overCeiling,
                180_000 * 1e6
            )
        );
        payroll.pay(bob, address(token), overCeiling);
    }

    // ── Non-member cannot be paid ─────────────────────────────────────────────
    function test_NonMemberReverts() public {
        vm.prank(steward);
        vm.expectRevert(
            abi.encodeWithSelector(InternalPayroll.NotAMember.selector, carol)
        );
        payroll.pay(carol, address(token), 1e6);
    }

    // ── Ratio update ──────────────────────────────────────────────────────────
    function test_UpdateMaxRatio() public {
        vm.prank(steward);
        payroll.updateMaxRatio(300); // 3:1
        assertEq(payroll.currentPayCeiling(), 90_000 * 1e6); // $30k × 3
    }

    function test_RatioBelowOneReverts() public {
        vm.prank(steward);
        vm.expectRevert(InternalPayroll.InvalidRatio.selector);
        payroll.updateMaxRatio(99);
    }
}
