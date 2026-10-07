"use client";

/**
 * The "Explain this finding" card — what a reviewer reads before anything else.
 *
 * Every word and figure here comes from CA-Guard's own record of the finding:
 * the signals with their working, the evidence in four honest states, the
 * account's ordinary range, similar entries, and review steps. No model wrote
 * any of it, so it is the same with or without one installed, and it is never
 * waiting on anything.
 *
 * The order follows a reviewer's questions: why is this here, what supports
 * it, compared with what, what do I look at next — and, first of all, what
 * this does *not* mean.
 */

import type { ReactNode } from "react";
import {
  Check,
  CircleDashed,
  CircleSlash,
  FileQuestion,
  Info,
  ListChecks,
  X,
} from "lucide-react";
import type {
  CardSignal,
  ComparableEntry,
  EvidenceItem,
  ExplanationCard,
  LedgerLine,
} from "@/lib/types";
import { ukDate } from "@/lib/types";
import { cx } from "./ui";

export function Section({
  title,
  count,
  aside,
  children,
}: {
  title: string;
  count?: number;
  aside?: ReactNode;
  children: ReactNode;
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
        {aside ? <span className="ml-auto font-normal normal-case tracking-normal">{aside}</span> : null}
      </h3>
      {children}
    </section>
  );
}

/** One sentence on why, and — just as prominently — what it does not mean. */
export function CardSummary({ card }: { card: ExplanationCard }) {
  return (
    <div className="space-y-2">
      <p className="text-[14px] leading-relaxed text-ink">{card.summary}</p>
      <p className="flex gap-1.5 text-[12px] leading-relaxed text-ink-muted">
        <Info size={13} className="mt-0.5 shrink-0 text-ink-faint" />
        {card.limitation}
      </p>
    </div>
  );
}

const LEVEL_STYLES: Record<CardSignal["level"], string> = {
  High: "bg-high-soft text-high ring-high/20",
  Medium: "bg-medium-soft text-medium ring-medium/20",
  Low: "bg-low-soft text-low ring-low/20",
};

export function SignalsSection({ card }: { card: ExplanationCard }) {
  const major = card.signals.filter((s) => !s.minor);
  const minor = card.signals.filter((s) => s.minor);
  return (
    <Section title="Why this was flagged" count={major.length || card.signals.length}>
      <ul className="space-y-2.5">
        {(major.length ? major : card.signals).map((signal) => (
          <SignalItem key={signal.kind} signal={signal} />
        ))}
      </ul>

      {minor.length && major.length ? (
        <details className="group mt-2.5 rounded-md border border-dashed border-line px-3 py-2">
          <summary className="cursor-pointer text-[12px] text-ink-muted">
            Also noted, with little weight ({minor.length})
          </summary>
          <ul className="mt-2.5 space-y-2.5">
            {minor.map((signal) => (
              <SignalItem key={signal.kind} signal={signal} />
            ))}
          </ul>
        </details>
      ) : null}

      <details className="mt-2.5 text-[12px] text-ink-muted">
        <summary className="cursor-pointer">How the priority of {card.priority.toFixed(2)} is built</summary>
        <p className="mt-1.5 leading-relaxed">{card.priority_method}</p>
        {card.evidence_uplift > 0 ? (
          <p className="tabular mt-1">
            Lift from missing evidence on this entry: +{card.evidence_uplift.toFixed(3)}
          </p>
        ) : null}
      </details>
    </Section>
  );
}

function SignalItem({ signal }: { signal: CardSignal }) {
  return (
    <li className="rounded-md border border-line bg-canvas/50 px-3 py-2.5">
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-[13px] font-semibold text-ink">{signal.title}</span>
        <span
          className={cx(
            "tabular shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold ring-1 ring-inset",
            LEVEL_STYLES[signal.level],
          )}
          title="This signal's weight × strength. Signals combine as independent reasons, so these do not add up."
        >
          {signal.level} · {signal.contribution.toFixed(2)}
        </span>
      </div>
      <p className="mt-1 text-[13px] leading-relaxed text-ink-muted">{signal.reason}</p>
      {signal.working.length ? (
        <dl className="mt-2 grid grid-cols-[minmax(8rem,auto)_1fr] gap-x-3 gap-y-0.5 border-t border-line/70 pt-2 text-[12px]">
          {signal.working.map((row) => (
            <div key={row.label} className="contents">
              <dt className="text-ink-faint">{row.label}</dt>
              <dd className="tabular text-ink">{row.value}</dd>
            </div>
          ))}
        </dl>
      ) : null}
      {signal.standard ? (
        <p className="mt-1.5 text-[11px] text-ink-faint">Relates to {signal.standard}</p>
      ) : null}
    </li>
  );
}

