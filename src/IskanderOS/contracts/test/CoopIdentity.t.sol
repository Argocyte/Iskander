// SPDX-License-Identifier: AGPL-3.0-only
pragma solidity ^0.8.24;

import {Test, console2} from "forge-std/Test.sol";
import {CoopIdentity}   from "../src/CoopIdentity.sol";

contract CoopIdentityTest is Test {
    CoopIdentity internal identity;

    address internal steward = makeAddr("steward");
    address internal alice   = makeAddr("alice");
    address internal bob     = makeAddr("bob");

    string  internal constant CID  = "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi";
    string  internal constant DID  = "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK";
    string  internal constant URI  = "ipfs://bafybeifoo";

    function setUp() public {
        identity = new CoopIdentity("Test Co-op", CID, steward);
    }

    // ── Positive cases ────────────────────────────────────────────────────────
    function test_AttestMembership() public {
        vm.prank(steward);
        uint256 tokenId = identity.attest(alice, DID, "worker-owner", URI);
        assertEq(identity.balanceOf(alice), 1);
        assertEq(identity.ownerOf(tokenId), alice);
        assertEq(identity.memberToken(alice), tokenId);
    }

    function test_RevokeMembership() public {
        vm.startPrank(steward);
        uint256 tokenId = identity.attest(alice, DID, "worker-owner", URI);
        identity.revoke(alice);
        vm.stopPrank();

        assertEq(identity.balanceOf(alice), 0);
        assertEq(identity.memberToken(alice), 0);

        (, , , bool active) = identity.memberRecords(tokenId);
        assertFalse(active);
    }

    function test_LegalWrapperCID() public view {
        assertEq(identity.legalWrapperCID(), CID);
        assertEq(identity.legalWrapperURI(), string(abi.encodePacked("ipfs://", CID)));
    }

    // ── ERC-4973: Transfer / Approval must revert ─────────────────────────────
    function test_TransferReverts() public {
        vm.prank(steward);
        uint256 tokenId = identity.attest(alice, DID, "worker-owner", URI);

        vm.prank(alice);
        vm.expectRevert(CoopIdentity.TransferProhibited.selector);
        identity.transferFrom(alice, bob, tokenId);
    }

    function test_ApproveReverts() public {
        vm.prank(steward);
        uint256 tokenId = identity.attest(alice, DID, "worker-owner", URI);

        vm.prank(alice);
        vm.expectRevert(CoopIdentity.ApprovalProhibited.selector);
        identity.approve(bob, tokenId);
    }

    // ── Access control ────────────────────────────────────────────────────────
    function test_NonStewardCannotAttest() public {
        vm.prank(alice);
        vm.expectRevert(CoopIdentity.NotSteward.selector);
        identity.attest(bob, DID, "worker-owner", URI);
    }

    function test_DoubleAttestReverts() public {
        vm.startPrank(steward);
        identity.attest(alice, DID, "worker-owner", URI);
        vm.expectRevert(abi.encodeWithSelector(CoopIdentity.AlreadyMember.selector, alice));
        identity.attest(alice, DID, "worker-owner", URI);
        vm.stopPrank();
    }

    function test_SetConstitution() public {
        address constitutionAddr = makeAddr("constitution");
        vm.prank(steward);
        identity.setConstitution(constitutionAddr);
        assertEq(identity.constitution(), constitutionAddr);
    }

    function test_SetConstitutionTwiceReverts() public {
        address addr1 = makeAddr("constitution1");
        address addr2 = makeAddr("constitution2");
        vm.prank(steward);
        identity.setConstitution(addr1);
        vm.prank(steward);
        vm.expectRevert("CoopIdentity: constitution already set");
        identity.setConstitution(addr2);
    }

    function test_NonStewardCannotSetConstitution() public {
        vm.prank(alice);
        vm.expectRevert(CoopIdentity.NotSteward.selector);
        identity.setConstitution(makeAddr("constitution"));
    }

    function test_SetConstitutionZeroAddressReverts() public {
        vm.prank(steward);
        vm.expectRevert("CoopIdentity: zero address");
        identity.setConstitution(address(0));
    }
}
