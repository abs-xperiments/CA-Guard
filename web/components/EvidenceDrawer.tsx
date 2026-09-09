"use client";

/**
 * Everything behind one finding, and the decision a reviewer records on it.
 *
 * The order on screen follows `docs/09_UI_UX.md`: **evidence first, AI prose
 * second**. A reviewer should reach their own view from the facts and the source
 * lines before reading anything written for them.
 *
 * The decision buttons were the subject of a bug report: pressing Accept
 * recorded the decision and showed the reviewer nothing at all. They now do
 * three things at once — the button itself confirms, a toast appears with an
 * undo, and the queue moves on to the next finding. Undo is honest here rather
 * than cosmetic: the trail is append-only, so undoing writes a further entry
 * instead of erasing one.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  Check,
  FileText,
  Loader2,
  Search,
  Sparkles,
  X,
} from "lucide-react";
import { ApiError, api } from "@/lib/api";
import type { Decision, Explanation, Finding, ReviewAction } from "@/lib/types";
import { concernLabel, ukDate } from "@/lib/types";
import { useToast } from "./Toast";
import { BandBadge, Button, EvidenceMeter, Key, StatusLabel, cx } from "./ui";

const ACTION_WORDS: Record<ReviewAction, string> = {
  accept: "Accepted",
  reject: "Rejected",
  investigate: "Marked for investigation",
  adjust: "Re-banded",
};

interface Props {
  engagementId: string;
  finding: Finding;
  onClose: () => void;
  onDecided: (decision: Decision) => void;
  onAdvance: () => boolean;
}

export function EvidenceDrawer({
  engagementId,
  finding,
  onClose,
  onDecided,
  onAdvance,
}: Props) {
  const toast = useToast();
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState<ReviewAction | null>(null);
  const [justDecided, setJustDecided] = useState<ReviewAction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [explanation, setExplanation] = useState<Explanation | null>(null);
  const [explaining, setExplaining] = useState(false);
  const [trail, setTrail] = useState<Decision[]>([]);
  const panel = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setNote("");
    setError(null);
    setExplanation(null);
    setJustDecided(null);
    api.trail(engagementId, finding.voucher_id).then(setTrail).catch(() => setTrail([]));
    panel.current?.focus();
  }, [engagementId, finding.voucher_id]);

  const decide = useCallback(
    async (action: ReviewAction, reason?: string) => {
      setSaving(action);
      setError(null);
      try {
        const decision = await api.decide(engagementId, {
          voucher_id: finding.voucher_id,
          action,
          note: (reason ?? note).trim() || undefined,
        });

        // 1. The button itself confirms, before anything moves.
        setJustDecided(action);
        onDecided(decision);
        setTrail((previous) => [...previous, decision]);
        setNote("");

        // 2. A toast says what happened and offers a way back. Undo is not a
        //    deletion — it records a further decision, which is what an
        //    append-only trail requires and what an auditor would expect.
        toast.show({
          tone: "success",
          message: `${ACTION_WORDS[action]} ${finding.voucher_id}`,
          detail:
            action === "accept"
              ? "It will appear in the report as an exception to follow up."
              : action === "reject"
                ? "Recorded as reviewed and not a concern."
                : "Kept open for further work.",
          action: {
            label: "Undo",
            onAction: async () => {
              const undone = await api.decide(engagementId, {
                voucher_id: finding.voucher_id,
                action: "investigate",
                note: `Reopened after being ${ACTION_WORDS[action].toLowerCase()}`,
              });
              onDecided(undone);
              setTrail((previous) => [...previous, undone]);
            },
          },
        });

        // 3. Move on. A reviewer working a queue wants the next item, not the
        //    one they have just finished with.
        window.setTimeout(() => {
          if (!onAdvance()) onClose();
        }, 420);
      } catch (caught) {
        setError(
          caught instanceof ApiError
            ? caught.message
            : "Could not record the decision. Nothing was saved.",
        );
        toast.show({
          tone: "error",
          message: "The decision was not saved",
          detail: "Nothing has changed. Try again in a moment.",
        });
      } finally {
        setSaving(null);
      }
    },
    [engagementId, finding.voucher_id, note, onAdvance, onClose, onDecided, toast],
  );

  // Keyboard decisions from inside the drawer, so a reviewer never has to move
  // between the keyboard and the mouse mid-queue.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      if (target && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) return;
      if (event.metaKey || event.ctrlKey || event.altKey) return;

      if (event.key === "a") void decide("accept");
      else if (event.key === "i") void decide("investigate");
      // Reject is not a bare keystroke: it needs a typed reason.
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [decide]);

  const words = note.trim().split(/\s+/).filter(Boolean).length;
  const rejectionNeedsReason = words < 3;

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
            {finding.status !== "not yet reviewed" ? (
              <StatusLabel status={finding.status} />
            ) : null}
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
            <Button
              onClick={async () => {
                setExplaining(true);
                try {
                  setExplanation(
                    await api.explanation(engagementId, finding.voucher_id),
                  );
                } catch {
                  toast.show({
                    tone: "error",
                    message: "Could not write an explanation",
                    detail: "The finding itself is unaffected.",
                  });
                } finally {
                  setExplaining(false);
                }
              }}
              disabled={explaining}
            >
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
              {trail.map((entry, index) => (
                <li
                  key={entry.sequence ?? index}
                  className="text-[13px] text-ink-muted"
                >
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

      <footer className="border-t border-line bg-canvas/40 px-5 py-4">
        {error ? (
          <p
            role="alert"
            className="mb-3 flex items-start gap-2 rounded-md bg-high-soft px-3 py-2 text-[13px] text-high"
          >
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
          <DecisionButton
            action="accept"
            label="Accept"
            icon={<Check size={14} />}
            variant="primary"
            saving={saving}
            justDecided={justDecided}
            onClick={() => decide("accept")}
            shortcut="A"
          />
          <DecisionButton
            action="reject"
            label="Reject"
            icon={<X size={14} />}
            variant="danger"
            saving={saving}
            justDecided={justDecided}
            disabled={rejectionNeedsReason}
            title={
              rejectionNeedsReason
                ? "A rejection needs a reason of at least three words"
                : "Reject"
            }
            onClick={() => decide("reject")}
          />
          <DecisionButton
            action="investigate"
            label="Investigate"
            icon={<Search size={14} />}
            saving={saving}
            justDecided={justDecided}
            onClick={() => decide("investigate")}
            shortcut="I"
          />
        </div>

        {rejectionNeedsReason ? (
          <p className="mt-2 flex items-center gap-1.5 text-[11px] text-ink-faint">
            <FileText size={11} />
            Rejecting needs a reason — someone will ask why this was dismissed.
            {words > 0 ? ` (${words} of 3 words)` : null}
          </p>
        ) : null}
      </footer>
    </aside>
  );
}

/**
 * A decision button that shows its own state.
 *
 * Three states, and the middle one is the one that was missing: idle, saving,
 * and *just done*. Without the third, a reviewer presses Accept and the only
 * evidence anything happened is that the row eventually disappears.
 */
