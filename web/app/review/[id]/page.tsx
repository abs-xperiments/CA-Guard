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

import { use, useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Download,
  FileSpreadsheet,
  Inbox,
  LogOut,
  ShieldCheck,
} from "lucide-react";
import { ApiError, api, auth } from "@/lib/api";
import type { Decision, Finding, Queue, RiskBand, User } from "@/lib/types";
import { EvidenceDrawer } from "@/components/EvidenceDrawer";
import { FindingsTable } from "@/components/FindingsTable";
import { IntakeNotice } from "@/components/IntakeNotice";
import { QueueSkeleton } from "@/components/Skeleton";
import { EngagementTitle } from "@/components/EngagementTitle";
import { Filters, NarrowingControls, matcher } from "@/components/QueueControls";
import { SourcesPanel } from "@/components/SourcesPanel";
import { useToast } from "@/components/Toast";
import { Button, EmptyState, ErrorState, Key, Stat, cx, shortcutBlocked } from "@/components/ui";

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
  const [showSources, setShowSources] = useState(false);
  const [search, setSearch] = useState("");
  const [concern, setConcern] = useState("all");
  const [onlyUndocumented, setOnlyUndocumented] = useState(false);
  // Rows rendered so far. A ranked queue is worked from the top, so drawing the
  // first page and adding more on request keeps a 2,000-finding ledger fast.
  const [shown, setShown] = useState(PAGE_SIZE);
  const searchBox = useRef<HTMLInputElement>(null);
  // 409: the engagement exists but cannot be rebuilt (its file was deleted, or
  // it predates stored originals). Retrying cannot help; re-uploading can.
  const [needsLedger, setNeedsLedger] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      setUser(await auth.me());
    } catch {
      router.replace("/login");
      return;
    }
    try {
      const loaded = await api.queue(id);
      setQueue(loaded);
      // A link to a finding (?finding=V003034) opens it, so a reviewer can
      // refresh, or send a colleague straight to the entry they mean.
      const linked = new URLSearchParams(window.location.search).get("finding");
      if (linked && loaded.findings.some((f) => f.voucher_id === linked)) {
        setSelected(linked);
      }
    } catch (caught) {
      setNeedsLedger(caught instanceof ApiError && caught.status === 409);
      setError(caught instanceof ApiError ? caught.message : "Could not load the review.");
    }
  }, [id, router]);

  useEffect(() => {
    void load();
  }, [load]);

  // Keep the address in step with the open finding. replaceState, not a push:
  // moving through a queue should not fill the back button with every voucher.
  useEffect(() => {
    if (!queue) return;
    const url = new URL(window.location.href);
    if (selected) url.searchParams.set("finding", selected);
    else url.searchParams.delete("finding");
    window.history.replaceState(null, "", url);
  }, [queue, selected]);

  const visible = useMemo(() => {
    if (!queue) return [];
    const match = matcher(search);
    return queue.findings.filter((finding) => {
      if (band !== "all" && finding.band !== band) return false;
      if (concern !== "all" && !finding.concerns.includes(concern)) return false;
      if (onlyUndocumented && finding.evidence.has_document) return false;
      if (!match(finding)) return false;
      const open = finding.status === "not yet reviewed";
      if (status === "open" && !open && !settling.has(finding.voucher_id)) return false;
      if (status === "reviewed" && open) return false;
      return true;
    });
  }, [queue, band, status, settling, search, concern, onlyUndocumented]);

  // Any narrowing beyond "not reviewed" means an empty list says nothing about
  // whether the review is finished.
  const narrowed = band !== "all" || concern !== "all" || onlyUndocumented || search.trim() !== "";

  useEffect(() => {
    setShown(PAGE_SIZE);
  }, [band, status, search, concern, onlyUndocumented]);

  const concernCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const finding of queue?.findings ?? []) {
      for (const kind of finding.concerns) counts.set(kind, (counts.get(kind) ?? 0) + 1);
    }
    return [...counts.entries()].sort((a, b) => b[1] - a[1]);
  }, [queue]);

  const clearFilters = useCallback(() => {
    setBand("all");
    setConcern("all");
    setOnlyUndocumented(false);
    setSearch("");
  }, []);

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

  // Moving past the last drawn row with the keyboard draws the next page.
  useEffect(() => {
    if (cursor >= shown - 1) setShown((previous) => previous + PAGE_SIZE);
  }, [cursor, shown]);

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
      if (shortcutBlocked(event)) return;

      if (event.key === "/") {
        event.preventDefault();
        searchBox.current?.focus();
      } else if (event.key === "Escape") {
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

  if (error && needsLedger) {
    return (
      <main className="mx-auto max-w-2xl px-6 py-16">
        <EmptyState
          icon={<FileSpreadsheet size={28} />}
          title="This review needs its ledger again"
          detail={error}
          action={
            <Link href="/">
              <Button variant="primary">Upload the ledger</Button>
            </Link>
          }
        />
      </main>
    );
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
            aria-label="Back to all reviews"
            className="flex items-center gap-1.5 text-sm text-ink-muted transition-colors hover:text-ink"
          >
            <ArrowLeft size={15} />
            <ShieldCheck size={16} className="text-accent" />
          </Link>

          <div className="min-w-0">
            <EngagementTitle
              name={queue.engagement.name}
              onRename={async (name) => {
                const renamed = await api.rename(id, name);
                setQueue((previous) => (previous ? { ...previous, engagement: renamed } : previous));
              }}
            />
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

          <Button onClick={() => setShowSources(true)} title="The files this review was built from">
            <FileSpreadsheet size={14} /> Source
          </Button>
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

      <main className="flex min-h-0 flex-1">
        <section className="flex min-w-0 flex-1 flex-col" aria-label="Review queue">
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
            <NarrowingControls
              concern={concern}
              concernCounts={concernCounts}
              onConcern={setConcern}
              onlyUndocumented={onlyUndocumented}
              onToggleUndocumented={() => setOnlyUndocumented((value) => !value)}
              search={search}
              onSearch={setSearch}
              searchBox={searchBox}
            />

            <div className="ml-auto flex items-center gap-1 text-[11px] text-ink-faint">
              <Key>j</Key>
              <Key>k</Key>
              <span>move</span>
              <Key>↵</Key>
              <span>open</span>
              <Key>e</Key>
              <Key>i</Key>
              <span>decide</span>
            </div>
          </div>

          {/* Focusable so the queue can be scrolled from the keyboard too. */}
          <div
            className="min-h-0 flex-1 overflow-y-auto px-5 py-4"
            tabIndex={0}
            aria-label="Findings"
          >
            {queue.intake ? <IntakeNotice intake={queue.intake} /> : null}
            {reviewed === 0 && !narrowed && visible.length > 0 ? (
              <p className="mb-3 text-[12px] leading-relaxed text-ink-muted">
                Start at the top: the queue is ranked, highest priority first. Open a finding to
                see why it was flagged, what evidence it has and what to look at next, then record
                your conclusion — <Key>e</Key> exception to follow up, <Key>i</Key> investigate,
                or clear it with a reason.
              </p>
            ) : null}
            {visible.length === 0 ? (
              <EmptyState
                icon={<Inbox size={22} />}
                title={
                  narrowed
                    ? "No findings match"
                    : allDone
                      ? "Every finding has been reviewed"
                      : status === "open"
                        ? "Nothing left to review"
                        : "No findings match these filters"
                }
                detail={
                  narrowed
                    ? "Nothing matches the search or filters. Clear them to see the rest of the queue."
                    : allDone
                      ? `All ${queue.flagged} findings carry a recorded decision. Open the report to see them together.`
                      : status === "open"
                        ? "Every finding has a recorded decision."
                        : "Widen the risk or status filter to see more."
                }
                action={
                  narrowed ? (
                    <Button onClick={clearFilters}>Clear search and filters</Button>
                  ) : allDone ? (
                    <a href={api.reportUrl(id, "html")} target="_blank" rel="noreferrer">
                      <Button variant="primary">
                        <Download size={14} /> Open the report
                      </Button>
                    </a>
                  ) : null
                }
              />
            ) : (
              <>
              <FindingsTable
                findings={visible.slice(0, shown)}
                selected={selected}
                cursor={cursor}
                settling={settling}
                onSelect={setSelected}
                onCursorChange={setCursor}
                notInFile={queue.intake?.not_in_file ?? []}
              />
              {visible.length > shown ? (
                <div className="mt-3 flex items-center justify-center gap-3 text-[12px] text-ink-muted">
                  <span className="tabular">
                    Showing {shown.toLocaleString("en-IN")} of{" "}
                    {visible.length.toLocaleString("en-IN")}, highest priority first
                  </span>
                  <Button onClick={() => setShown((previous) => previous + PAGE_SIZE)}>
                    Show {Math.min(PAGE_SIZE, visible.length - shown).toLocaleString("en-IN")} more
                  </Button>
                </div>
              ) : null}
              </>
            )}
          </div>
        </section>

        {openFinding ? (
          <EvidenceDrawer
            engagementId={id}
            finding={openFinding}
            onClose={() => setSelected(null)}
            onOpenVoucher={setSelected}
            onDecided={applyDecision}
            onAdvance={advance}
          />
        ) : null}
      </main>

      {showSources ? (
        <SourcesPanel
          engagementId={id}
          canDelete={user?.is_admin ?? false}
          onClose={() => setShowSources(false)}
        />
      ) : null}
    </div>
  );
}

const PAGE_SIZE = 200;
