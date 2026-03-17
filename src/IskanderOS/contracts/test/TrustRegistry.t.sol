// SPDX-License-Identifier: AGPL-3.0-only
pragma solidity ^0.8.24;

import {Test, console2} from "forge-std/Test.sol";
import {CoopIdentity}   from "../src/CoopIdentity.sol";
import {TrustRegistry}  from "../src/governance/TrustRegistry.sol";

contract TrustRegistryTest is Test {
    CoopIdentity  internal identity;
    TrustRegistry internal registry;

    address internal steward  = makeAddr("steward");
    address internal alice    = makeAddr("alice");
    address internal bob      = makeAddr("bob");
    address internal outsider = makeAddr("outsider");

    string  internal constant CID = "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi";
    string  internal constant DID = "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK";
    string  internal constant URI = "ipfs://bafybeifoo";

    bytes32 internal uniKey = keccak256(abi.encodePacked("university-of-mondragon-ed25519-pub"));
    bytes32 internal fedKey = keccak256(abi.encodePacked("disco-federation-es256-pub"));

    function setUp() public {
        // Deploy CoopIdentity (no BrightID in test).
        identity = new CoopIdentity("Test Co-op", CID, steward, address(0), bytes32(0));

        // Deploy TrustRegistry.
        registry = new TrustRegistry(address(identity));

        // Register members via CoopIdentity.
        vm.startPrank(steward);
        identity.attest(alice, DID, "steward", URI);
        identity.attest(bob,   DID, "worker-owner", URI);
        vm.stopPrank();
    }

    // ── Registration ────────────────────────────────────────────────────────

    function test_registerIssuer() public {
        vm.prank(alice);
        registry.registerIssuer(
            uniKey,
            "did:web:university.mondragon.edu",
            "University of Mondragon",
            "Ed25519"
        );

        assertTrue(registry.isIssuerTrusted(uniKey));
        assertEq(registry.activeCount(), 1);
        assertEq(registry.issuerCount(), 1);
    }

    function test_registerIssuer_multiple() public {
        vm.startPrank(alice);
        registry.registerIssuer(uniKey, "did:web:uni.edu", "University", "Ed25519");
        registry.registerIssuer(fedKey, "did:web:disco.coop", "DisCO Federation", "ES256");
        vm.stopPrank();

        assertTrue(registry.isIssuerTrusted(uniKey));
        assertTrue(registry.isIssuerTrusted(fedKey));
        assertEq(registry.activeCount(), 2);
        assertEq(registry.issuerCount(), 2);
    }

    function test_registerIssuer_only_member() public {
        vm.prank(outsider);
        vm.expectRevert(abi.encodeWithSelector(TrustRegistry.NotMember.selector, outsider));
        registry.registerIssuer(uniKey, "did:web:uni.edu", "University", "Ed25519");
    }

    function test_registerIssuer_duplicate_reverts() public {
        vm.startPrank(alice);
        registry.registerIssuer(uniKey, "did:web:uni.edu", "University", "Ed25519");

        vm.expectRevert(abi.encodeWithSelector(TrustRegistry.IssuerAlreadyRegistered.selector, uniKey));
        registry.registerIssuer(uniKey, "did:web:uni.edu", "University", "Ed25519");
        vm.stopPrank();
    }

    function test_registerIssuer_zero_fingerprint_reverts() public {
        vm.prank(alice);
        vm.expectRevert(TrustRegistry.ZeroFingerprint.selector);
        registry.registerIssuer(bytes32(0), "did:web:uni.edu", "University", "Ed25519");
    }

    function test_registerIssuer_empty_did_reverts() public {
        vm.prank(alice);
        vm.expectRevert(TrustRegistry.EmptyDid.selector);
        registry.registerIssuer(uniKey, "", "University", "Ed25519");
    }

    // ── Revocation ──────────────────────────────────────────────────────────

    function test_revokeIssuer() public {
        vm.prank(alice);
        registry.registerIssuer(uniKey, "did:web:uni.edu", "University", "Ed25519");

        assertTrue(registry.isIssuerTrusted(uniKey));

        vm.prank(bob);
        registry.revokeIssuer(uniKey, CID);

        assertFalse(registry.isIssuerTrusted(uniKey));
        assertEq(registry.activeCount(), 0);
        // Total count still includes revoked
        assertEq(registry.issuerCount(), 1);
    }

    function test_revokeIssuer_emits_event() public {
        vm.prank(alice);
        registry.registerIssuer(uniKey, "did:web:uni.edu", "University", "Ed25519");

        vm.prank(bob);
        vm.expectEmit(true, true, false, true);
        emit TrustRegistry.IssuerRevoked(uniKey, "did:web:uni.edu", bob, CID);
        registry.revokeIssuer(uniKey, CID);
    }

    function test_revokeIssuer_not_found_reverts() public {
        vm.prank(alice);
        vm.expectRevert(abi.encodeWithSelector(TrustRegistry.IssuerNotFound.selector, uniKey));
        registry.revokeIssuer(uniKey, CID);
    }

    function test_revokeIssuer_already_revoked_reverts() public {
        vm.prank(alice);
        registry.registerIssuer(uniKey, "did:web:uni.edu", "University", "Ed25519");

        vm.prank(alice);
        registry.revokeIssuer(uniKey, CID);

        vm.prank(bob);
        vm.expectRevert(abi.encodeWithSelector(TrustRegistry.IssuerAlreadyRevoked.selector, uniKey));
        registry.revokeIssuer(uniKey, CID);
    }

    function test_revokeIssuer_empty_rationale_reverts() public {
        vm.prank(alice);
        registry.registerIssuer(uniKey, "did:web:uni.edu", "University", "Ed25519");

        vm.prank(bob);
        vm.expectRevert(TrustRegistry.EmptyRationale.selector);
        registry.revokeIssuer(uniKey, "");
    }

    // ── Re-registration After Revocation ────────────────────────────────────

    function test_reregister_after_revoke() public {
        vm.prank(alice);
        registry.registerIssuer(uniKey, "did:web:uni.edu", "University", "Ed25519");

        vm.prank(alice);
        registry.revokeIssuer(uniKey, CID);
        assertFalse(registry.isIssuerTrusted(uniKey));

        // Re-register with updated info
        vm.prank(bob);
        registry.registerIssuer(uniKey, "did:web:uni-v2.edu", "University v2", "Ed25519");
        assertTrue(registry.isIssuerTrusted(uniKey));
        assertEq(registry.activeCount(), 1);
        // Total count should NOT increase (same fingerprint)
        assertEq(registry.issuerCount(), 1);
    }

    // ── Query Functions ─────────────────────────────────────────────────────

    function test_getIssuer() public {
        vm.prank(alice);
        registry.registerIssuer(uniKey, "did:web:uni.edu", "University", "Ed25519");

        (
            string memory issuerDid,
            string memory issuerName,
            string memory keyType,
            uint256 registeredAt,
            bool active
        ) = registry.getIssuer(uniKey);

        assertEq(issuerDid, "did:web:uni.edu");
        assertEq(issuerName, "University");
        assertEq(keyType, "Ed25519");
        assertGt(registeredAt, 0);
        assertTrue(active);
    }

    function test_getActiveIssuers() public {
        vm.startPrank(alice);
        registry.registerIssuer(uniKey, "did:web:uni.edu", "University", "Ed25519");
        registry.registerIssuer(fedKey, "did:web:disco.coop", "DisCO", "ES256");
        vm.stopPrank();

        bytes32[] memory active = registry.getActiveIssuers();
        assertEq(active.length, 2);

        // Revoke one
        vm.prank(bob);
        registry.revokeIssuer(uniKey, CID);

        active = registry.getActiveIssuers();
        assertEq(active.length, 1);
        assertEq(active[0], fedKey);
    }

    function test_untrusted_key_returns_false() public view {
        assertFalse(registry.isIssuerTrusted(uniKey));
    }
}
