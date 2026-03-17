// SPDX-License-Identifier: AGPL-3.0-only
pragma solidity ^0.8.24;

/**
 * @title  IskanderEscrow
 * @notice Escrow contract for inter-cooperative trade with locked fund release.
 *
 * LEGAL NOTICE:
 *   This contract enforces payment terms for inter-coop trade as defined in
 *   the terms_ipfs_cid Ricardian contract. It does NOT replace legal contract
 *   law. In any dispute, the off-chain legal instrument governs. The escrow
 *   is a technical enforcement mechanism, not a substitute for cooperative
 *   accountability and good faith.
 *
 * FLOW:
 *   1. Buyer coop calls `createEscrow()` — funds locked in this contract.
 *   2. Seller coop delivers goods/services off-chain.
 *   3. Buyer calls `confirmDelivery()` — releases funds to seller.
 *   4. If disputed: either party calls `dispute()` — triggers federated jury
 *      via ActivityPub (Phase 15 off-chain flow).
 *   5. ArbitrationRegistry.sol calls `executeVerdict()` after jury decision.
 *
 * ── SAFE MULTI-SIG INTEGRATION ────────────────────────────────────────────────
 *   createEscrow() and executeVerdict() should be called by the cooperatives'
 *   respective Safe multi-sig wallets, ensuring democratic approval of both
 *   the trade commitment and the verdict execution.
 *
 * @dev Follows the Checks-Effects-Interactions pattern. Uses ReentrancyGuard.
 *      ERC-20 tokens only — native ETH escrow left as a future extension.
 */

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/security/ReentrancyGuard.sol";
import {CoopIdentity} from "./CoopIdentity.sol";

