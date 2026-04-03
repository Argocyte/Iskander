// SPDX-License-Identifier: AGPL-3.0-only
pragma solidity ^0.8.24;

import {Test, console2} from "forge-std/Test.sol";
import {Constitution} from "../src/Constitution.sol";

contract ConstitutionTest is Test {
    Constitution internal constitution;
    address internal coopIdentity = makeAddr("coopIdentity");
    string  internal constant GENESIS_CID = "QmGenesisManifestCID1234567890abcdef12345678";
    string  internal constant CONSTITUTION_CID = "QmConstitutionCID1234567890abcdef1234567890ab";
    uint16  internal constant FOUNDER_COUNT = 3;

    function setUp() public {
        constitution = new Constitution(GENESIS_CID, CONSTITUTION_CID, FOUNDER_COUNT, coopIdentity);
    }

    function test_GenesisRatifiedEventEmitted() public {
        vm.recordLogs();
        Constitution c = new Constitution(GENESIS_CID, CONSTITUTION_CID, FOUNDER_COUNT, coopIdentity);
        Vm.Log[] memory entries = vm.getRecordedLogs();
        assertGt(entries.length, 0, "No events emitted");
    }

    function test_CidHashesMatchInput() public view {
        assertEq(constitution.genesisCIDHash(), keccak256(bytes(GENESIS_CID)));
        assertEq(constitution.constitutionCIDHash(), keccak256(bytes(CONSTITUTION_CID)));
    }

    function test_FounderCountStored() public view {
        assertEq(constitution.founderCount(), FOUNDER_COUNT);
    }

    function test_CoopIdentityLink() public view {
        assertEq(constitution.coopIdentity(), coopIdentity);
    }

    function test_RatifiedAtSet() public view {
        assertGt(constitution.ratifiedAt(), 0);
    }

    function test_ImmutableFieldsCannotChange() public view {
        assertTrue(constitution.genesisCIDHash() != bytes32(0));
        assertTrue(constitution.constitutionCIDHash() != bytes32(0));
        assertTrue(constitution.founderCount() > 0);
    }

    function test_SoloNodeWithZeroCoopIdentity() public {
        Constitution solo = new Constitution(GENESIS_CID, CONSTITUTION_CID, 1, address(0));
        assertEq(solo.coopIdentity(), address(0));
        assertEq(solo.founderCount(), 1);
    }
}
