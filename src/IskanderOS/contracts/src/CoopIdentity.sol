// SPDX-License-Identifier: AGPL-3.0-only
pragma solidity ^0.8.24;

/**
 * @title  CoopIdentity
 * @notice ERC-4973 Account-Bound Token (ABT) representing cooperative membership.
 *
 * LEGAL NOTICE:
 *   This smart contract is an ON-CHAIN EXTENSION of the cooperative's real-world
 *   legal wrapper (e.g., an LCA, LLC Operating Agreement, or Bylaws) whose IPFS
 *   content identifier (CID) is stored in `legalWrapperCID`. The contract does NOT
 *   replace, supersede, or limit the legal liability of members or stewards under
 *   that legal instrument. In any conflict, the off-chain legal document governs.
 *
 * @dev    ERC-4973 tokens are non-transferable and non-approvable by design.
 *         Minting = granting membership. Burning = revoking membership.
 *         The `legalWrapperCID` binds this contract instance to a specific,
 *         immutable Ricardian constitution stored on IPFS.
 */

import {IERC165} from "@openzeppelin/contracts/utils/introspection/IERC165.sol";
import {ERC165} from "@openzeppelin/contracts/utils/introspection/ERC165.sol";
import {Strings} from "@openzeppelin/contracts/utils/Strings.sol";

// ── Phase 17: BrightID Sybil-Resistant Identity ─────────────────────────────
// Identity is derived 100% from the peer-to-peer social graph via BrightID.
// No Gitcoin Passport. No wallet-balance-based voting weights. No invasive KYC.
// BrightID's Web-of-Trust model ensures 1-Member-1-Vote without requiring
// members to expose government IDs or accumulate on-chain wealth signals.
// This directly implements CCIN Principle 1 (Voluntary & Open Membership)
// and Principle 2 (Democratic Member Control — one member, one vote).

/// @dev BrightID verifier interface (deployed on Gnosis Chain; bridgeable to L2s).
///      See: https://dev.brightid.org/docs/verifications/on-chain
interface IBrightID {
    /// @notice Check if an address is verified as unique within a BrightID app context.
    /// @param appContext  The keccak256 hash of the cooperative's BrightID app name.
    /// @param addrs      Array of addresses linked to the BrightID account.
    /// @return True if the contextId is verified (unique human in this app).
    function isVerifiedUser(
        bytes32 appContext,
        address[] calldata addrs
    ) external view returns (bool);
}

/// @dev ERC-4973 interface — Account-Bound Tokens (EIP-4973)
interface IERC4973 is IERC165 {
    event Attest(address indexed to, uint256 indexed tokenId);
    event Revoke(address indexed to, uint256 indexed tokenId);

    function balanceOf(address owner) external view returns (uint256);
    function ownerOf(uint256 tokenId) external view returns (address);
    function tokenURI(uint256 tokenId) external view returns (string memory);
}

