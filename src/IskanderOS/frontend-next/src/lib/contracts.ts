/**
 * contracts.ts — Phase 19: Contract ABIs and Addresses.
 *
 * Provides typed contract references for Wagmi useReadContract/useWriteContract.
 * Addresses are loaded from environment variables (set after deployment).
 */

// ── Contract Addresses (from deployment.json / env vars) ─────────────────────

export const CONTRACT_ADDRESSES = {
  CoopIdentity: process.env.NEXT_PUBLIC_COOP_IDENTITY_ADDRESS || "",
  IskanderEscrow: process.env.NEXT_PUBLIC_ISKANDER_ESCROW_ADDRESS || "",
  ArbitrationRegistry: process.env.NEXT_PUBLIC_ARBITRATION_REGISTRY_ADDRESS || "",
  MACIVoting: process.env.NEXT_PUBLIC_MACI_VOTING_ADDRESS || "",
  InternalPayroll: process.env.NEXT_PUBLIC_INTERNAL_PAYROLL_ADDRESS || "",
} as const;

// ── Minimal ABIs (only the functions we call from the frontend) ──────────────

/**
 * CoopIdentity — ERC-4973 Soulbound Token
 * Used to read member data (DID, role, trust score) from the frontend.
 */
export const COOP_IDENTITY_ABI = [
  {
    inputs: [{ name: "account", type: "address" }],
    name: "memberToken",
    outputs: [{ name: "", type: "uint256" }],
    stateMutability: "view",
    type: "function",
  },
  {
    inputs: [{ name: "tokenId", type: "uint256" }],
    name: "memberRecords",
    outputs: [
      { name: "did", type: "string" },
      { name: "role", type: "string" },
      { name: "trustScore", type: "uint16" },
      { name: "joinedAt", type: "uint256" },
      { name: "active", type: "bool" },
    ],
    stateMutability: "view",
    type: "function",
  },
  {
    inputs: [],
    name: "name",
    outputs: [{ name: "", type: "string" }],
    stateMutability: "view",
    type: "function",
  },
  {
    inputs: [],
    name: "coopName",
    outputs: [{ name: "", type: "string" }],
    stateMutability: "view",
    type: "function",
  },
] as const;

/**
 * IskanderEscrow — Inter-coop escrow
 * Used for reading escrow status from the frontend.
 */
export const ISKANDER_ESCROW_ABI = [
  {
    inputs: [{ name: "escrowId", type: "uint256" }],
    name: "getEscrow",
    outputs: [
      { name: "buyer", type: "address" },
      { name: "seller", type: "address" },
      { name: "token", type: "address" },
      { name: "amount", type: "uint256" },
      { name: "status", type: "uint8" },
    ],
    stateMutability: "view",
    type: "function",
  },
] as const;
