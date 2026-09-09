/** Shapes returned by the local CA-Guard API. Mirrors `caguard.api.models`. */

export type RiskBand = "high" | "medium" | "low";

export type ReviewAction = "accept" | "reject" | "investigate" | "adjust";

export interface Signal {
  kind: string;
  reason: string;
  strength: number;
  contribution: number;
  evidence: Record<string, unknown>;
}

export interface Evidence {
  completeness: number;
  missing: string[];
  has_document: boolean;
  has_approval: boolean;
  approval_expected: boolean;
  has_narration: boolean;
  summary: string;
}

export interface Finding {
  voucher_id: string;
  voucher_date: string;
  amount_paise: number;
  amount_display: string;
  priority: number;
  band: RiskBand;
  concerns: string[];
  signals: Signal[];
  evidence: Evidence;
  line_ids: string[];
  status: string;
  reviewer: string | null;
  note: string | null;
}

export interface Engagement {
  id: string;
  name: string;
  entity_id: string;
  fiscal_year: string;
  source_name: string;
  voucher_count: number;
  short_hash: string;
  opened_at: string;
}

export interface User {
  id: string;
  email: string;
  name: string;
  display_name: string;
  is_admin: boolean;
  created_at: string;
}

export interface SignupState {
  state: "bootstrap" | "invite_only";
  needs_invite: boolean;
  explanation: string;
  any_users: boolean;
}

export interface IntakeReport {
  summary: string;
  mapped: Record<string, string>;
  derived: string[];
  not_in_file: string[];
  ignored: string[];
  notes: string[];
  rows_read: number;
  rows_used: number;
}

export interface Queue {
  engagement: Engagement;
  findings: Finding[];
  total_vouchers: number;
  flagged: number;
  bands: Record<string, number>;
  states: Record<string, number>;
  model_available: boolean;
  intake: IntakeReport | null;
}

export interface Decision {
  voucher_id: string;
  action: ReviewAction;
  reviewer: string;
  note: string | null;
  adjusted_band: RiskBand | null;
  decided_at: string;
  sequence: number | null;
}

export interface Explanation {
  voucher_id: string;
  text: string;
  source: "deterministic" | "model";
  provider: string;
  latency_seconds: number;
  provenance: string;
}

/** Turn a signal key into something a reviewer reads without decoding. */
export const CONCERN_LABELS: Record<string, string> = {
  missing_evidence: "No supporting document",
  duplicate_entry: "Possible duplicate",
  period_end_concentration: "Year-end adjustment",
  post_close_entry: "Posted after close",
  rare_account_pair: "Unusual account pairing",
  off_hours_posting: "Entered out of hours",
  round_amount: "Round amount",
  unusual_preparer_account: "Outside preparer's area",
  weekend_posting: "Entered on a Sunday",
  amount_outlier: "Unusual amount for the account",
  threshold_adjacent: "Just below approval limit",
  ml_anomaly: "Statistically unusual",
};

export function concernLabel(kind: string): string {
  return CONCERN_LABELS[kind] ?? kind.replace(/_/g, " ");
}

/** 2025-03-31 → 31-03-2025, the order an Indian reader expects. */
export function ukDate(iso: string): string {
  const parts = iso.split("-");
  return parts.length === 3 ? `${parts[2]}-${parts[1]}-${parts[0]}` : iso;
}
