// SPDX-License-Identifier: AGPL-3.0-only
pragma solidity ^0.8.24;

/// @title Constitution — Immutable on-chain genesis anchor
contract Constitution {
    bytes32 public immutable genesisCIDHash;
    bytes32 public immutable constitutionCIDHash;
    uint256 public immutable ratifiedAt;
    uint16  public immutable founderCount;
    address public immutable coopIdentity;

    event GenesisRatified(string genesisCID, string constitutionCID, uint16 founderCount);

    constructor(
        string memory _genesisCID,
        string memory _constitutionCID,
        uint16 _founderCount,
        address _coopIdentity
    ) {
        genesisCIDHash = keccak256(bytes(_genesisCID));
        constitutionCIDHash = keccak256(bytes(_constitutionCID));
        ratifiedAt = block.timestamp;
        founderCount = _founderCount;
        coopIdentity = _coopIdentity;
        emit GenesisRatified(_genesisCID, _constitutionCID, _founderCount);
    }
}