contract CoopIdentity is ERC165, IERC4973 {
    using Strings for uint256;

    // ─── Ricardian Binding ────────────────────────────────────────────────────
    /// @notice IPFS CID of the cooperative's legal wrapper (bylaws / LCA).
    ///         Immutable: changing the legal doc requires deploying a new contract.
    string public legalWrapperCID;

    // ─── Cooperative Metadata ─────────────────────────────────────────────────
    string public coopName;
    address public steward;          // M-of-N Safe multi-sig in production

    // ─── Token State ──────────────────────────────────────────────────────────
    uint256 private _nextTokenId;

    mapping(uint256 => address) private _owners;
    mapping(address => uint256) private _balances;
    mapping(uint256 => string)  private _tokenURIs;

    /// @notice Member metadata stored on-chain for governance lookups
    struct MemberRecord {
        string  did;            // W3C DID (e.g. did:key:z6Mk...)
        string  role;           // e.g. "worker-owner", "steward", "associate"
        uint256 joinedAt;       // block.timestamp of attestation
        bool    active;
        // Phase 15: Inter-coop trust score. Range: [0, 1000]. 1000 = full trust.
        // Reduced by ArbitrationRegistry on bad-faith arbitration findings.
        // Restored by steward after remediation.
        uint16  trustScore;
    }
    mapping(uint256 => MemberRecord) public memberRecords;
    /// @notice Reverse lookup: address → tokenId (0 = not a member)
    mapping(address => uint256) public memberToken;

    // ─── Phase 15: Arbitration Registry ──────────────────────────────────────
    /// @notice The ArbitrationRegistry contract authorised to slash trust scores.
    ///         Set by the steward after ArbitrationRegistry deployment.
    address public arbitrationRegistry;

    // ─── Phase 17: BrightID Sybil Resistance ───────────────────────────────
    /// @notice BrightID verifier contract (on Gnosis Chain or bridged).
    IBrightID public brightIdVerifier;
    /// @notice keccak256 hash of the cooperative's BrightID app context string.
    ///         Each cooperative registers a unique app context with BrightID to
    ///         ensure Sybil resistance is scoped to their membership.
    bytes32 public brightIdAppContext;

    // ─── Events ───────────────────────────────────────────────────────────────
    event MembershipGranted(address indexed member, uint256 tokenId, string did, string role);
    event MembershipRevoked(address indexed member, uint256 tokenId);
    event StewardTransferred(address indexed oldSteward, address indexed newSteward);
    // Phase 15
    event TrustSlashed(address indexed member, uint16 penalty, uint16 newScore, bytes32 caseHash);
    event TrustRestored(address indexed member, uint16 restoration, uint16 newScore, bytes32 caseHash);
    event ArbitrationRegistrySet(address indexed registry);

    // ─── Errors ───────────────────────────────────────────────────────────────
    error NotSteward();
    error AlreadyMember(address account);
    error NotAMember(address account);
    error TransferProhibited();           // ERC-4973: tokens are account-bound
    error ApprovalProhibited();           // ERC-4973: no approvals
    error NotArbitrationRegistry();       // Phase 15: caller is not ArbitrationRegistry
    error TrustScoreUnderflow(uint16 current, uint16 penalty); // penalty > current score
    // Phase 17: BrightID verification failed — applicant is not verified as a
    // unique human in this cooperative's BrightID app context.
    error BrightIDNotVerified(address applicant);

    // ─── Constructor ──────────────────────────────────────────────────────────
    /**
     * @param _coopName          Human-readable cooperative name
     * @param _legalWrapperCID   IPFS CID of the ratified legal wrapper document.
     *                           Retrieve via: ipfs cat <_legalWrapperCID>
     * @param _steward           Address of the initial steward (should be a Safe)
     * @param _brightIdVerifier  Address of the BrightID verifier contract.
     *                           On Gnosis Chain: 0x... (see dev.brightid.org).
     *                           Pass address(0) to disable BrightID checks (dev only).
     * @param _brightIdAppContext keccak256 of the cooperative's BrightID app name
     *                           (e.g., keccak256("iskander-coop-mainnet")).
     */
    constructor(
        string memory _coopName,
        string memory _legalWrapperCID,
        address _steward,
        address _brightIdVerifier,
        bytes32 _brightIdAppContext
    ) {
        require(bytes(_legalWrapperCID).length > 0, "CoopIdentity: legalWrapperCID required");
        require(_steward != address(0), "CoopIdentity: steward cannot be zero address");

        coopName           = _coopName;
        legalWrapperCID    = _legalWrapperCID;
        steward            = _steward;
        _nextTokenId       = 1;

        // Phase 17: BrightID Sybil resistance. Identity derived from peer-to-peer
        // social graph — no Gitcoin Passport, no wallet-balance voting weights,
        // no invasive KYC. The cooperative trusts the Web-of-Trust, not wealth signals.
        brightIdVerifier   = IBrightID(_brightIdVerifier);
        brightIdAppContext = _brightIdAppContext;
    }

    // ─── Modifiers ────────────────────────────────────────────────────────────
    modifier onlySteward() {
        if (msg.sender != steward) revert NotSteward();
        _;
    }

    modifier onlyArbitrationRegistry() {
        if (msg.sender != arbitrationRegistry) revert NotArbitrationRegistry();
        _;
    }

    // ─── Membership Management ───────────────────────────────────────────────
    /**
     * @notice Attest (mint) a membership token to `_to`.
     * @dev    One token per address enforced. Called by the steward Safe after
     *         off-chain ratification of the legal wrapper by the applicant.
     */
    function attest(
        address _to,
        string calldata _did,
        string calldata _role,
        string calldata _tokenURI
    ) external onlySteward returns (uint256 tokenId) {
        if (memberToken[_to] != 0) revert AlreadyMember(_to);

        // ── Phase 17: BrightID Sybil-Resistance Gate ────────────────────────
        // Before minting the ERC-4973 Soulbound Token, verify that the applicant
        // is a unique human in this cooperative's BrightID app context.
        // 1-Member-1-Vote requires 1-Human-1-Account. BrightID's peer-to-peer
        // social graph is the ONLY identity signal — no wealth-gating, no KYC.
        // The cooperative's BrightID sponsor backend (brightid_sponsor.py) ensures
        // the onboarding cost is zero for non-technical workers (bakers, drivers).
        if (address(brightIdVerifier) != address(0)) {
            address[] memory addrs = new address[](1);
            addrs[0] = _to;
            if (!brightIdVerifier.isVerifiedUser(brightIdAppContext, addrs))
                revert BrightIDNotVerified(_to);
        }

        tokenId = _nextTokenId++;
        _owners[tokenId]    = _to;
        _balances[_to]      = 1;
        _tokenURIs[tokenId] = _tokenURI;
        memberToken[_to]    = tokenId;

        memberRecords[tokenId] = MemberRecord({
            did:        _did,
            role:       _role,
            joinedAt:   block.timestamp,
            active:     true,
            trustScore: 1000  // Phase 15: full trust on admission
        });

        emit Attest(_to, tokenId);
        emit MembershipGranted(_to, tokenId, _did, _role);
    }

    /**
     * @notice Revoke (burn) a membership token.
     * @dev    Requires steward multi-sig approval. Revocation must follow the
     *         process defined in the legal wrapper (legalWrapperCID) — this
     *         on-chain action alone does not constitute lawful expulsion.
     */
    function revoke(address _from) external onlySteward {
        uint256 tokenId = memberToken[_from];
        if (tokenId == 0) revert NotAMember(_from);

        memberRecords[tokenId].active = false;
        delete _owners[tokenId];
        delete _balances[_from];
        delete memberToken[_from];

        emit Revoke(_from, tokenId);
        emit MembershipRevoked(_from, tokenId);
    }

    // ─── Phase 15: Trust Score Management ────────────────────────────────────

    /**
     * @notice Set the ArbitrationRegistry contract authorised to call slashTrust.
     * @dev    Called once by the steward after ArbitrationRegistry is deployed.
     *         Changing it requires steward multi-sig approval.
     */
    function setArbitrationRegistry(address _registry) external onlySteward {
        require(_registry != address(0), "CoopIdentity: zero address");
        arbitrationRegistry = _registry;
        emit ArbitrationRegistrySet(_registry);
    }

    address public constitution;

    event ConstitutionSet(address indexed constitution);

    function setConstitution(address _constitution) external onlySteward {
        require(_constitution != address(0), "CoopIdentity: zero address");
        require(constitution == address(0), "CoopIdentity: constitution already set");
        constitution = _constitution;
        emit ConstitutionSet(_constitution);
    }

    /**
     * @notice Reduce a member's trust score following a bad-faith arbitration finding.
     * @dev    Only callable by the authorised ArbitrationRegistry contract.
     *         Reverts if penalty > current score (no underflow; floor is 0).
     *         A trust score of 0 does NOT automatically revoke membership —
     *         that decision belongs to the steward and the legal wrapper process.
     * @param  member    Cooperative member whose score is slashed.
     * @param  penalty   Points to deduct (uint16; max 1000).
     * @param  caseHash  keccak256 hash of the arbitration case — links slash to evidence.
     */
    function slashTrust(
        address member,
        uint16  penalty,
        bytes32 caseHash
    ) external onlyArbitrationRegistry {
        uint256 tokenId = memberToken[member];
        if (tokenId == 0) revert NotAMember(member);

        uint16 current = memberRecords[tokenId].trustScore;
        if (penalty > current) revert TrustScoreUnderflow(current, penalty);

        uint16 newScore = current - penalty;
        memberRecords[tokenId].trustScore = newScore;

        emit TrustSlashed(member, penalty, newScore, caseHash);
    }

    /**
     * @notice Restore trust score after remediation.
     * @dev    Callable by steward (human gate) after the member has fulfilled
     *         the jury's remediation requirements.
     *         Score is capped at 1000 — cannot exceed the initial full-trust value.
     * @param  member       Cooperative member whose score is restored.
     * @param  restoration  Points to add back (capped at 1000).
     * @param  caseHash     Links restoration to the originating arbitration case.
     */
    function restoreTrust(
        address member,
        uint16  restoration,
        bytes32 caseHash
    ) external onlySteward {
        uint256 tokenId = memberToken[member];
        if (tokenId == 0) revert NotAMember(member);

        uint16 current  = memberRecords[tokenId].trustScore;
        uint16 newScore = uint16(
            uint256(current) + uint256(restoration) > 1000
                ? 1000
                : current + restoration
        );
        memberRecords[tokenId].trustScore = newScore;

        emit TrustRestored(member, restoration, newScore, caseHash);
    }

    /**
     * @notice Transfer stewardship to a new address (e.g., upgraded Safe).
     */
    function transferSteward(address _newSteward) external onlySteward {
        require(_newSteward != address(0), "CoopIdentity: zero address");
        emit StewardTransferred(steward, _newSteward);
        steward = _newSteward;
    }

    // ─── ERC-4973 View Functions ──────────────────────────────────────────────
    function balanceOf(address owner) external view override returns (uint256) {
        return _balances[owner];
    }

    function ownerOf(uint256 tokenId) external view override returns (address) {
        address owner = _owners[tokenId];
        require(owner != address(0), "CoopIdentity: token does not exist");
        return owner;
    }

    function tokenURI(uint256 tokenId) external view override returns (string memory) {
        require(_owners[tokenId] != address(0), "CoopIdentity: token does not exist");
        return _tokenURIs[tokenId];
    }

    /// @notice Returns the IPFS gateway URL for the legal wrapper document
    function legalWrapperURI() external view returns (string memory) {
        return string(abi.encodePacked("ipfs://", legalWrapperCID));
    }

    // ─── ERC-165 ─────────────────────────────────────────────────────────────
    function supportsInterface(bytes4 interfaceId)
        public view override(ERC165, IERC165)
        returns (bool)
    {
        return
            interfaceId == type(IERC4973).interfaceId ||
            super.supportsInterface(interfaceId);
    }

    // ─── ERC-4973: Explicitly Disable Transfers & Approvals ──────────────────
    /// @dev Any attempt to transfer reverts — tokens are account-bound by spec.
    function transferFrom(address, address, uint256) external pure {
        revert TransferProhibited();
    }

    function approve(address, uint256) external pure {
        revert ApprovalProhibited();
    }

    function setApprovalForAll(address, bool) external pure {
        revert ApprovalProhibited();
    }
}
