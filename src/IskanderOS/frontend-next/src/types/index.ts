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

// ── Deliberation (Native Loomio) ──────────────────────────────────────────

export type ProcessType =
  | 'sense_check' | 'advice' | 'consent' | 'consensus'
  | 'choose' | 'score' | 'allocate' | 'rank' | 'time_poll'

export type StanceOption = 'agree' | 'abstain' | 'disagree' | 'block'
export type ThreadStatus  = 'open' | 'closed' | 'pinned'
export type ProposalStatus = 'open' | 'closed' | 'withdrawn'
export type DecisionType  = 'passed' | 'rejected' | 'withdrawn' | 'no_quorum'

export interface SubGroup {
  id: string
  slug: string
  name: string
  description: string | null
  created_by: string
  created_at: string
}

export interface SubGroupMember {
  sub_group_id: string
  member_did: string
  role: 'member' | 'coordinator'
  joined_at: string
}

export interface ThreadSummary {
  id: string
  title: string
  author_did: string
  status: ThreadStatus
  tags: string[]
  sub_group_id: string | null
  open_proposal_count: number
  comment_count: number
  last_activity: string
}

export interface CommentResponse {
  id: string
  thread_id: string
  author_did: string
  parent_id: string | null
  body: string
  edited_at: string | null
  created_at: string
  reactions: Record<string, number>
}

export interface ProposalTally {
  agree: number
  abstain: number
  disagree: number
  block: number
  total: number
  options: Record<string, number>
}

export interface StanceResponse {
  id: string
  proposal_id: string
  member_did: string
  stance: string
  reason: string | null
  score: number | null
  rank_order: Record<string, unknown>[] | null
  created_at: string
  updated_at: string
}

export interface OutcomeResponse {
  id: string
  proposal_id: string
  statement: string
  decision_type: DecisionType
  precedent_id: string | null
  ai_draft: string | null
  stated_by: string
  created_at: string
}

export interface ProposalSummary {
  id: string
  title: string
  process_type: ProcessType
  status: ProposalStatus
  closing_at: string | null
  stance_count: number
}

export interface ProposalDetail extends ProposalSummary {
  thread_id: string
  body: string
  options: string[] | null
  quorum_pct: number
  ai_draft: string | null
  author_did: string
  created_at: string
  closed_at: string | null
  stances: StanceResponse[]
  tally: ProposalTally | null
  outcome: OutcomeResponse | null
}

export interface ThreadDetail {
  id: string
  title: string
  context: string
  author_did: string
  sub_group_id: string | null
  tags: string[]
  status: ThreadStatus
  ai_context_draft: string | null
  created_at: string
  updated_at: string
  comments: CommentResponse[]
  proposals: ProposalSummary[]
  tasks: TaskResponse[]
}

export interface TaskResponse {
  id: string
  thread_id: string
  outcome_id: string | null
  title: string
  assignee_did: string | null
  due_date: string | null
  done: boolean
  done_at: string | null
  created_by: string
  created_at: string
}

// WebSocket deliberation events (extends existing AgentEvent)
export type DeliberationEvent =
  | 'thread_created'
  | 'comment_added'
  | 'proposal_opened'
  | 'stance_cast'
  | 'proposal_closed'
  | 'outcome_stated'
  | 'task_assigned'
  | 'member_nudge'
