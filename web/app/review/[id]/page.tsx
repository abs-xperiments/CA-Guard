"use client";

/**
 * The review workspace.
 *
 * A ranked queue on the left, the evidence behind the selected finding on the
 * right. Fully keyboard-driven, because a CA working through a hundred findings
 * should never have to reach for the mouse: j/k to move, Enter to open, a/r/i
 * to decide, Esc to close.
 */

import { use, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Download, Inbox, ShieldCheck } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { Decision, Finding, Queue, RiskBand } from "@/lib/types";
import { concernLabel } from "@/lib/types";
import { EvidenceDrawer } from "@/components/EvidenceDrawer";
import { FindingsTable } from "@/components/FindingsTable";
import { IntakeNotice } from "@/components/IntakeNotice";
import { Button, EmptyState, ErrorState, Key, Spinner, Stat, cx } from "@/components/ui";

type BandFilter = RiskBand | "all";
type StatusFilter = "all" | "open" | "reviewed";

export default function ReviewPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);

  const [queue, setQueue] = useState<Queue | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [cursor, setCursor] = useState(0);
  const [band, setBand] = useState<BandFilter>("all");
  const [status, setStatus] = useState<StatusFilter>("open");
  const [reviewer, setReviewer] = useState("reviewer");

  const load = useCallback(async () => {
    setError(null);
    try {
      setQueue(await api.queue(id));
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not load the review.");
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const saved = window.localStorage.getItem("ca-guard-reviewer");
    if (saved) setReviewer(saved);
  }, []);

  const visible = useMemo(() => {
    if (!queue) return [];
    return queue.findings.filter((finding) => {
      if (band !== "all" && finding.band !== band) return false;
      const open = finding.status === "not yet reviewed";
      if (status === "open" && !open) return false;
      if (status === "reviewed" && open) return false;
      return true;
    });
  }, [queue, band, status]);

  const reviewed = useMemo(
    () =>
      queue
        ? queue.findings.filter((f) => f.status !== "not yet reviewed").length
        : 0,
    [queue],
  );

  const current = visible[cursor] ?? null;
  const openFinding = selected
    ? (queue?.findings.find((f) => f.voucher_id === selected) ?? null)
    : null;

  // Keep the cursor inside the list when filters change under it.
  useEffect(() => {
    setCursor((previous) => Math.min(previous, Math.max(visible.length - 1, 0)));
  }, [visible.length]);

  const applyDecision = useCallback((decision: Decision) => {
    setQueue((previous) =>
      previous
        ? {
            ...previous,
            findings: previous.findings.map((finding) =>
              finding.voucher_id === decision.voucher_id
                ? {
                    ...finding,
                    status: decision.action,
                    reviewer: decision.reviewer,
                    note: decision.note,
                  }
                : finding,
            ),
          }
        : previous,
    );
  }, []);

  // Keyboard navigation. Ignored while typing, so a note can contain "a".
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      if (target && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) return;

      if (event.key === "Escape") {
        setSelected(null);
        return;
      }
      if (event.key === "j" || event.key === "ArrowDown") {
        event.preventDefault();
        setCursor((c) => Math.min(c + 1, Math.max(visible.length - 1, 0)));
      } else if (event.key === "k" || event.key === "ArrowUp") {
        event.preventDefault();
        setCursor((c) => Math.max(c - 1, 0));
      } else if (event.key === "Enter" && current) {
        setSelected(current.voucher_id);
      } else if (["a", "i"].includes(event.key) && current) {
        // Reject is deliberately not a bare keystroke: it needs a reason, and
        // the reason belongs in the drawer where the reviewer can type it.
        void api
          .decide(id, {
            voucher_id: current.voucher_id,
            action: event.key === "a" ? "accept" : "investigate",
            reviewer,
          })
          .then(applyDecision)
          .catch(() => undefined);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [visible.length, current, id, reviewer, applyDecision]);

  if (error) {
    return (
      <main className="mx-auto max-w-2xl px-6 py-16">
        <ErrorState message={error} retry={() => void load()} />
        <div className="mt-4">
          <Link href="/" className="text-sm text-accent hover:underline">
            ← Back to reviews
          </Link>
        </div>
      </main>
    );
  }

  if (!queue) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <Spinner label="Loading the review queue…" />
      </main>
    );
  }

  const progress = queue.flagged ? reviewed / queue.flagged : 0;

  return (
    <div className="flex h-screen flex-col">
      <header className="shrink-0 border-b border-line bg-surface px-5 py-3">
        <div className="flex items-center gap-4">
          <Link
            href="/"
            className="flex items-center gap-1.5 text-sm text-ink-muted transition-colors hover:text-ink"
          >
            <ArrowLeft size={15} />
            <ShieldCheck size={16} className="text-accent" />
          </Link>

          <div className="min-w-0">
            <h1 className="truncate text-sm font-semibold text-ink">
              {queue.engagement.name}
            </h1>
            <p className="truncate text-[12px] text-ink-muted">
              {queue.engagement.source_name} ·{" "}
              {queue.total_vouchers.toLocaleString("en-IN")} vouchers ·{" "}
              <span className="font-mono">{queue.engagement.short_hash}</span>
            </p>
          </div>

          <dl className="ml-auto flex items-center gap-6">
            <Stat label="Flagged" value={queue.flagged} />
            <Stat label="High" value={queue.bands.high ?? 0} tone="text-high" />
            <Stat label="Medium" value={queue.bands.medium ?? 0} tone="text-medium" />
            <Stat
              label="Reviewed"
              value={`${reviewed} of ${queue.flagged}`}
              tone="text-ink"
            />
          </dl>

          <a href={api.reportUrl(id, "html")} target="_blank" rel="noreferrer">
            <Button title="Open the review report">
              <Download size={14} /> Report
            </Button>
          </a>
        </div>

        <div className="mt-2.5 h-1 overflow-hidden rounded-full bg-line">
          <div
            className="h-full rounded-full bg-accent transition-[width] duration-500"
            style={{ width: `${Math.round(progress * 100)}%` }}
          />
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        <section className="flex min-w-0 flex-1 flex-col">
          <div className="flex shrink-0 flex-wrap items-center gap-2 border-b border-line bg-surface/60 px-5 py-2.5">
            <Filters
              label="Risk"
              value={band}
              options={[
                ["all", "All"],
                ["high", "High"],
                ["medium", "Medium"],
                ["low", "Low"],
              ]}
              onChange={(value) => setBand(value as BandFilter)}
            />
            <Filters
              label="Status"
              value={status}
              options={[
                ["open", "Not reviewed"],
                ["reviewed", "Reviewed"],
                ["all", "All"],
              ]}
              onChange={(value) => setStatus(value as StatusFilter)}
            />

            <label className="ml-auto flex items-center gap-2 text-[12px] text-ink-muted">
              Reviewer
              <input
                value={reviewer}
                onChange={(event) => {
                  setReviewer(event.target.value);
                  window.localStorage.setItem("ca-guard-reviewer", event.target.value);
                }}
                className="w-28 rounded border border-line bg-surface px-2 py-1 text-[13px] text-ink focus:border-accent focus:outline-none"
              />
            </label>

            <div className="flex items-center gap-1 text-[11px] text-ink-faint">
              <Key>j</Key>
              <Key>k</Key>
              <span>move</span>
              <Key>↵</Key>
              <span>open</span>
            </div>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
            {queue.intake ? <IntakeNotice intake={queue.intake} /> : null}
            {visible.length === 0 ? (
              <EmptyState
                icon={<Inbox size={22} />}
                title={
                  status === "open"
                    ? "Nothing left to review"
                    : "No findings match these filters"
                }
                detail={
                  status === "open"
                    ? `Every one of the ${queue.flagged} findings has a recorded decision. Open the report to see them together.`
                    : "Widen the risk or status filter to see more."
                }
              />
            ) : (
              <FindingsTable
                findings={visible}
                selected={selected}
                cursor={cursor}
                onSelect={setSelected}
                onCursorChange={setCursor}
              />
            )}
          </div>
        </section>

        {openFinding ? (
          <EvidenceDrawer
            engagementId={id}
            finding={openFinding}
            reviewer={reviewer}
            onClose={() => setSelected(null)}
            onDecided={applyDecision}
          />
        ) : null}
      </div>
    </div>
  );
}

function Filters({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: Array<[string, string]>;
  onChange: (value: string) => void;
}) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-[11px] uppercase tracking-wide text-ink-faint">{label}</span>
      <div className="flex overflow-hidden rounded-md ring-1 ring-inset ring-line">
        {options.map(([key, text]) => (
          <button
            key={key}
            onClick={() => onChange(key)}
            className={cx(
              "px-2.5 py-1 text-[12px] font-medium transition-colors",
              value === key
                ? "bg-accent text-white"
                : "bg-surface text-ink-muted hover:bg-canvas",
            )}
          >
            {text}
          </button>
        ))}
      </div>
    </div>
  );
}

/** Kept for a future filter-by-concern control; already used for labels. */
export const conceptLabel = concernLabel;
