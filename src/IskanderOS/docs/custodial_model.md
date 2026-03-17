# Custodial Treasury Model — Phase 19

## Overview

The Iskander cooperative operates a custodial treasury model that bridges
fiat (off-chain) and crypto (on-chain) economies. This enables meatspace
cooperatives — bakeries, care collectives, worker co-ops — to participate
in the Iskander network without requiring every member to hold a crypto
wallet or interact directly with the blockchain.

## How It Works

### On-Chain Layer
- The cooperative's **Gnosis Safe multi-sig** holds pooled xDAI + ERC-20 tokens.
- All high-value on-chain transactions require steward multi-sig signatures (HITL gate).
- Smart contracts (CoopIdentity, IskanderEscrow, GovernanceModule) execute on Gnosis Chain.

### Internal Credit Layer
- Off-chain members hold **internal credits** — accounting units denominated in the same
  unit as the on-chain token (xDAI equivalent).
- Credits are tracked in the `credit_accounts` and `credit_transactions` PostgreSQL tables.
- The cooperative is the legal custodian of the pooled funds.

### Fiat Bridge
- Stewards process fiat deposits (bank transfer, cash, check) and credit the member's
  internal account via `POST /credits/deposit`.
- Every fiat deposit is logged in the `fiat_deposits` table with payment method,
  reference ID, and confirmation status for regulatory audit trail.

## Credit-to-Chain Conversion

When an off-chain member needs to participate in on-chain actions (e.g., escrow creation,
governance voting), the following flow applies:

1. Member requests conversion via `POST /credits/convert-to-chain`.
2. Credits are debited from the member's internal account.
3. The backend creates a pending Safe transaction to transfer equivalent tokens.
4. Steward multi-sig signs the transaction (HITL gate for amounts above threshold).
5. On-chain transaction metadata references the member's DID (not their non-existent wallet).

## Legal Framework

- The cooperative acts as **custodian** under its legal wrapper (Ricardian contract stored
  on IPFS, referenced by `CoopIdentity.legalWrapperCID`).
- Internal credits are **accounting units**, not securities. They represent the member's
  share of the cooperative's pooled treasury, governed by the cooperative's bylaws.
- The Ricardian contract (Phase 17) includes a **NY Convention arbitration clause**
  ensuring disputes are enforceable across jurisdictions.
- Tax obligations remain with individual members. The cooperative provides transaction
  records via `GET /credits/ledger/{did}` for reporting purposes.

## Anti-Wealth-Bias Guarantee

This model ensures ICA Principle 1 (Voluntary and Open Membership) is upheld:

- **No wallet required**: Members interact via credits, not crypto.
- **No on-chain presence required**: The Phase 18 IPD audit system weights meatspace
  peer attestations when on-chain signals are unavailable (weight redistribution).
- **Equal access**: A bakery with excellent peer attestations scores equally against
  a DAO with full on-chain history in cooperation probability predictions.

## Regulatory Considerations

- The cooperative must comply with local money transmission regulations.
- KYC/AML may be required depending on jurisdiction — the steward-assisted model
  centralizes this responsibility with the cooperative, not individual members.
- Fiat deposit records include payment method, currency, and reference IDs for
  audit compliance.
