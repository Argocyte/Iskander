/**
 * api.ts — Phase 19: Typed API Client for Iskander Backend.
 *
 * Drop-in replacement for frontend/api_client.py using fetch.
 * Auto-injects JWT Authorization header from auth state.
 */

import type {
  ThreadSummary,
  ThreadDetail,
  CommentResponse,
  ProposalDetail,
  StanceResponse,
  OutcomeResponse,
  TaskResponse,
  SubGroup,
  SubGroupMember,
  ProcessType,
  DecisionType,
} from "../types";

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

// ── Deliberation API ──────────────────────────────────────────────────────

export const deliberation = {
  listThreads: (params?: {
    status?: string; tag?: string; sub_group_id?: string; search?: string
  }) => {
    const cleaned: Record<string, string> = {}
    if (params) {
      for (const [k, v] of Object.entries(params)) {
        if (v !== undefined) cleaned[k] = v
      }
    }
    const q = new URLSearchParams(cleaned).toString()
    return apiFetch<ThreadSummary[]>(`/deliberation/threads${q ? '?' + q : ''}`)
  },

  createThread: (body: {
    title: string; context?: string; author_did: string;
    sub_group_id?: string; tags?: string[]
  }) => apiFetch<ThreadDetail>('/deliberation/threads', {
    method: 'POST', body: JSON.stringify(body),
  }),

  getThread: (threadId: string) =>
    apiFetch<ThreadDetail>(`/deliberation/threads/${threadId}`),

  updateThread: (threadId: string, body: {
    title?: string; context?: string; status?: string; tags?: string[]
  }) => apiFetch<ThreadDetail>(`/deliberation/threads/${threadId}`, {
    method: 'PATCH', body: JSON.stringify(body),
  }),

  addComment: (threadId: string, body: {
    thread_id: string; author_did: string; body: string; parent_id?: string
  }) => apiFetch<CommentResponse>(`/deliberation/threads/${threadId}/comments`, {
    method: 'POST', body: JSON.stringify(body),
  }),

  toggleReaction: (threadId: string, commentId: string, body: {
    member_did: string; emoji: string
  }) => apiFetch<{ action: string; emoji: string }>(
    `/deliberation/threads/${threadId}/comments/${commentId}/react`,
    { method: 'POST', body: JSON.stringify(body) },
  ),

  markSeen: (threadId: string, memberDid: string) =>
    apiFetch<{ status: string }>(
      `/deliberation/threads/${threadId}/seen?member_did=${encodeURIComponent(memberDid)}`,
      { method: 'POST' },
    ),

  createProposal: (threadId: string, body: {
    thread_id: string; title: string; body: string;
    process_type: ProcessType; author_did: string;
    options?: string[]; quorum_pct?: number; closing_at?: string
  }) => apiFetch<ProposalDetail>(
    `/deliberation/threads/${threadId}/proposals`,
    { method: 'POST', body: JSON.stringify(body) },
  ),

  getProposal: (threadId: string, proposalId: string) =>
    apiFetch<ProposalDetail>(
      `/deliberation/threads/${threadId}/proposals/${proposalId}`
    ),

  castStance: (threadId: string, proposalId: string, body: {
    member_did: string; stance: string; reason?: string;
    score?: number; rank_order?: Record<string, unknown>[]
  }) => apiFetch<StanceResponse>(
    `/deliberation/threads/${threadId}/proposals/${proposalId}/stance`,
    { method: 'POST', body: JSON.stringify(body) },
  ),

  stateOutcome: (threadId: string, proposalId: string, body: {
    statement: string; decision_type: DecisionType; stated_by: string
  }) => apiFetch<OutcomeResponse>(
    `/deliberation/threads/${threadId}/proposals/${proposalId}/outcome`,
    { method: 'POST', body: JSON.stringify(body) },
  ),

  createTask: (threadId: string, body: {
    thread_id: string; title: string; created_by: string;
    assignee_did?: string; due_date?: string; outcome_id?: string
  }) => apiFetch<TaskResponse>(
    `/deliberation/threads/${threadId}/tasks`,
    { method: 'POST', body: JSON.stringify(body) },
  ),

  updateTask: (taskId: string, body: {
    done?: boolean; assignee_did?: string; due_date?: string; title?: string
  }) => apiFetch<TaskResponse>(`/deliberation/tasks/${taskId}`, {
    method: 'PATCH', body: JSON.stringify(body),
  }),
}

// ── SubGroups API ─────────────────────────────────────────────────────────

export const subgroups = {
  list: () => apiFetch<SubGroup[]>('/subgroups'),

  create: (body: { slug: string; name: string; created_by: string; description?: string }) =>
    apiFetch<SubGroup>('/subgroups', { method: 'POST', body: JSON.stringify(body) }),

  listMembers: (subgroupId: string) =>
    apiFetch<SubGroupMember[]>(`/subgroups/${subgroupId}/members`),

  addMember: (subgroupId: string, body: { member_did: string; role?: string }) =>
    apiFetch<SubGroupMember>(`/subgroups/${subgroupId}/members`, {
      method: 'POST', body: JSON.stringify(body),
    }),

  removeMember: (subgroupId: string, memberDid: string) =>
    apiFetch<void>(
      `/subgroups/${subgroupId}/members/${encodeURIComponent(memberDid)}`,
      { method: 'DELETE' },
    ),
}

export default { auth, system, governance, treasury, escrow, ipdAudit, deliberation, subgroups };
