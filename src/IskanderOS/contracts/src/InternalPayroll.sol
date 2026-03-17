// SPDX-License-Identifier: AGPL-3.0-only
pragma solidity ^0.8.24;

/**
 * @title  InternalPayroll
 * @notice Enforces a Mondragon-style pay ratio cap between the highest and
 *         lowest compensated worker-owners in the cooperative.
 *
 * LEGAL NOTICE:
 *   This contract enforces the pay-ratio rule as defined in the cooperative's
 *   legal wrapper. It does NOT constitute a complete payroll or employment
 *   contract. Tax obligations, labour law compliance, and member consent
 *   remain governed by the off-chain legal wrapper bound to CoopIdentity's
 *   `legalWrapperCID`. EVM reverts logged here are advisory — human stewards
 *   MUST review any revert before re-routing funds.
 *
 * @dev    Mondragon Cooperatives historically use a 6:1 ratio (highest:lowest).
 *         This is configurable at deploy time and adjustable by the steward Safe.
 *
 *         Flow:
 *           1. Steward registers members with their annualised base pay.
 *           2. `pay()` reverts if the proposed payment would push any member's
 *              effective rate above `maxRatio × lowestBasePay`.
 *           3. Reverts are surfaced to the backend and persisted in Postgres.
 */

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {CoopIdentity} from "./CoopIdentity.sol";