function DecisionButton({
  action,
  label,
  icon,
  variant = "ghost",
  saving,
  justDecided,
  disabled,
  title,
  shortcut,
  onClick,
}: {
  action: ReviewAction;
  label: string;
  icon: React.ReactNode;
  variant?: "primary" | "ghost" | "danger";
  saving: ReviewAction | null;
  justDecided: ReviewAction | null;
  disabled?: boolean;
  title?: string;
  shortcut?: string;
  onClick: () => void;
}) {
  const isSaving = saving === action;
  const isDone = justDecided === action;

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled || saving !== null}
      title={title ?? (shortcut ? `${label} (${shortcut})` : label)}
      className={cx(
        "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium",
        "transition-all duration-200 disabled:cursor-not-allowed disabled:opacity-45",
        isDone
          ? "bg-rejected text-white shadow-sm"
          : variant === "primary"
            ? "bg-accent text-white hover:bg-accent/90 shadow-sm"
            : variant === "danger"
              ? "bg-surface text-high ring-1 ring-inset ring-high/25 hover:bg-high-soft"
              : "bg-surface text-ink ring-1 ring-inset ring-line hover:bg-canvas",
      )}
    >
      {isSaving ? (
        <Loader2 size={14} className="animate-spin" />
      ) : isDone ? (
        <Check size={14} />
      ) : (
        icon
      )}
      {isDone ? "Done" : label}
      {shortcut && !isDone && !isSaving ? (
        <span className="ml-0.5 opacity-60">
          <Key>{shortcut}</Key>
        </span>
      ) : null}
    </button>
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