contract IskanderEscrow is ReentrancyGuard {
    using SafeERC20 for IERC20;

    // ── Types ─────────────────────────────────────────────────────────────────

    enum EscrowStatus {
        Active,       // Funds locked; awaiting delivery confirmation.
        Released,     // Funds released to seller — trade complete.
        Disputed,     // Dispute raised; awaiting federated jury verdict.
        Arbitrated,   // Verdict executed — funds distributed per ruling.
        Expired       // Deadline passed with no action; refund available.
    }

    struct Escrow {
        address buyerCoop;        // Buyer cooperative's Safe address.
        address sellerCoop;       // Seller cooperative's Safe address.
        IERC20  token;            // ERC-20 token used for payment.
        uint256 amount;           // Total locked amount (in token's smallest unit).
        string  termsIpfsCid;     // IPFS CID of the Ricardian trade contract.
        EscrowStatus status;
        uint256 createdAt;
        uint256 expiresAt;        // Unix timestamp; 0 = no expiry.
        bytes32 disputeHash;      // keccak256(escrowId, disputeDescription) — set on dispute.
    }

    // ── State ─────────────────────────────────────────────────────────────────

    /// @notice The cooperative identity contract — verifies membership of both parties.
    CoopIdentity public immutable coopIdentity;

    /// @notice The ArbitrationRegistry that may call executeVerdict().
    address public arbitrationRegistry;

    uint256 private _nextEscrowId;

    mapping(uint256 => Escrow) public escrows;

    // ── Events ────────────────────────────────────────────────────────────────

    event EscrowCreated(
        uint256 indexed escrowId,
        address indexed buyerCoop,
        address indexed sellerCoop,
        address token,
        uint256 amount,
        string  termsIpfsCid
    );
    event DeliveryConfirmed(uint256 indexed escrowId, address indexed confirmedBy);
    /// @notice Phase 22: Emitted when funds are released to the seller cooperative.
    ///         The off-chain Fiat Gateway Agent monitors this event to propose
    ///         off-ramp decisions (hold cFIAT on-chain vs burn to physical bank).
    event FiatSettlementReady(
        uint256 indexed escrowId,
        address indexed sellerCoop,
        address token,
        uint256 amount
    );
    event DisputeRaised(uint256 indexed escrowId, address indexed raisedBy, bytes32 disputeHash);
    event VerdictExecuted(
        uint256 indexed escrowId,
        address buyerRefund,
        uint256 buyerAmount,
        address sellerPayout,
        uint256 sellerAmount
    );
    event EscrowExpired(uint256 indexed escrowId);

    // ── Errors ────────────────────────────────────────────────────────────────

    error NotParty(address caller);
    error NotArbitrationRegistry(address caller);
    error WrongStatus(EscrowStatus current, EscrowStatus required);
    error InvalidSplit();
    error ZeroAmount();
    error ZeroAddress();
    error DeadlineExpired(uint256 deadline);
    error NotExpiredYet(uint256 deadline, uint256 currentTime);

    // ── Modifiers ─────────────────────────────────────────────────────────────

    modifier onlyParty(uint256 escrowId) {
        Escrow storage e = escrows[escrowId];
        if (msg.sender != e.buyerCoop && msg.sender != e.sellerCoop)
            revert NotParty(msg.sender);
        _;
    }

    modifier onlyArbitrationRegistry() {
        if (msg.sender != arbitrationRegistry)
            revert NotArbitrationRegistry(msg.sender);
        _;
    }

    modifier inStatus(uint256 escrowId, EscrowStatus required) {
        if (escrows[escrowId].status != required)
            revert WrongStatus(escrows[escrowId].status, required);
        _;
    }

    // ── Constructor ───────────────────────────────────────────────────────────

    /**
     * @param _coopIdentity        Address of the CoopIdentity membership contract.
     * @param _arbitrationRegistry Address of the ArbitrationRegistry (set after deploy).
     *                             Pass address(0) initially; set via setArbitrationRegistry().
     */
    constructor(address _coopIdentity, address _arbitrationRegistry) {
        if (_coopIdentity == address(0)) revert ZeroAddress();
        coopIdentity = CoopIdentity(_coopIdentity);
        arbitrationRegistry = _arbitrationRegistry;
        _nextEscrowId = 1;
    }

    function setArbitrationRegistry(address _registry) external {
        // In production: gate this behind onlySteward or Safe multi-sig.
        require(_registry != address(0), "IskanderEscrow: zero address");
        arbitrationRegistry = _registry;
    }

    // ── Core Functions ────────────────────────────────────────────────────────

    /**
     * @notice Lock funds for an inter-cooperative trade.
     *
     * @dev  The buyer must approve this contract for `_amount` tokens before calling.
     *       Both `_buyerCoop` and `_sellerCoop` should hold CoopIdentity SBTs to
     *       confirm they are valid cooperative members — this is verified off-chain
     *       by the Iskander backend before the Safe submits this transaction.
     *
     * @param _sellerCoop    Address of the seller cooperative's Safe wallet.
     * @param _token         ERC-20 token contract address.
     * @param _amount        Amount of tokens to lock.
     * @param _termsIpfsCid  IPFS CID of the Ricardian trade contract (immutable record).
     * @param _expiresAt     Unix timestamp for automatic expiry (0 = no expiry).
     *
     * @return escrowId  The ID of the newly created escrow.
     */
    function createEscrow(
        address _sellerCoop,
        address _token,
        uint256 _amount,
        string calldata _termsIpfsCid,
        uint256 _expiresAt
    ) external nonReentrant returns (uint256 escrowId) {
        if (_sellerCoop == address(0) || _token == address(0)) revert ZeroAddress();
        if (_amount == 0) revert ZeroAmount();
        if (_expiresAt != 0 && _expiresAt <= block.timestamp)
            revert DeadlineExpired(_expiresAt);

        escrowId = _nextEscrowId++;

        escrows[escrowId] = Escrow({
            buyerCoop:   msg.sender,
            sellerCoop:  _sellerCoop,
            token:       IERC20(_token),
            amount:      _amount,
            termsIpfsCid: _termsIpfsCid,
            status:      EscrowStatus.Active,
            createdAt:   block.timestamp,
            expiresAt:   _expiresAt,
            disputeHash: bytes32(0)
        });

        // Pull tokens from buyer — buyer must have called token.approve() first.
        IERC20(_token).safeTransferFrom(msg.sender, address(this), _amount);

        emit EscrowCreated(escrowId, msg.sender, _sellerCoop, _token, _amount, _termsIpfsCid);
    }

    /**
     * @notice Confirm delivery and release funds to the seller cooperative.
     *
     * @dev  Only the buyer cooperative may confirm delivery.
     *       This is the happy path — no arbitration needed.
     */
    function confirmDelivery(uint256 escrowId)
        external
        nonReentrant
        inStatus(escrowId, EscrowStatus.Active)
    {
        Escrow storage e = escrows[escrowId];
        if (msg.sender != e.buyerCoop) revert NotParty(msg.sender);

        // Checks-Effects-Interactions
        e.status = EscrowStatus.Released;
        e.token.safeTransfer(e.sellerCoop, e.amount);

        emit DeliveryConfirmed(escrowId, msg.sender);
        // Phase 22: Signal to the off-chain Fiat Gateway Agent that cFIAT
        // has been released. The agent will propose: hold on-chain or off-ramp
        // to the cooperative's physical bank account.
        emit FiatSettlementReady(escrowId, e.sellerCoop, address(e.token), e.amount);
    }

    /**
     * @notice Raise a dispute to trigger the federated arbitration process.
     *
     * @dev  Either party may raise a dispute while the escrow is Active.
     *       The `_disputeDescription` is NOT stored on-chain (gas efficiency +
     *       privacy). A hash is stored for integrity verification. The full
     *       description is stored in the off-chain ArbitrationCase record.
     *
     * @param escrowId            The escrow being disputed.
     * @param _disputeDescription Free-text description of the dispute (hashed only).
     */
    function dispute(
        uint256 escrowId,
        string calldata _disputeDescription
    )
        external
        onlyParty(escrowId)
        inStatus(escrowId, EscrowStatus.Active)
    {
        Escrow storage e = escrows[escrowId];

        bytes32 hash = keccak256(abi.encodePacked(escrowId, _disputeDescription));
        e.status = EscrowStatus.Disputed;
        e.disputeHash = hash;

        emit DisputeRaised(escrowId, msg.sender, hash);
        // Off-chain: the Iskander backend observes this event and initiates
        // the federated jury selection via ActivityPub (Phase 15 protocol).
    }

    /**
     * @notice Execute an arbitration verdict by releasing funds per jury ruling.
     *
     * @dev  Only callable by the ArbitrationRegistry contract after the federated
     *       jury has recorded a verdict. The split must sum to e.amount.
     *
     * @param escrowId       The escrow being resolved.
     * @param buyerAmount    Wei to return to the buyer cooperative.
     * @param sellerAmount   Wei to release to the seller cooperative.
     */
    function executeVerdict(
        uint256 escrowId,
        uint256 buyerAmount,
        uint256 sellerAmount
    )
        external
        nonReentrant
        onlyArbitrationRegistry
        inStatus(escrowId, EscrowStatus.Disputed)
    {
        Escrow storage e = escrows[escrowId];
        if (buyerAmount + sellerAmount != e.amount) revert InvalidSplit();

        e.status = EscrowStatus.Arbitrated;

        if (buyerAmount > 0)  e.token.safeTransfer(e.buyerCoop,  buyerAmount);
        if (sellerAmount > 0) e.token.safeTransfer(e.sellerCoop, sellerAmount);

        emit VerdictExecuted(escrowId, e.buyerCoop, buyerAmount, e.sellerCoop, sellerAmount);
    }

    /**
     * @notice Refund the buyer if the escrow has expired with no action.
     *
     * @dev  Available to either party once `expiresAt` has passed and the
     *       escrow is still Active (not disputed or released).
     */
    function claimExpiry(uint256 escrowId)
        external
        nonReentrant
        onlyParty(escrowId)
        inStatus(escrowId, EscrowStatus.Active)
    {
        Escrow storage e = escrows[escrowId];
        if (e.expiresAt == 0 || block.timestamp < e.expiresAt)
            revert NotExpiredYet(e.expiresAt, block.timestamp);

        e.status = EscrowStatus.Expired;
        e.token.safeTransfer(e.buyerCoop, e.amount);

        emit EscrowExpired(escrowId);
    }

    // ── View Helpers ──────────────────────────────────────────────────────────

    function getEscrow(uint256 escrowId) external view returns (Escrow memory) {
        return escrows[escrowId];
    }
}