contract InternalPayroll {
    using SafeERC20 for IERC20;

    // ─── Configuration ────────────────────────────────────────────────────────
    CoopIdentity public immutable identity;
    address       public steward;

    /// @notice Maximum ratio of highest:lowest annualised pay (scaled ×100 to
    ///         allow fractional ratios, e.g. 600 = 6.00×, 150 = 1.50×).
    uint256 public maxRatioScaled;   // default: 600 (6:1)

    // ─── Member Pay Registry ──────────────────────────────────────────────────
    struct PayRecord {
        uint256 annualisedBase;   // in token's smallest unit (e.g. USDC 6 dec)
        bool    registered;
    }
    mapping(address => PayRecord) public payRegistry;

    /// @notice Sorted tracking of lowest registered base pay (cache)
    uint256 public lowestBasePay;   // updated on register / deregister
    uint256 public memberCount;

    // Ordered list for lowest-pay tracking
    address[] private _members;

    // ─── Events ───────────────────────────────────────────────────────────────
    event MemberRegistered(address indexed member, uint256 annualisedBase);
    event MemberDeregistered(address indexed member);
    event PaymentExecuted(address indexed member, address token, uint256 amount);
    event RatioUpdated(uint256 oldRatio, uint256 newRatio);
    event PayRatioViolation(
        address indexed member,
        uint256 attemptedAmount,
        uint256 maxAllowed,
        uint256 lowestBase
    );

    // ─── Errors ───────────────────────────────────────────────────────────────
    error NotSteward();
    error NotAMember(address account);
    error AlreadyRegistered(address account);
    error PayRatioExceeded(uint256 attempted, uint256 maxAllowed);
    error ZeroAmount();
    error NoMembersRegistered();
    error InvalidRatio();

    // ─── Constructor ─────────────────────────────────────────────────────────
    /**
     * @param _identity      Deployed CoopIdentity contract
     * @param _steward       Steward Safe address
     * @param _maxRatioScaled Pay cap ratio × 100 (e.g. 600 for 6:1 Mondragon standard)
     */
    constructor(
        address _identity,
        address _steward,
        uint256 _maxRatioScaled
    ) {
        require(_identity != address(0), "InternalPayroll: zero identity");
        require(_steward  != address(0), "InternalPayroll: zero steward");
        require(_maxRatioScaled >= 100,  "InternalPayroll: ratio must be >= 1.00x (100)");

        identity       = CoopIdentity(_identity);
        steward        = _steward;
        maxRatioScaled = _maxRatioScaled;
    }

    // ─── Modifiers ────────────────────────────────────────────────────────────
    modifier onlySteward() {
        if (msg.sender != steward) revert NotSteward();
        _;
    }

    modifier onlyMember(address account) {
        if (identity.memberToken(account) == 0) revert NotAMember(account);
        _;
    }

    // ─── Member Registration ─────────────────────────────────────────────────
    /**
     * @notice Register a member's annualised base pay.
     * @dev    `annualisedBase` should be expressed in the ERC-20 token's
     *         smallest unit for consistency with `pay()`.
     */
    function registerMember(address member, uint256 annualisedBase)
        external
        onlySteward
        onlyMember(member)
    {
        if (payRegistry[member].registered) revert AlreadyRegistered(member);
        require(annualisedBase > 0, "InternalPayroll: zero base pay");

        payRegistry[member] = PayRecord({
            annualisedBase: annualisedBase,
            registered:     true
        });
        _members.push(member);
        memberCount++;

        _recalculateLowest();
        emit MemberRegistered(member, annualisedBase);
    }

    /**
     * @notice Deregister a member (e.g. on membership revocation).
     */
    function deregisterMember(address member) external onlySteward {
        if (!payRegistry[member].registered) revert NotAMember(member);

        delete payRegistry[member];
        memberCount--;

        // Remove from _members array
        for (uint256 i = 0; i < _members.length; i++) {
            if (_members[i] == member) {
                _members[i] = _members[_members.length - 1];
                _members.pop();
                break;
            }
        }

        _recalculateLowest();
        emit MemberDeregistered(member);
    }

    // ─── Pay Execution ────────────────────────────────────────────────────────
    /**
     * @notice Transfer `amount` of `token` to `member`, enforcing the pay ratio.
     * @dev    `amount` is treated as an annualised equivalent for ratio checking.
     *         For period-based payments, callers must annualise before calling.
     *
     *         REVERT BEHAVIOUR: Any violation emits `PayRatioViolation` before
     *         reverting so the backend can capture the reason via eth_getLogs
     *         (simulated call) and persist to the `evm_reverts` Postgres table.
     */
    function pay(
        address member,
        address token,
        uint256 amount         // annualised equivalent in token units
    ) external onlySteward onlyMember(member) {
        if (amount == 0) revert ZeroAmount();
        if (memberCount == 0) revert NoMembersRegistered();

        uint256 _lowest = lowestBasePay;
        if (_lowest == 0) revert NoMembersRegistered();

        uint256 maxAllowed = (_lowest * maxRatioScaled) / 100;

        if (amount > maxAllowed) {
            emit PayRatioViolation(member, amount, maxAllowed, _lowest);
            revert PayRatioExceeded(amount, maxAllowed);
        }

        IERC20(token).safeTransferFrom(msg.sender, member, amount);
        emit PaymentExecuted(member, token, amount);
    }

    // ─── Governance ───────────────────────────────────────────────────────────
    /**
     * @notice Update the pay ratio cap. Requires steward Safe approval.
     * @dev    Changing the ratio is a significant governance action that MUST
     *         be ratified via the process in the legal wrapper before execution.
     */
    function updateMaxRatio(uint256 _newRatioScaled) external onlySteward {
        if (_newRatioScaled < 100) revert InvalidRatio();
        emit RatioUpdated(maxRatioScaled, _newRatioScaled);
        maxRatioScaled = _newRatioScaled;
    }

    function transferSteward(address _new) external onlySteward {
        require(_new != address(0), "InternalPayroll: zero address");
        steward = _new;
    }

    // ─── Internal ─────────────────────────────────────────────────────────────
    function _recalculateLowest() internal {
        if (_members.length == 0) {
            lowestBasePay = 0;
            return;
        }
        uint256 lowest = type(uint256).max;
        for (uint256 i = 0; i < _members.length; i++) {
            uint256 base = payRegistry[_members[i]].annualisedBase;
            if (base > 0 && base < lowest) lowest = base;
        }
        lowestBasePay = (lowest == type(uint256).max) ? 0 : lowest;
    }

    // ─── View Helpers ─────────────────────────────────────────────────────────
    /**
     * @notice Returns maximum allowable annualised pay for any member
     *         given current lowest base pay and ratio.
     */
    function currentPayCeiling() external view returns (uint256) {
        if (lowestBasePay == 0) return 0;
        return (lowestBasePay * maxRatioScaled) / 100;
    }

    function getMembers() external view returns (address[] memory) {
        return _members;
    }
}
