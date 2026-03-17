// SPDX-License-Identifier: AGPL-3.0-only
pragma solidity ^0.8.24;

/**
 * @title  CoopFiatToken (cFIAT)
 * @notice ERC-20 token backed 1:1 by fiat held in a cooperative bank trust account.
 *
 * ANTI-EXTRACTIVE:
 *   This token exists to bypass Visa, Mastercard, and Stripe. Inter-cooperative
 *   commerce settles directly via cooperative bank rails, returning the 2-3%
 *   transaction fees back to the workers and the cooperative ecosystem.
 *
 * REGULATORY REALISM:
 *   Every cFIAT token in circulation is backed by an equivalent amount of fiat
 *   currency held in a regulated cooperative bank trust account. This is NOT
 *   fractional reserve. The BankOracle address represents the physical bank's
 *   API bridge — it can only mint when a real deposit is confirmed, and burn
 *   when a real withdrawal is executed.
 *
 * ACCESS CONTROL:
 *   - Only the designated BankOracle address can mint() and burn().
 *   - The BankOracle is the off-chain bridge operated by the cooperative's
 *     treasury, gated by BrightID-verified Human-in-the-Loop approval.
 *   - The cooperative's Safe multi-sig can update the BankOracle address
 *     via setBankOracle() if the bridge needs to be rotated.
 *
 * @dev Extends OpenZeppelin ERC20 with restricted mint/burn roles.
 */

import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";

contract CoopFiatToken is ERC20 {
    // ── State ─────────────────────────────────────────────────────────────────

    /// @notice The only address permitted to mint and burn cFIAT.
    ///         Represents the cooperative bank's off-chain API bridge.
    address public bankOracle;

    /// @notice The Safe multi-sig that governs this token contract.
    address public immutable governance;

    // ── Events ────────────────────────────────────────────────────────────────

    /// @notice Emitted when cFIAT is minted after a confirmed fiat deposit.
    event FiatMinted(
        address indexed to,
        uint256 amount,
        string  bankReference
    );

    /// @notice Emitted when cFIAT is burned for off-ramp to the physical bank.
    event FiatBurned(
        address indexed from,
        uint256 amount,
        string  bankReference
    );

    /// @notice Emitted when the BankOracle address is rotated.
    event BankOracleUpdated(
        address indexed previousOracle,
        address indexed newOracle
    );

    // ── Errors ────────────────────────────────────────────────────────────────

    error OnlyBankOracle(address caller);
    error OnlyGovernance(address caller);
    error ZeroAddress();
    error ZeroAmount();

    // ── Modifiers ─────────────────────────────────────────────────────────────

    modifier onlyBankOracle() {
        if (msg.sender != bankOracle) revert OnlyBankOracle(msg.sender);
        _;
    }

    modifier onlyGovernance() {
        if (msg.sender != governance) revert OnlyGovernance(msg.sender);
        _;
    }

    // ── Constructor ───────────────────────────────────────────────────────────

    /**
     * @param _name        Token name (e.g. "Cooperative British Pound").
     * @param _symbol      Token symbol (e.g. "cGBP").
     * @param _bankOracle  Initial BankOracle address (the fiat bridge).
     * @param _governance   Safe multi-sig address for governance functions.
     */
    constructor(
        string memory _name,
        string memory _symbol,
        address _bankOracle,
        address _governance
    ) ERC20(_name, _symbol) {
        if (_bankOracle == address(0) || _governance == address(0))
            revert ZeroAddress();
        bankOracle = _bankOracle;
        governance = _governance;
    }

    // ── Mint / Burn ───────────────────────────────────────────────────────────

    /**
     * @notice Mint cFIAT after a confirmed fiat deposit in the cooperative bank.
     *
     * @dev Only callable by the BankOracle. The off-chain bridge verifies
     *      the deposit via Open Banking API before calling this function.
     *      The bankReference links to the real-world bank transaction.
     *
     * @param _to             Recipient address (cooperative Safe or member wallet).
     * @param _amount         Amount to mint (in token's smallest unit, 18 decimals).
     * @param _bankReference  Off-chain bank transaction reference for audit trail.
     */
    function mint(
        address _to,
        uint256 _amount,
        string calldata _bankReference
    ) external onlyBankOracle {
        if (_to == address(0)) revert ZeroAddress();
        if (_amount == 0) revert ZeroAmount();

        _mint(_to, _amount);
        emit FiatMinted(_to, _amount, _bankReference);
    }

    /**
     * @notice Burn cFIAT to initiate an off-ramp to the physical bank account.
     *
     * @dev Only callable by the BankOracle. The off-chain bridge drafts a
     *      pending bank transfer (requiring human approval) before calling this.
     *      Burning without a corresponding bank transfer draft is a protocol
     *      violation logged in the Glass Box audit ledger.
     *
     * @param _from           Address whose tokens are burned (must have approved).
     * @param _amount         Amount to burn.
     * @param _bankReference  Off-chain bank transfer reference for audit trail.
     */
    function burn(
        address _from,
        uint256 _amount,
        string calldata _bankReference
    ) external onlyBankOracle {
        if (_from == address(0)) revert ZeroAddress();
        if (_amount == 0) revert ZeroAmount();

        _burn(_from, _amount);
        emit FiatBurned(_from, _amount, _bankReference);
    }

    // ── Governance ────────────────────────────────────────────────────────────

    /**
     * @notice Update the BankOracle address.
     *
     * @dev Only callable by the governance Safe multi-sig. Used when the
     *      fiat bridge infrastructure is rotated or upgraded.
     */
    function setBankOracle(address _newOracle) external onlyGovernance {
        if (_newOracle == address(0)) revert ZeroAddress();
        address previous = bankOracle;
        bankOracle = _newOracle;
        emit BankOracleUpdated(previous, _newOracle);
    }
}
