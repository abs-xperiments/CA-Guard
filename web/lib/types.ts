/** Shapes returned by the local CA-Guard API. Mirrors `caguard.api.models`. */

export type RiskBand = "high" | "medium" | "low";

export type ReviewAction = "accept" | "reject" | "investigate" | "adjust";

/**
 * What each decision is called on screen (D-055). The stored values are
 * unchanged; only the words are. "Accept" read to an accountant as "the entry
 * is fine" — the opposite of what it meant — so the label now says what the
 * reviewer concluded.
 */
export const DECISION_LABELS: Record<ReviewAction, { button: string; status: string; done: string }> = {
  accept: {
    button: "Exception — follow up",
    status: "Exception",
    done: "Recorded as an exception to follow up",
  },
  reject: {
    button: "Cleared — not a concern",
    status: "Cleared",
    done: "Recorded as cleared",
  },
  investigate: { button: "Investigate", status: "Investigating", done: "Marked for investigation" },
  adjust: { button: "Re-band", status: "Re-banded", done: "Re-banded" },
};

export interface Signal {
  kind: string;
  reason: string;
  strength: number;
  contribution: number;
  level: "High" | "Medium" | "Low";
  /** Below the display floor: "also noted", not a headline reason. */
  minor: boolean;
  evidence: Record<string, unknown>;
}

/** The structured explanation. Built by CA-Guard from recorded facts; no model involved. */
export interface ExplanationCard {
  summary: string;
  limitation: string;
  priority: number;
  priority_method: string;
  evidence_uplift: number;
  signals: CardSignal[];
  evidence: EvidenceItem[];
  evidence_present: number;
  evidence_expected: number;
  profile: AccountProfile | null;
  similar: ComparableEntry[];
  next_steps: string[];
}

export interface CardSignal {
  kind: string;
  title: string;
  reason: string;
  contribution: number;
  level: "High" | "Medium" | "Low";
  minor: boolean;
  working: { label: string; value: string }[];
  standard: string | null;
}

export interface EvidenceItem {
  name: string;
  state: "present" | "missing" | "not_expected" | "not_in_file";
  detail: string;
}

export interface AccountProfile {
  account_code: string;
  account_name: string;
  entries: number;
  median: string;
  typical_range: string;
}

export interface ComparableEntry {
  voucher_id: string;
  voucher_date: string;
  amount_display: string;
  has_document: boolean;
  narration: string | null;
  created_by: string | null;
  is_flagged: boolean;
  basis: string;
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
  /** The transaction itself. Present on a single finding, empty in the queue. */
  lines: LedgerLine[];
  source: SourceRef | null;
  /** The structured explanation. Present on a single finding only. */
  card: ExplanationCard | null;
  /** For searching the queue. */
  accounts: string[];
  narration: string | null;
  prepared_by: string | null;
}

/** One ledger line behind a finding, and where it sits in the uploaded file. */
export interface LedgerLine {
  line_id: string;
  line_number: number | null;
  account_code: string;
  account_name: string;
  debit_paise: number;
  credit_paise: number;
  debit_display: string;
  credit_display: string;
  narration: string | null;
  document_ref: string | null;
  voucher_type: string | null;
  cost_centre: string | null;
  created_by: string | null;
  approved_by: string | null;
  posted_at: string | null;
  /** Row in the original file, numbered as a spreadsheet shows it (header = 1). */
  source_row: number | null;
}

export interface SourceRef {
  id: string;
  filename: string;
}

/** An uploaded file, exactly as it was received. */
export interface SourceFile {
  id: string;
  engagement_id: string;
  filename: string;
  file_type: string;
  size_bytes: number;
  sha256: string;
  uploaded_at: string;
  uploaded_by: string;
  rows_read: number;
  rows_used: number;
  available: boolean;
  deleted_at: string | null;
  deleted_by: string | null;
}

export interface SourcePreview {
  source_id: string;
  filename: string;
  columns: string[];
  rows: { row: number; values: (string | null)[] }[];
  total_rows: number;
  offset: number;
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

/** A dashboard row: the engagement and how far its review has got. */
export interface EngagementSummary {
  engagement: Engagement;
  /** Null until the ledger has been analysed under this version. */
  flagged: number | null;
  high: number | null;
  medium: number | null;
  reviewed: number;
  last_activity: string;
  latest_file: string | null;
}

/** A background analysis, as the upload screen follows it. */
export interface UploadJob {
  id: string;
  state: "queued" | "running" | "done" | "failed";
  stage: string | null;
  stages: { key: string; label: string; state: "done" | "current" | "pending" }[];
  engagement_id: string | null;
  error: string | null;
  elapsed_seconds: number;
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

/** 1536 → "1.5 KB". Sizes a reviewer can compare at a glance. */
export function fileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

/** An ISO timestamp as an Indian reader writes it: 07-10-2026, 21:40. */
export function whenIST(iso: string): string {
  return new Date(iso).toLocaleString("en-IN", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "Asia/Kolkata",
  });
}

/** 2025-03-31 → 31-03-2025, the order an Indian reader expects. */
export function ukDate(iso: string): string {
  const parts = iso.split("-");
  return parts.length === 3 ? `${parts[2]}-${parts[1]}-${parts[0]}` : iso;
}
