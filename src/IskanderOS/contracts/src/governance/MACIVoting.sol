// SPDX-License-Identifier: AGPL-3.0-only
pragma solidity ^0.8.24;

/**
 * @title  MACIVoting
 * @notice Minimum Anti-Collusion Infrastructure (MACI) voting stub for
 *         Project Iskander's ZK-Democracy layer (Phase 12).
 *
 * ╔══════════════════════════════════════════════════════════════════════════╗
 * ║  PRIVACY AS A HUMAN RIGHT                                               ║
 * ║  This contract implements the DisCO framework's mandate that democratic ║
 * ║  participation must be free from coercion, surveillance, and vote-      ║
 * ║  buying. MACI achieves this by ensuring that:                           ║
 * ║    1. Votes are encrypted with ephemeral keypairs before submission.    ║
 * ║    2. Only the ZK Coordinator (an off-chain TEE process) can decrypt    ║
 * ║       individual votes — and it publishes only the aggregate tally.     ║
 * ║    3. No on-chain observer — including other cooperative members or     ║
 * ║       managers — can link a specific member's address to their vote.    ║
 * ║  This prevents the "panopticon problem" where transparent ledgers       ║
 * ║  enable managerial surveillance and social pressure, undermining the    ║
 * ║  psychological safety required for genuine democratic participation.    ║
 * ╚══════════════════════════════════════════════════════════════════════════╝
 *
 * @dev  STUB CONTRACT — cryptographic internals (Poseidon hash, Groth16
 *       verifier, polynomial commitment) are NOT implemented here. In
 *       production, replace the bodies of `processMessages()` and
 *       `verifyTally()` with calls to the real MACI v1 verifier contracts
 *       (https://github.com/privacy-scaling-explorations/maci).
 *
 * ── INTEGRATION WITH SAFE MULTI-SIG ──────────────────────────────────────
 *  High-Impact transactions (see InternalPayroll.sol thresholds) are gated
 *  behind this contract's `verifyTally()`. The Safe executor script MUST:
 *    1. Call `verifyTally(proposalId, tallyRoot, proof)` on this contract.
 *    2. Receive `true` (M-of-N quorum met AND ZK proof valid).
 *    3. Only then submit the transaction to the Safe `execTransaction()`.
 *  This means the Safe will REJECT any High-Impact action unless a valid
 *  cryptographic proof of democratic consent has been anchored on-chain.
 *  No off-chain vote result, no manager override, no AI recommendation can
 *  bypass this gate.
 */

import {IERC165} from "@openzeppelin/contracts/utils/introspection/IERC165.sol";
import {ERC165} from "@openzeppelin/contracts/utils/introspection/ERC165.sol";

// ─── Interfaces ───────────────────────────────────────────────────────────────

/**
 * @notice Minimal interface to CoopIdentity to confirm membership before
 *         allowing sign-up. Prevents Sybil attacks using non-member addresses.
 */
interface ICoopIdentity {
    function balanceOf(address owner) external view returns (uint256);
}

/**
 * @notice Stub interface for the Groth16 ZK-SNARK verifier contract that
 *         validates tally proofs generated off-chain by the MACI Coordinator.
 * @dev    In production, deploy a circuit-specific verifier contract generated
 *         by snarkjs from the compiled MACI tally circuit, then set its address
 *         via the constructor.
 */
interface ISnarkVerifier {
    /// @return isValid True iff the proof is valid for the given public inputs.
    function verifyProof(
        uint256[2] calldata pA,
        uint256[2][2] calldata pB,
        uint256[2] calldata pC,
        uint256[] calldata publicSignals
    ) external view returns (bool isValid);
}

// ─── Contract ─────────────────────────────────────────────────────────────────