const EVIDENCE_STATES: Record<
  EvidenceItem["state"],
  { label: string; icon: ReactNode; tone: string }
> = {
  present: { label: "Present", icon: <Check size={14} />, tone: "text-rejected" },
  missing: { label: "Missing", icon: <X size={14} />, tone: "text-high" },
  not_expected: { label: "Not required", icon: <CircleSlash size={14} />, tone: "text-ink-faint" },
  not_in_file: { label: "Not in the file", icon: <FileQuestion size={14} />, tone: "text-medium" },
};

export function EvidenceSection({ card }: { card: ExplanationCard }) {
  return (
    <Section
      title="Evidence"
      aside={
        <span className="tabular text-[12px] text-ink-muted">
          {card.evidence_expected
            ? `${card.evidence_present} of ${card.evidence_expected} expected items present`
            : "nothing that could be checked"}
        </span>
      }
    >
      <ul className="divide-y divide-line rounded-md border border-line">
        {card.evidence.map((item) => {
          const state = EVIDENCE_STATES[item.state];
          return (
            <li key={item.name} className="flex items-start gap-3 px-3 py-2">
              <span className={cx("mt-0.5 shrink-0", state.tone)}>{state.icon}</span>
              <div className="min-w-0 flex-1">
                <div className="flex items-baseline justify-between gap-3">
                  <span className="text-[13px] font-medium text-ink">{item.name}</span>
                  <span className={cx("text-[11px] font-semibold", state.tone)}>{state.label}</span>
                </div>
                <p className="text-[12px] text-ink-muted">{item.detail}</p>
              </div>
            </li>
          );
        })}
      </ul>
    </Section>
  );
}

