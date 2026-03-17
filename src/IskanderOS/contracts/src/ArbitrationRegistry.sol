// SPDX-License-Identifier: AGPL-3.0-only
pragma solidity ^0.8.24;

/**
 * @title  ArbitrationRegistry
 * @notice On-chain verdict records for the Iskander Solidarity Court (Phase 15).
 *
 * DESIGN PHILOSOPHY:
 *   The Arbitrator Agent NEVER renders a verdict autonomously. This contract
 *   only records verdicts that have been:
 *     1. Deliberated by a federated jury of humans from sister cooperatives.
 *     2. Submitted by the ArbitrationRegistry operator (a Safe multi-sig) after
 *        the human jury has reached consensus via Matrix rooms + ActivityPub.
 *     3. Cryptographically committed to the case hash for tamper-evidence.
 *
 *   The contract stores only the verdict hash, outcome, and trust adjustments.
 *   All deliberation content (evidence, jury deliberation logs) is stored
 *   off-chain under IPFS CIDs — preserving privacy while maintaining integrity.
 *
 * TRUST SCORE SLASHING:
 *   Bad-faith actors (e.g., a cooperative that raises fraudulent disputes or
 *   fails to deliver goods) face a trust score reduction on their CoopIdentity
 *   SBT. This is not punitive — it is reputational signal for future trades.
 *   Rehabilitation: `CoopIdentity.restoreTrust()` is available after a
 *   community-approved rehabilitation process.
 *
 * @dev  Case hashes use keccak256(escrowId, caseId, verdictOutcome) for
 *       tamper-evident commitment. The full case record lives off-chain.
 */

import {CoopIdentity} from "./CoopIdentity.sol";
import {IskanderEscrow} from "./IskanderEscrow.sol";