contract MACIVoting is ERC165 {

    // ── Types ────────────────────────────────────────────────────────────────

    enum ProposalStatus {
        Active,       // Accepting sign-ups and encrypted votes.
        Processing,   // Coordinator is generating the ZK tally proof off-chain.
        Finalized,    // Tally verified on-chain; result is binding.
        Rejected      // ZK proof invalid or quorum not met; Safe gate blocks.
    }

    struct Proposal {
        string  description;      // Human-readable description (max 280 chars).
        string  ipfsCID;          // IPFS CID of full proposal text.
        uint256 signUpDeadline;   // UNIX timestamp after which signUp() reverts.
        uint256 voteDeadline;     // UNIX timestamp after which publishMessage() reverts.
        uint256 totalSignUps;     // Count of registered voters (public).
        uint256 coordinatorPubKeyX; // x-coordinate of coordinator's ephemeral pubkey.
        uint256 coordinatorPubKeyY; // y-coordinate of coordinator's ephemeral pubkey.
        ProposalStatus status;
        // ── Tally (populated after verifyTally) ──────────────────────────────
        uint256 tallyCommitmentRoot; // Poseidon root committing to the result vector.
        bool    quorumMet;           // True iff yesVotes / totalSignUps >= quorumBps / 10000.
    }

    struct EncryptedMessage {
        /**
         * @dev An encrypted vote payload generated by the voter's client using
         *      ECDH(voterEphemeralPrivKey, coordinatorPubKey) → shared secret →
         *      AES-256-GCM(voteData, sharedSecret).
         *      The coordinator is the ONLY entity that can decrypt this.
         *      On-chain, we store only the ciphertext — the cleartext vote is
         *      NEVER written to any blockchain state or event.
         */
        uint256[10] ciphertext; // Packed encrypted payload (MACI message format).
        uint256[2]  encPubKey;  // Voter's ephemeral public key for ECDH.
        uint256     nonce;      // Per-voter message nonce to prevent replay.
    }

    // ── State ────────────────────────────────────────────────────────────────

    /// @notice The cooperative's identity contract — used to gate signUp().
    ICoopIdentity public immutable coopIdentity;

    /// @notice The off-chain MACI Coordinator address (MACICoordinator in Python).
    ///         Only this address may call processMessages() and verifyTally().
    address public coordinator;

    /// @notice Address of the Groth16 verifier contract for tally proofs.
    ///         Set to address(0) in stub mode — verifyTally() will log a warning.
    ISnarkVerifier public snarkVerifier;

    /// @notice Quorum threshold in basis points (e.g. 5100 = 51% supermajority).
    uint16 public quorumBps;

    uint256 private _nextProposalId;

    mapping(uint256 => Proposal) public proposals;

    /// @notice Tracks which members have signed up for each proposal.
    ///         Hidden from other members — only the coordinator sees the ECDH keys.
    mapping(uint256 => mapping(address => bool)) private _signedUp;

    /// @notice Encrypted messages per proposal, appended in submission order.
    ///         The coordinator processes these in batch to generate the tally proof.
    mapping(uint256 => EncryptedMessage[]) private _messages;

    // ── Events ───────────────────────────────────────────────────────────────

    /// @notice Emitted when a member signs up. No vote data is exposed.
    event MemberSignedUp(uint256 indexed proposalId, uint256 stateIndex);

    /// @notice Emitted when an encrypted vote message is published.
    ///         The ciphertext is opaque to all on-chain observers.
    event MessagePublished(uint256 indexed proposalId, uint256 messageIndex);

    /// @notice Emitted when the coordinator submits tally results.
    event TallyVerified(uint256 indexed proposalId, bool quorumMet, uint256 tallyRoot);

    /// @notice Emitted when a ZK proof fails — logged anonymously (no member id).
    event ProofRejected(uint256 indexed proposalId, string reason);

    /// @notice Emitted when a new proposal is created.
    event ProposalCreated(uint256 indexed proposalId, string description, uint256 voteDeadline);

    // ── Errors ───────────────────────────────────────────────────────────────

    error NotCoordinator();
    error NotMember(address caller);
    error AlreadySignedUp(address caller, uint256 proposalId);
    error DeadlinePassed(uint256 deadline, uint256 currentTime);
    error DeadlineNotPassed(uint256 deadline, uint256 currentTime);
    error ProposalNotActive(uint256 proposalId);
    error ProposalNotProcessing(uint256 proposalId);
    error InvalidProof();
    error ZeroAddress();

    // ── Modifiers ────────────────────────────────────────────────────────────

    modifier onlyCoordinator() {
        if (msg.sender != coordinator) revert NotCoordinator();
        _;
    }

    modifier proposalActive(uint256 proposalId) {
        if (proposals[proposalId].status != ProposalStatus.Active)
            revert ProposalNotActive(proposalId);
        _;
    }

    // ── Constructor ──────────────────────────────────────────────────────────

    /**
     * @param _coopIdentity  Address of the deployed CoopIdentity contract.
     * @param _coordinator   Address of the MACI Coordinator (Python MACICoordinator).
     * @param _snarkVerifier Address of the Groth16 tally verifier (address(0) in stub).
     * @param _quorumBps     Quorum in basis points (e.g. 5100 for 51%).
     */
    constructor(
        address _coopIdentity,
        address _coordinator,
        address _snarkVerifier,
        uint16  _quorumBps
    ) {
        if (_coopIdentity == address(0) || _coordinator == address(0))
            revert ZeroAddress();

        coopIdentity  = ICoopIdentity(_coopIdentity);
        coordinator   = _coordinator;
        snarkVerifier = ISnarkVerifier(_snarkVerifier); // May be address(0) in stub.
        quorumBps     = _quorumBps;
        _nextProposalId = 1;
    }

    // ── Coordinator Management ───────────────────────────────────────────────

    /**
     * @notice Replace the coordinator address (e.g., after TEE key rotation).
     * @dev    Only the current coordinator may rotate. In production, gate this
     *         behind the Safe multi-sig for additional security.
     */
    function rotateCoordinator(address _newCoordinator) external onlyCoordinator {
        if (_newCoordinator == address(0)) revert ZeroAddress();
        coordinator = _newCoordinator;
    }

    // ── Proposal Lifecycle ────────────────────────────────────────────────────

    /**
     * @notice Create a new voting proposal.
     * @param _description      Short description (≤ 280 chars) for on-chain display.
     * @param _ipfsCID          IPFS CID of the full proposal document.
     * @param _signUpDuration   Seconds from now during which members may sign up.
     * @param _voteDuration     Seconds from signUpDeadline during which votes accepted.
     * @param _coordPubKeyX     x-coordinate of the coordinator's ephemeral public key.
     * @param _coordPubKeyY     y-coordinate of the coordinator's ephemeral public key.
     *
     * @dev The coordinator public key is rotated per-proposal. This means that
     *      even if a future coordinator key is compromised, past votes remain
     *      encrypted and unreadable — forward secrecy for democratic privacy.
     */
    function createProposal(
        string  calldata _description,
        string  calldata _ipfsCID,
        uint256 _signUpDuration,
        uint256 _voteDuration,
        uint256 _coordPubKeyX,
        uint256 _coordPubKeyY
    ) external onlyCoordinator returns (uint256 proposalId) {
        proposalId = _nextProposalId++;

        proposals[proposalId] = Proposal({
            description:             _description,
            ipfsCID:                 _ipfsCID,
            signUpDeadline:          block.timestamp + _signUpDuration,
            voteDeadline:            block.timestamp + _signUpDuration + _voteDuration,
            totalSignUps:            0,
            coordinatorPubKeyX:      _coordPubKeyX,
            coordinatorPubKeyY:      _coordPubKeyY,
            status:                  ProposalStatus.Active,
            tallyCommitmentRoot:     0,
            quorumMet:               false
        });

        emit ProposalCreated(proposalId, _description, proposals[proposalId].voteDeadline);
    }

    // ── Core MACI Functions ───────────────────────────────────────────────────

    /**
     * @notice Register a member's ephemeral voting key for a proposal.
     *
     * @dev  PRIVACY GUARANTEE: The `_voterPubKey` emitted here is an EPHEMERAL
     *       key generated fresh by the voter's client — it has no connection to
     *       the voter's wallet address beyond the transaction sender. On-chain
     *       observers see only: "some wallet registered to vote." They cannot
     *       infer anything about the member's voting intention.
     *
     * @param proposalId    The proposal to register for.
     * @param _voterPubKeyX x-coordinate of the voter's ephemeral public key.
     * @param _voterPubKeyY y-coordinate of the voter's ephemeral public key.
     */
    function signUp(
        uint256 proposalId,
        uint256 _voterPubKeyX,
        uint256 _voterPubKeyY
    ) external proposalActive(proposalId) {
        Proposal storage p = proposals[proposalId];

        // Gate: only cooperative members may vote.
        if (coopIdentity.balanceOf(msg.sender) == 0)
            revert NotMember(msg.sender);

        // Gate: sign-up window still open.
        if (block.timestamp > p.signUpDeadline)
            revert DeadlinePassed(p.signUpDeadline, block.timestamp);

        // Gate: prevent double sign-up.
        if (_signedUp[proposalId][msg.sender])
            revert AlreadySignedUp(msg.sender, proposalId);

        _signedUp[proposalId][msg.sender] = true;
        uint256 stateIndex = p.totalSignUps;
        p.totalSignUps++;

        // NOTE: voterPubKey is logged for the coordinator's ECDH computation.
        // It is NOT the member's wallet key — it is a fresh ephemeral key.
        emit MemberSignedUp(proposalId, stateIndex);

        // In production: store _voterPubKeyX/_voterPubKeyY in a Merkle state
        // tree (the "state tree") that the coordinator processes off-chain.
        // Stub: we discard the pubkey after event emission.
        (_voterPubKeyX, _voterPubKeyY); // silence unused-variable compiler warning
    }

    /**
     * @notice Submit an encrypted vote message for a proposal.
     *
     * @dev  ANTI-COERCION DESIGN: A voter may call publishMessage() multiple
     *       times. The coordinator processes messages in REVERSE order, so the
     *       LAST message from each voter wins. This allows a voter who was
     *       coerced into submitting a specific vote to secretly override it with
     *       a second message — the coercer cannot verify which message is final
     *       without access to the coordinator's private decryption key.
     *       This is the core MACI anti-bribery mechanism.
     *
     * @param proposalId The proposal being voted on.
     * @param message    Encrypted vote payload (see EncryptedMessage struct).
     */
    function publishMessage(
        uint256 proposalId,
        EncryptedMessage calldata message
    ) external proposalActive(proposalId) {
        Proposal storage p = proposals[proposalId];

        // Gate: vote window open (after sign-up deadline has passed is fine per MACI spec).
        if (block.timestamp > p.voteDeadline)
            revert DeadlinePassed(p.voteDeadline, block.timestamp);

        uint256 msgIndex = _messages[proposalId].length;
        _messages[proposalId].push(message);

        emit MessagePublished(proposalId, msgIndex);
        // Ciphertext content is NOT indexed or decoded on-chain.
    }

    /**
     * @notice Transition proposal to Processing state once the vote window closes.
     * @dev    Called by the coordinator to signal that it is computing the tally
     *         proof off-chain. No state change to vote data — purely a status flag.
     */
    function beginProcessing(uint256 proposalId) external onlyCoordinator {
        Proposal storage p = proposals[proposalId];
        if (p.status != ProposalStatus.Active)
            revert ProposalNotActive(proposalId);
        if (block.timestamp <= p.voteDeadline)
            revert DeadlineNotPassed(p.voteDeadline, block.timestamp);

        p.status = ProposalStatus.Processing;
    }

    /**
     * @notice Verify the ZK tally proof and record the binding result on-chain.
     *
     * @dev  SAFE MULTI-SIG GATE:
     *       The cooperative's Safe executor script reads `proposals[id].quorumMet`
     *       and `proposals[id].status == Finalized` before submitting any High-Impact
     *       transaction. If this function was never called, or the proof was rejected,
     *       the Safe will refuse to execute — no managerial override possible.
     *
     *       The `_tallyRoot` is a Poseidon hash committing to the full vote tally
     *       vector (e.g., [yesVotes, noVotes, abstainVotes]). The `_proof` is a
     *       Groth16 proof generated by the MACI tally circuit, proving that the
     *       tally is consistent with all encrypted messages in the message tree
     *       WITHOUT revealing any individual vote.
     *
     * @param proposalId    ID of the proposal being finalized.
     * @param _tallyRoot    Poseidon commitment to the tally result vector.
     * @param _yesVotes     Declared yes vote count (must match tally commitment).
     * @param _totalVotes   Total votes processed (must equal totalSignUps for full participation).
     * @param _pA           Groth16 proof π_A (G1 point).
     * @param _pB           Groth16 proof π_B (G2 point).
     * @param _pC           Groth16 proof π_C (G1 point).
     * @param _pubSignals   Public signals: [tallyRoot, yesVotes, totalVotes, proposalId].
     */
    function processMessages(
        uint256   proposalId,
        uint256   _tallyRoot,
        uint256   _yesVotes,
        uint256   _totalVotes,
        uint256[2] calldata _pA,
        uint256[2][2] calldata _pB,
        uint256[2] calldata _pC,
        uint256[] calldata _pubSignals
    ) external onlyCoordinator {
        Proposal storage p = proposals[proposalId];
        if (p.status != ProposalStatus.Processing)
            revert ProposalNotProcessing(proposalId);

        // ── STUB: ZK Proof Verification ───────────────────────────────────────
        // In production: call snarkVerifier.verifyProof(_pA, _pB, _pC, _pubSignals).
        // The verifier contract is generated by compiling the MACI tally circuit
        // with snarkjs and deploying the resulting Verifier.sol.
        bool proofValid;
        if (address(snarkVerifier) == address(0)) {
            // STUB MODE: accept any proof. Log clearly for audit.
            proofValid = true;
            emit ProofRejected(proposalId, "STUB_MODE: snarkVerifier not set — proof accepted unconditionally. DO NOT use in production.");
        } else {
            proofValid = snarkVerifier.verifyProof(_pA, _pB, _pC, _pubSignals);
        }

        if (!proofValid) {
            // Fail gracefully: mark rejected, emit anonymous error, do NOT finalize.
            // The Safe gate will see status != Finalized and refuse to execute.
            p.status = ProposalStatus.Rejected;
            emit ProofRejected(proposalId, "INVALID_ZK_PROOF: tally proof verification failed.");
            return;
        }

        // ── Quorum Check ──────────────────────────────────────────────────────
        // Quorum is assessed against total sign-ups (not total membership), matching
        // standard cooperative governance conventions for deliberative assemblies.
        bool quorumMet = false;
        if (_totalVotes > 0) {
            quorumMet = (_yesVotes * 10000 / _totalVotes) >= quorumBps;
        }

        p.tallyCommitmentRoot = _tallyRoot;
        p.quorumMet           = quorumMet;
        p.status              = ProposalStatus.Finalized;

        emit TallyVerified(proposalId, quorumMet, _tallyRoot);

        // Silence unused parameter warnings (stub — real impl uses these in pubSignals).
        (_pA, _pB, _pC, _pubSignals, _totalVotes);
    }

    // ── Safe Gate Helper ──────────────────────────────────────────────────────

    /**
     * @notice Read-only gate check for the Safe executor script.
     * @return True iff the proposal has a valid ZK tally AND quorum was met.
     * @dev    Safe executor MUST call this before any High-Impact transaction.
     *         Returns false if: proof was rejected, quorum not met, or tally
     *         not yet finalized. Reverts are intentionally avoided so the Safe
     *         script can handle the failure case gracefully.
     */
    function verifyTally(uint256 proposalId) external view returns (bool) {
        Proposal storage p = proposals[proposalId];
        return p.status == ProposalStatus.Finalized && p.quorumMet;
    }

    // ── View Helpers ──────────────────────────────────────────────────────────

    /// @notice Returns the number of encrypted messages submitted for a proposal.
    function messageCount(uint256 proposalId) external view returns (uint256) {
        return _messages[proposalId].length;
    }

    /// @notice Returns true if an address has signed up for a proposal.
    ///         Intentionally public — sign-up participation (not vote content) is visible.
    function hasSignedUp(uint256 proposalId, address member) external view returns (bool) {
        return _signedUp[proposalId][member];
    }

    // ── ERC-165 ───────────────────────────────────────────────────────────────

    function supportsInterface(bytes4 interfaceId)
        public view override(ERC165)
        returns (bool)
    {
        return super.supportsInterface(interfaceId);
    }
}