export function ComparablesSection({
  card,
  onOpen,
}: {
  card: ExplanationCard;
  onOpen?: (voucherId: string) => void;
}) {
  const { profile, similar } = card;
  if (!profile && !similar.length) return null;
  return (
    <Section title="Compared with this ledger">
      {profile ? (
        <p className="text-[12px] leading-relaxed text-ink-muted">
          <span className="font-medium text-ink">
            {profile.account_name || profile.account_code}
          </span>{" "}
          <span className="font-mono text-[11px] text-ink-faint">{profile.account_code}</span> has{" "}
          <span className="tabular">{profile.entries.toLocaleString("en-IN")}</span> entries in
          this ledger. Usual amount <span className="tabular text-ink">{profile.median}</span>;
          typical range <span className="tabular text-ink">{profile.typical_range}</span>.
        </p>
      ) : null}
      {similar.length ? (
        <div className="mt-2 overflow-hidden rounded-md border border-line">
          <table className="w-full text-[12px]">
            <thead className="bg-canvas text-ink-faint">
              <tr>
                <th className="px-3 py-1.5 text-left font-medium">Similar entry</th>
                <th className="px-3 py-1.5 text-right font-medium">Amount</th>
                <th className="px-3 py-1.5 text-left font-medium">Document</th>
                <th className="px-3 py-1.5 text-left font-medium">By</th>
              </tr>
            </thead>
            <tbody>
              {similar.map((entry) => (
                <ComparableRow key={entry.voucher_id} entry={entry} onOpen={onOpen} />
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      <p className="mt-1.5 text-[11px] text-ink-faint">
        From this uploaded ledger only — not prior years.
      </p>
    </Section>
  );
}

function ComparableRow({
  entry,
  onOpen,
}: {
  entry: ComparableEntry;
  onOpen?: (voucherId: string) => void;
}) {
  const openable = entry.is_flagged && onOpen;
  return (
    <tr className="border-t border-line align-top">
      <td className="px-3 py-1.5">
        <div className="flex items-center gap-1.5">
          {openable ? (
            <button
              type="button"
              onClick={() => onOpen(entry.voucher_id)}
              className="font-mono text-accent hover:underline"
              title="Open this finding"
            >
              {entry.voucher_id}
            </button>
          ) : (
            <span className="font-mono text-ink">{entry.voucher_id}</span>
          )}
          <span className="text-ink-faint">{entry.voucher_date}</span>
          {entry.is_flagged ? (
            <span className="rounded bg-high-soft px-1 text-[10px] font-semibold text-high">
              flagged
            </span>
          ) : null}
        </div>
        {entry.narration ? (
          <p className="truncate text-[11px] text-ink-muted" title={entry.narration}>
            {entry.narration}
          </p>
        ) : null}
      </td>
      <td className="tabular px-3 py-1.5 text-right text-ink">{entry.amount_display}</td>
      <td className={cx("px-3 py-1.5", entry.has_document ? "text-rejected" : "text-high")}>
        {entry.has_document ? "Yes" : "No"}
      </td>
      <td className="px-3 py-1.5 text-ink-muted">{entry.created_by ?? "—"}</td>
    </tr>
  );
}

export function NextStepsSection({ card }: { card: ExplanationCard }) {
  return (
    <Section title="Suggested review steps">
      <ol className="space-y-1.5">
        {card.next_steps.map((step, index) => (
          <li key={step} className="flex gap-2 text-[13px] leading-relaxed text-ink">
            <span className="tabular mt-px flex size-5 shrink-0 items-center justify-center rounded-full bg-canvas text-[11px] text-ink-muted ring-1 ring-inset ring-line">
              {index + 1}
            </span>
            {step}
          </li>
        ))}
      </ol>
      <p className="mt-1.5 flex items-center gap-1 text-[11px] text-ink-faint">
        <ListChecks size={12} /> Procedures to consider, not conclusions.
      </p>
    </Section>
  );
}

/** While the full card loads: the queue's own view of the signals, so nothing is blank. */
export function CardPlaceholder() {
  return (
    <p className="flex items-center gap-1.5 text-[12px] text-ink-faint">
      <CircleDashed size={13} className="animate-pulse-soft" /> Loading the working…
    </p>
  );
}

/** The voucher's lines as a reviewer reads a journal: account, debit, credit, narration. */
export function Transaction({ lines }: { lines: LedgerLine[] }) {
  const narrations = Array.from(
    new Set(lines.map((line) => line.narration).filter((n): n is string => Boolean(n))),
  );
  const references = Array.from(
    new Set(lines.map((line) => line.document_ref).filter((r): r is string => Boolean(r))),
  );
  const first = lines[0];
  return (
    <div className="overflow-hidden rounded-md border border-line">
      <table className="w-full text-[12px]">
        <thead className="bg-canvas text-ink-faint">
          <tr>
            <th className="px-3 py-1.5 text-left font-medium">Account</th>
            <th className="px-3 py-1.5 text-right font-medium">Debit</th>
            <th className="px-3 py-1.5 text-right font-medium">Credit</th>
            <th className="px-3 py-1.5 text-right font-medium" title="Row in the uploaded file">
              Row
            </th>
          </tr>
        </thead>
        <tbody>
          {lines.map((line) => (
            <tr key={line.line_id} className="border-t border-line">
              <td className="px-3 py-1.5">
                <span className="text-ink">{line.account_name || "—"}</span>
                <span className="ml-1.5 font-mono text-[11px] text-ink-faint">
                  {line.account_code}
                </span>
              </td>
              <td className="tabular px-3 py-1.5 text-right text-ink">{line.debit_display}</td>
              <td className="tabular px-3 py-1.5 text-right text-ink">{line.credit_display}</td>
              <td className="tabular px-3 py-1.5 text-right text-ink-faint">
                {line.source_row?.toLocaleString("en-IN") ?? "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <dl className="grid grid-cols-[7rem_1fr] gap-x-3 gap-y-1 border-t border-line bg-canvas/40 px-3 py-2.5 text-[12px]">
        <dt className="text-ink-faint">Narration</dt>
        <dd className="text-ink">
          {narrations.length ? narrations.join(" · ") : <Absent>none recorded</Absent>}
        </dd>
        <dt className="text-ink-faint">Document ref.</dt>
        <dd className="text-ink">
          {references.length ? references.join(", ") : <Absent>none recorded</Absent>}
        </dd>
        <dt className="text-ink-faint">Prepared by</dt>
        <dd className="text-ink">{first?.created_by ?? <Absent>not recorded</Absent>}</dd>
        <dt className="text-ink-faint">Approved by</dt>
        <dd className="text-ink">{first?.approved_by ?? <Absent>not recorded</Absent>}</dd>
        {first?.posted_at ? (
          <>
            <dt className="text-ink-faint">Entered</dt>
            <dd className="tabular text-ink">
              {ukDate(first.posted_at.slice(0, 10))} {first.posted_at.slice(11, 16)}
            </dd>
          </>
        ) : null}
        {first?.voucher_type ? (
          <>
            <dt className="text-ink-faint">Voucher type</dt>
            <dd className="text-ink">{first.voucher_type.replace(/_/g, " ")}</dd>
          </>
        ) : null}
      </dl>
    </div>
  );
}

function Absent({ children }: { children: string }) {
  return <span className="text-ink-faint italic">{children}</span>;
}

/** " · rows 1,842–1,843" — where in the file this voucher sits. */
export function sourceRows(lines: LedgerLine[]): string {
  const rows = lines.map((line) => line.source_row).filter((r): r is number => r !== null);
  if (!rows.length) return "";
  const low = Math.min(...rows);
  const high = Math.max(...rows);
  const fmt = (n: number) => n.toLocaleString("en-IN");
  return low === high ? ` · row ${fmt(low)}` : ` · rows ${fmt(low)}–${fmt(high)}`;
}