contract ArbitrationRegistry {

    // ── Types ─────────────────────────────────────────────────────────────────

    enum VerdictOutcome {
        BuyerFavored,   // Full or partial refund to buyer; seller found at fault.
        SellerFavored,  // Full release to seller; buyer's dispute deemed bad-faith.
        Split,          // Negotiated split — both parties partially compensated.
        Dismissed       // Dispute dismissed (frivolous); no trust slash.
    }

    struct ArbitrationCase {
        uint256 escrowId;
        bytes32 caseHash;          // keccak256(escrowId, caseId, juryIpfsCid)
        VerdictOutcome outcome;
        uint256 buyerAmount;       // Token amount returned to buyer.
        uint256 sellerAmount;      // Token amount released to seller.
        string  juryIpfsCid;       // IPFS CID of the jury deliberation record.
        bool    executed;          // True after IskanderEscrow.executeVerdict() called.
        uint256 recordedAt;
    }

    // ── State ─────────────────────────────────────────────────────────────────

    CoopIdentity    public immutable coopIdentity;
    IskanderEscrow  public immutable escrowContract;

    /// @notice The Safe multi-sig that may record verdicts.
    ///         In production: a dedicated ArbitrationSafe with jury members as signers.
    address public operator;

    uint256 private _nextCaseId;

    mapping(uint256 => ArbitrationCase) public cases;

    /// @notice Maps escrowId → caseId for quick lookup.
    mapping(uint256 => uint256) public escrowToCase;

    // ── Events ────────────────────────────────────────────────────────────────

    event CaseOpened(uint256 indexed caseId, uint256 indexed escrowId, bytes32 caseHash);
    event VerdictRecorded(
        uint256 indexed caseId,
        uint256 indexed escrowId,
        VerdictOutcome outcome,
        string  juryIpfsCid
    );
    event VerdictExecuted(uint256 indexed caseId, uint256 indexed escrowId);
    event TrustAdjusted(address indexed party, uint256 caseId, int16 delta);

    // ── Errors ────────────────────────────────────────────────────────────────

    error NotOperator(address caller);
    error CaseAlreadyExists(uint256 escrowId);
    error CaseNotFound(uint256 caseId);
    error AlreadyExecuted(uint256 caseId);

    // ── Modifiers ─────────────────────────────────────────────────────────────

    modifier onlyOperator() {
        if (msg.sender != operator) revert NotOperator(msg.sender);
        _;
    }

    // ── Constructor ───────────────────────────────────────────────────────────

    /**
     * @param _coopIdentity  Address of CoopIdentity (for trust score adjustments).
     * @param _escrow        Address of IskanderEscrow (to call executeVerdict).
     * @param _operator      Address of the ArbitrationSafe (multi-sig jury operator).
     */
    constructor(
        address _coopIdentity,
        address _escrow,
        address _operator
    ) {
        require(_coopIdentity != address(0) && _escrow != address(0) && _operator != address(0),
            "ArbitrationRegistry: zero address");
        coopIdentity = CoopIdentity(_coopIdentity);
        escrowContract = IskanderEscrow(_escrow);
        operator = _operator;
        _nextCaseId = 1;
    }

    // ── Case Management ───────────────────────────────────────────────────────

    /**
     * @notice Open a new arbitration case for a disputed escrow.
     *
     * @dev  Called by the operator Safe after the Iskander backend has received
     *       a `DisputeRaised` event from IskanderEscrow and completed the
     *       off-chain jury selection process (ActivityPub + HITL).
     *
     * @param _escrowId     The disputed escrow ID.
     * @param _juryIpfsCid  IPFS CID of the jury selection and evidence record.
     *
     * @return caseId  The newly assigned case ID.
     */
    function openCase(
        uint256 _escrowId,
        string calldata _juryIpfsCid
    ) external onlyOperator returns (uint256 caseId) {
        if (escrowToCase[_escrowId] != 0) revert CaseAlreadyExists(_escrowId);

        caseId = _nextCaseId++;
        bytes32 caseHash = keccak256(abi.encodePacked(_escrowId, caseId, _juryIpfsCid));

        cases[caseId] = ArbitrationCase({
            escrowId:     _escrowId,
            caseHash:     caseHash,
            outcome:      VerdictOutcome.Dismissed,  // Default; overwritten on verdict.
            buyerAmount:  0,
            sellerAmount: 0,
            juryIpfsCid:  _juryIpfsCid,
            executed:     false,
            recordedAt:   block.timestamp
        });
        escrowToCase[_escrowId] = caseId;

        emit CaseOpened(caseId, _escrowId, caseHash);
    }

    /**
     * @notice Record the federated jury's verdict and execute the escrow release.
     *
     * @dev  This function:
     *   1. Records the verdict on-chain with the jury IPFS CID.
     *   2. Calls IskanderEscrow.executeVerdict() to release funds.
     *   3. Adjusts trust scores on CoopIdentity for bad-faith parties.
     *
     * HITL GATE:
     *   The operator Safe requires M-of-N jury signatures to call this function.
     *   The Arbitrator Agent facilitates the process but NEVER signs autonomously.
     *
     * @param _caseId        The case being resolved.
     * @param _outcome       The jury's verdict outcome.
     * @param _buyerAmount   Tokens to return to the buyer.
     * @param _sellerAmount  Tokens to release to the seller.
     * @param _buyerSlash    Trust score penalty for the buyer (0 if not at fault).
     * @param _sellerSlash   Trust score penalty for the seller (0 if not at fault).
     */
    function recordVerdict(
        uint256 _caseId,
        VerdictOutcome _outcome,
        uint256 _buyerAmount,
        uint256 _sellerAmount,
        uint16  _buyerSlash,
        uint16  _sellerSlash
    ) external onlyOperator {
        ArbitrationCase storage c = cases[_caseId];
        if (c.recordedAt == 0) revert CaseNotFound(_caseId);
        if (c.executed) revert AlreadyExecuted(_caseId);

        c.outcome     = _outcome;
        c.buyerAmount = _buyerAmount;
        c.sellerAmount = _sellerAmount;
        c.executed    = true;

        emit VerdictRecorded(_caseId, c.escrowId, _outcome, c.juryIpfsCid);

        // Execute escrow fund distribution.
        escrowContract.executeVerdict(c.escrowId, _buyerAmount, _sellerAmount);
        emit VerdictExecuted(_caseId, c.escrowId);

        // Apply trust score adjustments to bad-faith parties.
        // Fetches party addresses from the escrow contract.
        IskanderEscrow.Escrow memory esc = escrowContract.getEscrow(c.escrowId);

        if (_buyerSlash > 0) {
            _slashTrust(esc.buyerCoop, _buyerSlash, _caseId);
        }
        if (_sellerSlash > 0) {
            _slashTrust(esc.sellerCoop, _sellerSlash, _caseId);
        }
    }

    // ── Trust Score Management ────────────────────────────────────────────────

    /**
     * @notice Slash the trust score of a party found to have acted in bad faith.
     *
     * @dev  Calls CoopIdentity.slashTrust(). The affected member's SBT trustScore
     *       is reduced, signalling reduced reliability for future inter-coop trades.
     *
     *       This is a REPUTATIONAL signal, not a punitive measure. The cooperative
     *       community decides what trust score threshold to require for new trades.
     */
    function _slashTrust(
        address _party,
        uint16  _penalty,
        uint256 _caseId
    ) internal {
        bytes32 caseHash = cases[_caseId].caseHash;
        // CoopIdentity.slashTrust is called on the member's token.
        // Note: _party is a Safe address; CoopIdentity.memberToken maps addresses to tokenIds.
        uint256 tokenId = coopIdentity.memberToken(_party);
        if (tokenId != 0) {
            coopIdentity.slashTrust(_party, _penalty, caseHash);
            emit TrustAdjusted(_party, _caseId, -int16(_penalty));
        }
    }

    /**
     * @notice Restore trust score after a community-approved rehabilitation process.
     *
     * @param _party        Address of the member/coop being rehabilitated.
     * @param _restoration  Points to restore.
     * @param _caseId       The original case ID (for audit trail).
     */
    function restoreTrust(
        address _party,
        uint16  _restoration,
        uint256 _caseId
    ) external onlyOperator {
        bytes32 caseHash = cases[_caseId].caseHash;
        coopIdentity.restoreTrust(_party, _restoration, caseHash);
        emit TrustAdjusted(_party, _caseId, int16(_restoration));
    }

    // ── View Helpers ──────────────────────────────────────────────────────────

    function getCase(uint256 caseId) external view returns (ArbitrationCase memory) {
        return cases[caseId];
    }

    function getCaseByEscrow(uint256 escrowId) external view returns (ArbitrationCase memory) {
        uint256 caseId = escrowToCase[escrowId];
        return cases[caseId];
    }
}
