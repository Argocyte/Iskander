// SPDX-License-Identifier: AGPL-3.0-only
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {ArbitrationRegistry} from "../src/ArbitrationRegistry.sol";
import {IskanderEscrow} from "../src/IskanderEscrow.sol";
import {CoopIdentity} from "../src/CoopIdentity.sol";
import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";

contract MockToken2 is ERC20 {
    constructor() ERC20("MockToken2", "MT2") { _mint(msg.sender, 1_000_000 ether); }
}

contract ArbitrationRegistryTest is Test {
    CoopIdentity         identity;
    IskanderEscrow       escrow;
    ArbitrationRegistry  registry;
    MockToken2           token;

    address steward  = address(0x1);
    address buyer    = address(0x2);
    address seller   = address(0x3);
    address operator = address(0x4);

    function setUp() public {
        identity = new CoopIdentity("Test Coop", "QmCID", steward);
        escrow   = new IskanderEscrow(address(identity), address(0)); // arbReg set after
        registry = new ArbitrationRegistry(address(identity), address(escrow), operator);
        escrow.setArbitrationRegistry(address(registry));

        token = new MockToken2();
        token.transfer(buyer, 5_000 ether);
        vm.prank(buyer);
        token.approve(address(escrow), type(uint256).max);
    }

    function _createDisputed() internal returns (uint256 escrowId) {
        vm.prank(buyer);
        escrowId = escrow.createEscrow(seller, address(token), 1_000 ether, "QmTerms", 0);
        vm.prank(buyer);
        escrow.dispute(escrowId, "Non-delivery");
    }

    // ── Open Case ─────────────────────────────────────────────────────────────

    function test_openCase() public {
        uint256 eid = _createDisputed();
        vm.prank(operator);
        uint256 cid = registry.openCase(eid, "QmJuryRecord");
        assertEq(registry.escrowToCase(eid), cid);
    }

    // ── Record Verdict ────────────────────────────────────────────────────────

    function test_recordVerdictBuyerFavored() public {
        uint256 eid = _createDisputed();
        vm.prank(operator);
        uint256 cid = registry.openCase(eid, "QmJury");

        vm.prank(operator);
        registry.recordVerdict(
            cid,
            ArbitrationRegistry.VerdictOutcome.BuyerFavored,
            1_000 ether,   // Full refund to buyer
            0,
            0,             // No buyer slash
            50             // Seller trust slash
        );

        ArbitrationRegistry.ArbitrationCase memory c = registry.getCase(cid);
        assertTrue(c.executed);
        assertEq(uint(c.outcome), uint(ArbitrationRegistry.VerdictOutcome.BuyerFavored));
        assertEq(token.balanceOf(buyer), 5_000 ether);  // Fully refunded
    }

    // ── Revert: duplicate case ────────────────────────────────────────────────

    function test_revert_duplicateCase() public {
        uint256 eid = _createDisputed();
        vm.prank(operator);
        registry.openCase(eid, "QmJury");

        vm.expectRevert(abi.encodeWithSelector(
            ArbitrationRegistry.CaseAlreadyExists.selector, eid
        ));
        vm.prank(operator);
        registry.openCase(eid, "QmJury2");
    }
}
