/**
 * Shared TypeScript types matching backend Pydantic schemas.
 */

// ── Auth ─────────────────────────────────────────────────────────────────────

export interface UserProfile {
  address: string;
  did: string | null;
  role: "steward" | "worker-owner" | "associate" | "guest";
  member_token_id: number | null;
  trust_score: number;
  is_member: boolean;
  is_smart_contract: boolean;
  chain_id: number;
}

// ── Governance ───────────────────────────────────────────────────────────────

export interface ProposalResponse {
  thread_id: string;
  status: string;
  safe_tx_draft: Record<string, unknown> | null;
  action_log: Record<string, unknown>[];
}

// ── Escrow ───────────────────────────────────────────────────────────────────

export interface EscrowData {
  escrow_id: string;
  buyer_coop: string;
  seller_coop: string;
  token_address: string;
  amount_wei: number;
  status: "Active" | "Released" | "Disputed";
}

// ── IPD Audit ────────────────────────────────────────────────────────────────

export interface PredictionResponse {
  partner_did: string;
  cooperation_probability: number;
  recommended_strategy: "cooperate" | "defect";
  strategy_rationale: string;
  payoff_matrix: {
    R: number;
    S: number;
    T: number;
    P: number;
  };
  expected_values: {
    EV_cooperate: number;
    EV_defect: number;
  };
  forgiveness_rate: number;
  requires_human_review: boolean;
  is_meatspace: boolean;
}

export interface ReputationProfile {
  node_did: string;
  total_interactions: number;
  cooperate_count: number;
  defect_count: number;
  cooperation_ratio: number;
  jury_participation_rate: number;
  audit_compliance_rate: number;
  is_meatspace: boolean;
  peer_attestation_avg: number;
}

// ── Credits ──────────────────────────────────────────────────────────────────

export interface CreditAccount {
  member_did: string;
  balance: number;
  is_on_chain: boolean;
  linked_address: string | null;
}

// ── WebSocket Events ─────────────────────────────────────────────────────────

export interface AgentEvent {
  task_id: string | null;
  agent_id: string | null;
  event:
    | "queued"
    | "running"
    | "node_entered"
    | "node_exited"
    | "hitl_required"
    | "task_complete"
    | "error"
    | "queue_rejected";
  node: string | null;
  timestamp: string;
  payload: Record<string, unknown>;
}
