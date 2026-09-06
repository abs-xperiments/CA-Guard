"use client";

/**
 * Everything behind one finding, and the decision a reviewer records on it.
 *
 * The order on screen is deliberate and follows `docs/09_UI_UX.md`: **evidence
 * first, AI prose second**. A reviewer should reach their own view from the
 * facts and the source lines before reading anything written for them. The
 * explanation sits below, clearly labelled with who wrote it.
 */

import { useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  Check,
  FileText,
  Loader2,
  Search,
  Sparkles,
  X,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { Decision, Explanation, Finding, ReviewAction } from "@/lib/types";
import { concernLabel, ukDate } from "@/lib/types";
import { BandBadge, Button, EvidenceMeter, Key, StatusLabel, cx } from "./ui";

interface Props {
  engagementId: string;
  finding: Finding;
  reviewer: string;
  onClose: () => void;
  onDecided: (decision: Decision) => void;
}

export function EvidenceDrawer({
  engagementId,
  finding,
  reviewer,
  onClose,
  onDecided,
}: Props) {
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState<ReviewAction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [explanation, setExplanation] = useState<Explanation | null>(null);
  const [explaining, setExplaining] = useState(false);
  const [trail, setTrail] = useState<Decision[]>([]);
  const panel = useRef<HTMLDivElement>(null);

  // Reset when the reviewer moves to a different finding.
  useEffect(() => {
    setNote("");
    setError(null);
    setExplanation(null);
    api.trail(engagementId, finding.voucher_id).then(setTrail).catch(() => setTrail([]));
    panel.current?.focus();
  }, [engagementId, finding.voucher_id]);

  async function decide(action: ReviewAction) {
    setSaving(action);
    setError(null);
    try {
      const decision = await api.decide(engagementId, {
        voucher_id: finding.voucher_id,
        action,
        reviewer,
        note: note.trim() || undefined,
      });
      onDecided(decision);
      setTrail((previous) => [...previous, decision]);
      setNote("");
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "Could not record the decision.",
      );
    } finally {
      setSaving(null);
    }
  }

  async function explain() {
    setExplaining(true);
    setError(null);
    try {
      setExplanation(await api.explanation(engagementId, finding.voucher_id));
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "Could not write an explanation.",
      );
    } finally {
      setExplaining(false);
    }
  }

  const rejectionNeedsReason = note.trim().split(/\s+/).filter(Boolean).length < 3;

  return (
    <aside
      ref={panel}
      tabIndex={-1}
      aria-label={`Finding ${finding.voucher_id}`}
      className="animate-drawer flex h-full w-[42rem] max-w-[46vw] flex-col border-l border-line bg-surface"
    >
      <header className="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-sm text-ink">{finding.voucher_id}</span>
            <BandBadge band={finding.band} />
            <span className="tabular text-xs text-ink-faint">
              priority {finding.priority.toFixed(2)}
            </span>
          </div>
          <p className="tabular mt-1 text-lg font-semibold text-ink">
            {finding.amount_display}
          </p>
          <p className="text-sm text-ink-muted">{ukDate(finding.voucher_date)}</p>
        </div>
        <Button variant="quiet" onClick={onClose} title="Close (Esc)">
          <X size={16} />
        </Button>
      </header>

      <div className="flex-1 space-y-6 overflow-y-auto px-5 py-5">
        {/* 1. Why it was flagged — the machine's reasoning, with its arithmetic. */}
        <Section title="Why this was flagged" count={finding.signals.length}>
          <ul className="space-y-2.5">
            {finding.signals.map((signal) => (
              <li
                key={signal.kind}
                className="rounded-md border border-line bg-canvas/50 px-3 py-2.5"
              >
                <div className="flex items-baseline justify-between gap-3">
                  <span className="text-[13px] font-semibold text-ink">
                    {concernLabel(signal.kind)}
                  </span>
                  <span
                    className="tabular shrink-0 text-[11px] text-ink-faint"
                    title="How much this contributed to the priority"
                  >
                    {(signal.contribution * 100).toFixed(0)}%
                  </span>
                </div>
                <p className="mt-1 text-[13px] leading-relaxed text-ink-muted">
                  {signal.reason}
                </p>
              </li>
            ))}
          </ul>
        </Section>

        {/* 2. Evidence — what can and cannot be produced to support the entry. */}
        <Section title="Evidence trail">
          <div className="rounded-md border border-line px-3 py-3">
            <div className="flex items-center justify-between">
              <EvidenceMeter completeness={finding.evidence.completeness} />
              <span className="text-[13px] text-ink-muted">
                {finding.evidence.summary}
              </span>
            </div>
            <dl className="mt-3 grid grid-cols-3 gap-2 border-t border-line pt-3">
              <Present label="Document" present={finding.evidence.has_document} />
              <Present
                label="Approval"
                present={finding.evidence.has_approval}
                expected={finding.evidence.approval_expected}
              />
              <Present label="Narration" present={finding.evidence.has_narration} />
            </dl>
          </div>
        </Section>

        {/* 3. Provenance — the reviewer must be able to check, not just believe. */}
        <Section title="Source lines">
          <div className="flex flex-wrap gap-1.5">
            {finding.line_ids.map((lineId) => (
              <span
                key={lineId}
                className="rounded bg-canvas px-2 py-1 font-mono text-[11px] text-ink-muted ring-1 ring-inset ring-line"
              >
                {lineId}
              </span>
            ))}
          </div>
        </Section>

        {/* 4. Prose, last and clearly attributed. */}
        <Section title="Plain-language explanation">
          {explanation ? (
            <div className="rounded-md border border-line bg-canvas/50 px-3 py-3">
              <p className="whitespace-pre-line text-[13px] leading-relaxed text-ink">
                {explanation.text}
              </p>
              <p className="mt-3 border-t border-line pt-2 text-[11px] text-ink-faint">
                {explanation.provenance}
                {explanation.latency_seconds > 0
                  ? ` · ${explanation.latency_seconds.toFixed(1)}s`
                  : null}
              </p>
            </div>
          ) : (
            <Button onClick={explain} disabled={explaining}>
              {explaining ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Sparkles size={14} />
              )}
              {explaining ? "Writing…" : "Explain this finding"}
            </Button>
          )}
        </Section>

        {trail.length > 0 ? (
          <Section title="Review history" count={trail.length}>
            <ol className="space-y-1.5">
              {trail.map((entry) => (
                <li key={entry.sequence} className="text-[13px] text-ink-muted">
                  <StatusLabel status={entry.action} />
                  <span className="text-ink-faint">
                    {" "}
                    by {entry.reviewer} ·{" "}
                    {new Date(entry.decided_at).toLocaleString("en-GB", {
                      dateStyle: "short",
                      timeStyle: "short",
                    })}
                  </span>
                  {entry.note ? (
                    <p className="mt-0.5 border-l-2 border-line pl-2 text-ink">
                      {entry.note}
                    </p>
                  ) : null}
                </li>
              ))}
            </ol>
          </Section>
        ) : null}
      </div>

      {/* Decision. Rejecting needs a reason, and the interface says so before
          the reviewer clicks rather than after. */}
      <footer className="border-t border-line bg-canvas/40 px-5 py-4">
        {error ? (
          <p className="mb-3 flex items-start gap-2 rounded-md bg-high-soft px-3 py-2 text-[13px] text-high">
            <AlertTriangle size={14} className="mt-0.5 shrink-0" />
            {error}
          </p>
        ) : null}

        <label className="block">
          <span className="text-[11px] uppercase tracking-wide text-ink-faint">
            Reviewer note
          </span>
          <textarea
            value={note}
            onChange={(event) => setNote(event.target.value)}
            rows={2}
            placeholder="Required when rejecting — what did you check?"
            className="mt-1 w-full resize-none rounded-md border border-line bg-surface px-3 py-2 text-[13px] text-ink placeholder:text-ink-faint focus:border-accent focus:outline-none"
          />
        </label>

        <div className="mt-3 flex items-center gap-2">
          <Button
            variant="primary"
            onClick={() => decide("accept")}
            disabled={saving !== null}
            title="Accept (A)"
          >
            <Check size={14} /> Accept
          </Button>
          <Button
            variant="danger"
            onClick={() => decide("reject")}
            disabled={saving !== null || rejectionNeedsReason}
            title={
              rejectionNeedsReason
                ? "A rejection needs a reason of at least three words"
                : "Reject (R)"
            }
          >
            <X size={14} /> Reject
          </Button>
          <Button
            onClick={() => decide("investigate")}
            disabled={saving !== null}
            title="Investigate (I)"
          >
            <Search size={14} /> Investigate
          </Button>

          <div className="ml-auto flex items-center gap-1 text-[11px] text-ink-faint">
            <Key>A</Key>
            <Key>R</Key>
            <Key>I</Key>
            <span className="ml-1">to decide</span>
          </div>
        </div>

        {rejectionNeedsReason ? (
          <p className="mt-2 flex items-center gap-1.5 text-[11px] text-ink-faint">
            <FileText size={11} />
            Rejecting needs a reason — someone will ask why this was dismissed.
          </p>
        ) : null}
      </footer>
    </aside>
  );
}

function Section({
  title,
  count,
  children,
}: {
  title: string;
  count?: number;
  children: React.ReactNode;
}) {
  return (
    <section>
      <h3 className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-ink-faint">
        {title}
        {count !== undefined ? (
          <span className="rounded-full bg-canvas px-1.5 text-[10px] text-ink-muted ring-1 ring-inset ring-line">
            {count}
          </span>
        ) : null}
      </h3>
      {children}
    </section>
  );
}

function Present({
  label,
  present,
  expected = true,
}: {
  label: string;
  present: boolean;
  expected?: boolean;
}) {
  // An approval that was never required is not a gap. Saying "not required"
  // rather than "missing" is the difference between a useful queue and noise.
  const state = !expected ? "not required" : present ? "present" : "missing";
  return (
    <div>
      <dt className="text-[11px] text-ink-faint">{label}</dt>
      <dd
        className={cx(
          "text-[13px] font-medium",
          state === "present"
            ? "text-rejected"
            : state === "missing"
              ? "text-high"
              : "text-ink-faint",
        )}
      >
        {state}
      </dd>
    </div>
  );
}
