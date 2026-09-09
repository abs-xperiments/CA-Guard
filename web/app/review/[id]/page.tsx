"use client";

/**
 * The review workspace.
 *
 * A ranked queue on the left, the evidence behind the selected finding on the
 * right. Fully keyboard-driven: j/k to move, Enter to open, a/i to decide,
 * Esc to close.
 *
 * Two things here came out of using it rather than testing it. The header
 * counters are derived from the findings on screen, because reading a
 * load-time snapshot meant the progress bar never moved. And a row that has
 * just been decided flashes once and stays visible for a beat before the
 * filter removes it — otherwise a decision looks like a row vanishing for no
 * reason.
 */

import { use, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, Download, Inbox, LogOut, ShieldCheck } from "lucide-react";
import { ApiError, api, auth } from "@/lib/api";
import type { Decision, Finding, Queue, RiskBand, User } from "@/lib/types";
import { EvidenceDrawer } from "@/components/EvidenceDrawer";
import { FindingsTable } from "@/components/FindingsTable";
import { IntakeNotice } from "@/components/IntakeNotice";
import { QueueSkeleton } from "@/components/Skeleton";
import { useToast } from "@/components/Toast";
import { Button, EmptyState, ErrorState, Key, Stat, cx } from "@/components/ui";

type BandFilter = RiskBand | "all";
type StatusFilter = "all" | "open" | "reviewed";

/** How long a just-decided row stays visible before the filter removes it. */
const SETTLE_MS = 1100;

export default function ReviewPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const toast = useToast();

  const [user, setUser] = useState<User | null>(null);
  const [queue, setQueue] = useState<Queue | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [cursor, setCursor] = useState(0);
  const [band, setBand] = useState<BandFilter>("all");
  const [status, setStatus] = useState<StatusFilter>("open");
  //: Vouchers decided moments ago. Kept in the list briefly so the decision is
  //: visibly acknowledged before the row leaves.
  const [settling, setSettling] = useState<Set<string>>(new Set());

  const load = useCallback(async () => {
    setError(null);
    try {
      setUser(await auth.me());
    } catch {
      router.replace("/login");
      return;
    }
    try {
      setQueue(await api.queue(id));
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not load the review.");
    }
  }, [id, router]);

  useEffect(() => {
    void load();
  }, [load]);

  const visible = useMemo(() => {
    if (!queue) return [];
    return queue.findings.filter((finding) => {
      if (band !== "all" && finding.band !== band) return false;
      const open = finding.status === "not yet reviewed";
      if (status === "open" && !open && !settling.has(finding.voucher_id)) return false;
      if (status === "reviewed" && open) return false;
      return true;
    });
  }, [queue, band, status, settling]);

  const reviewed = useMemo(
    () => (queue ? queue.findings.filter((f) => f.status !== "not yet reviewed").length : 0),
    [queue],
  );

  const current = visible[cursor] ?? null;
  const openFinding = selected
    ? (queue?.findings.find((f) => f.voucher_id === selected) ?? null)
    : null;

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

    // Hold the row in place just long enough to see it change.
    setSettling((previous) => new Set(previous).add(decision.voucher_id));
    window.setTimeout(() => {
      setSettling((previous) => {
        const next = new Set(previous);
        next.delete(decision.voucher_id);
        return next;
      });
    }, SETTLE_MS);
  }, []);

  /** Move to the next finding in the queue. Returns false when there is none. */
  const advance = useCallback((): boolean => {
    const remaining = visible.filter(
      (finding) =>
        finding.voucher_id !== selected && finding.status === "not yet reviewed",
    );
    const next = remaining[0];
    if (!next) return false;
    setSelected(next.voucher_id);
    setCursor(visible.findIndex((f) => f.voucher_id === next.voucher_id));
    return true;
  }, [visible, selected]);

  // Queue-level keyboard navigation. Decisions from inside the drawer are
  // handled there, so a keystroke is never claimed twice.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      if (target && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) return;
      if (event.metaKey || event.ctrlKey || event.altKey) return;

      if (event.key === "Escape") {
        setSelected(null);
      } else if (event.key === "j" || event.key === "ArrowDown") {
        event.preventDefault();
        setCursor((c) => Math.min(c + 1, Math.max(visible.length - 1, 0)));
      } else if (event.key === "k" || event.key === "ArrowUp") {
        event.preventDefault();
        setCursor((c) => Math.max(c - 1, 0));
      } else if (event.key === "Enter" && current) {
        setSelected(current.voucher_id);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [visible.length, current]);

  async function signOut() {
    await auth.logout().catch(() => undefined);
    router.replace("/login");
  }

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
      <div className="flex h-screen flex-col">
        <header className="shrink-0 border-b border-line bg-surface px-5 py-4">
          <div className="h-4 w-56 animate-pulse-soft rounded bg-line" />
        </header>
        <div className="flex-1 px-5 py-4">
          <QueueSkeleton />
        </div>
      </div>
    );
  }

  const progress = queue.flagged ? reviewed / queue.flagged : 0;
  const allDone = reviewed === queue.flagged && queue.flagged > 0;

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
              tone={allDone ? "text-rejected" : "text-ink"}
            />
          </dl>

          <a href={api.reportUrl(id, "html")} target="_blank" rel="noreferrer">
            <Button title="Open the review report">
              <Download size={14} /> Report
            </Button>
          </a>

          {user ? (
            <div className="flex items-center gap-2 border-l border-line pl-3">
              <div className="text-right">
                <p className="text-[12px] font-medium text-ink">{user.display_name}</p>
                <p className="text-[11px] text-ink-faint">
                  decisions signed as this account
                </p>
              </div>
              <Button variant="quiet" onClick={() => void signOut()} title="Sign out">
                <LogOut size={14} />
              </Button>
            </div>
          ) : null}
        </div>

        <div className="mt-2.5 h-1 overflow-hidden rounded-full bg-line">
          <div
            className={cx(
              "h-full rounded-full transition-[width] duration-500",
              allDone ? "bg-rejected" : "bg-accent",
            )}
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

            <div className="ml-auto flex items-center gap-1 text-[11px] text-ink-faint">
              <Key>j</Key>
              <Key>k</Key>
              <span>move</span>
              <Key>↵</Key>
              <span>open</span>
              <Key>a</Key>
              <Key>i</Key>
              <span>decide</span>
            </div>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
            {queue.intake ? <IntakeNotice intake={queue.intake} /> : null}
            {visible.length === 0 ? (
              <EmptyState
                icon={<Inbox size={22} />}
                title={
                  allDone
                    ? "Every finding has been reviewed"
                    : status === "open"
                      ? "Nothing left to review"
                      : "No findings match these filters"
                }
                detail={
                  allDone
                    ? `All ${queue.flagged} findings carry a recorded decision. Open the report to see them together.`
                    : status === "open"
                      ? "Every finding has a recorded decision."
                      : "Widen the risk or status filter to see more."
                }
                action={
                  allDone ? (
                    <a href={api.reportUrl(id, "html")} target="_blank" rel="noreferrer">
                      <Button variant="primary">
                        <Download size={14} /> Open the report
                      </Button>
                    </a>
                  ) : null
                }
              />
            ) : (
              <FindingsTable
                findings={visible}
                selected={selected}
                cursor={cursor}
                settling={settling}
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
            onClose={() => setSelected(null)}
            onDecided={applyDecision}
            onAdvance={advance}
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
