/**
 * api.ts — Phase 19: Typed API Client for Iskander Backend.
 *
 * Drop-in replacement for frontend/api_client.py using fetch.
 * Auto-injects JWT Authorization header from auth state.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

let accessToken: string | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

/**
 * Generic fetch wrapper with JWT injection and error handling.
 */
async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (accessToken) {
    headers["Authorization"] = `Bearer ${accessToken}`;
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new ApiError(
      response.status,
      errorBody.detail || response.statusText,
      errorBody
    );
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public body?: unknown
  ) {
    super(message);
    this.name = "ApiError";
  }
}

// ── Auth Endpoints ───────────────────────────────────────────────────────────

export const auth = {
  getNonce: () => apiFetch<{ nonce: string }>("/auth/nonce", { method: "POST" }),

  login: (message: string, signature: string) =>
    apiFetch<{
      access_token: string;
      refresh_token: string;
      token_type: string;
      expires_in: number;
      user: {
        address: string;
        did: string | null;
        role: string;
        member_token_id: number | null;
        trust_score: number;
        is_member: boolean;
        is_smart_contract: boolean;
        chain_id: number;
      };
    }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ message, signature }),
    }),

  refresh: (refreshToken: string) =>
    apiFetch<{ access_token: string; token_type: string; expires_in: number }>(
      "/auth/refresh",
      {
        method: "POST",
        body: JSON.stringify({ refresh_token: refreshToken }),
      }
    ),

  logout: (refreshToken: string) =>
    apiFetch<void>("/auth/logout", {
      method: "POST",
      body: JSON.stringify({ refresh_token: refreshToken }),
    }),
};

// ── Health ───────────────────────────────────────────────────────────────────

export const system = {
  health: () =>
    apiFetch<{
      status: string;
      node: string;
      evm_chain_id: number;
      llm_model: string;
      queue_depth: number;
      ws_connections: number;
    }>("/health"),
};

// ── Governance ───────────────────────────────────────────────────────────────

export const governance = {
  propose: (data: {
    description: string;
    to?: string;
    value_wei?: number;
    data?: string;
    nonce?: number;
    proposed_by: string;
  }) =>
    apiFetch<{
      thread_id: string;
      status: string;
      safe_tx_draft: Record<string, unknown> | null;
      action_log: Record<string, unknown>[];
    }>("/governance/propose", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  getProposal: (threadId: string) =>
    apiFetch<{
      thread_id: string;
      status: string;
      safe_tx_draft: Record<string, unknown> | null;
      action_log: Record<string, unknown>[];
    }>(`/governance/proposals/${threadId}`),

  vote: (data: {
    thread_id: string;
    approved: boolean;
    rejection_reason?: string;
    voter_did: string;
  }) =>
    apiFetch<{
      thread_id: string;
      status: string;
      safe_tx_draft: Record<string, unknown> | null;
      action_log: Record<string, unknown>[];
    }>("/governance/vote", {
      method: "POST",
      body: JSON.stringify(data),
    }),
};

// ── Treasury ─────────────────────────────────────────────────────────────────

export const treasury = {
  submitPayment: (data: Record<string, unknown>) =>
    apiFetch("/treasury/payment", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  approvePayment: (data: { thread_id: string; approved: boolean; reason?: string }) =>
    apiFetch("/treasury/approve", {
      method: "POST",
      body: JSON.stringify(data),
    }),
};

// ── Escrow ───────────────────────────────────────────────────────────────────

export const escrow = {
  create: (data: Record<string, unknown>) =>
    apiFetch("/escrow/create", { method: "POST", body: JSON.stringify(data) }),

  get: (escrowId: string) => apiFetch(`/escrow/${escrowId}`),

  release: (escrowId: string) =>
    apiFetch(`/escrow/${escrowId}/release`, { method: "POST" }),

  dispute: (escrowId: string, description: string) =>
    apiFetch(`/escrow/${escrowId}/dispute`, {
      method: "POST",
      body: JSON.stringify({ description }),
    }),
};

// ── IPD Audit ────────────────────────────────────────────────────────────────

export const ipdAudit = {
  predict: (partnerDid: string, isMeatspace?: boolean) =>
    apiFetch("/ipd-audit/predict", {
      method: "POST",
      body: JSON.stringify({ partner_did: partnerDid, is_meatspace: isMeatspace }),
    }),

  reputation: (nodeDid: string) => apiFetch(`/ipd-audit/reputation/${nodeDid}`),

  pairwise: (nodeA: string, nodeB: string) =>
    apiFetch(`/ipd-audit/pairwise?node_a=${nodeA}&node_b=${nodeB}`),
};

export default { auth, system, governance, treasury, escrow, ipdAudit };
