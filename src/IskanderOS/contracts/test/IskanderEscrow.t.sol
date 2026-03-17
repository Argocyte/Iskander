// SPDX-License-Identifier: AGPL-3.0-only
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {IskanderEscrow} from "../src/IskanderEscrow.sol";
import {CoopIdentity} from "../src/CoopIdentity.sol";
import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";

/// @dev Minimal ERC-20 for testing.
contract MockToken is ERC20 {
    constructor() ERC20("MockToken", "MTK") {
        _mint(msg.sender, 1_000_000 ether);
    }
}

contract IskanderEscrowTest is Test {
    CoopIdentity  identity;
    IskanderEscrow escrow;
    MockToken     token;

    address steward  = address(0x1);
    address buyer    = address(0x2);
    address seller   = address(0x3);
    address arbReg   = address(0x9);

    function setUp() public {
        identity = new CoopIdentity("Test Coop", "QmTestCID", steward);
        escrow   = new IskanderEscrow(address(identity), arbReg);
        token    = new MockToken();

        token.transfer(buyer, 10_000 ether);
        vm.prank(buyer);
        token.approve(address(escrow), type(uint256).max);
    }

    // ── Happy Path ────────────────────────────────────────────────────────────

    function test_createAndConfirm() public {
        vm.prank(buyer);
        uint256 id = escrow.createEscrow(seller, address(token), 1_000 ether, "QmTerms", 0);
        assertEq(uint(escrow.escrows(id).status), uint(IskanderEscrow.EscrowStatus.Active));

        vm.prank(buyer);
        escrow.confirmDelivery(id);
        assertEq(uint(escrow.escrows(id).status), uint(IskanderEscrow.EscrowStatus.Released));
        assertEq(token.balanceOf(seller), 1_000 ether);
    }

    // ── Dispute Path ──────────────────────────────────────────────────────────

    function test_dispute() public {
        vm.prank(buyer);
        uint256 id = escrow.createEscrow(seller, address(token), 500 ether, "QmTerms", 0);

        vm.prank(seller);
        escrow.dispute(id, "Goods not as described");
        assertEq(uint(escrow.escrows(id).status), uint(IskanderEscrow.EscrowStatus.Disputed));
    }

    function test_executeVerdictSplit() public {
        vm.prank(buyer);
        uint256 id = escrow.createEscrow(seller, address(token), 600 ether, "QmTerms", 0);

        vm.prank(buyer);
        escrow.dispute(id, "Partial delivery");

        vm.prank(arbReg);
        escrow.executeVerdict(id, 200 ether, 400 ether);
        assertEq(token.balanceOf(buyer),  9_600 ether + 200 ether);  // 10k - 600 + 200
        assertEq(token.balanceOf(seller), 400 ether);
        assertEq(uint(escrow.escrows(id).status), uint(IskanderEscrow.EscrowStatus.Arbitrated));
    }

    // ── Expiry ────────────────────────────────────────────────────────────────

    function test_claimExpiry() public {
        uint256 deadline = block.timestamp + 100;
        vm.prank(buyer);
        uint256 id = escrow.createEscrow(seller, address(token), 200 ether, "QmTerms", deadline);

        vm.warp(deadline + 1);
        vm.prank(buyer);
        escrow.claimExpiry(id);
        assertEq(uint(escrow.escrows(id).status), uint(IskanderEscrow.EscrowStatus.Expired));
        assertEq(token.balanceOf(buyer), 10_000 ether);  // Fully refunded.
    }

    // ── Revert Cases ──────────────────────────────────────────────────────────

    function test_revert_confirmByNonBuyer() public {
        vm.prank(buyer);
        uint256 id = escrow.createEscrow(seller, address(token), 100 ether, "QmTerms", 0);

        vm.expectRevert(abi.encodeWithSelector(IskanderEscrow.NotParty.selector, seller));
        vm.prank(seller);
        escrow.confirmDelivery(id);
    }

    function test_revert_invalidSplit() public {
        vm.prank(buyer);
        uint256 id = escrow.createEscrow(seller, address(token), 100 ether, "QmTerms", 0);
        vm.prank(buyer);
        escrow.dispute(id, "Test");

        vm.expectRevert(IskanderEscrow.InvalidSplit.selector);
        vm.prank(arbReg);
        escrow.executeVerdict(id, 50 ether, 60 ether);  // 110 != 100
    }
}
