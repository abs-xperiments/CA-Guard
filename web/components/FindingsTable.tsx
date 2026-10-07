"use client";

/**
 * The review queue.
 *
 * Dense, because a reviewer is scanning; readable, because they are scanning
 * for hours. Ranked highest priority first — Phase 4 measured that ordering
 * taking precision in the first 25 items from 34% to 100%, so the order is the
 * product and the table exists to present it.
 *
 * Fully keyboard-driven: j/k or arrows to move, Enter to open. A CA working a
 * long queue should not have to reach for the mouse.
 */

import { useEffect, useRef } from "react";
import type { Finding } from "@/lib/types";
import { concernLabel, ukDate } from "@/lib/types";
import { BandBadge, StatusLabel, cx } from "./ui";

interface Props {
  findings: Finding[];
  selected: string | null;
  cursor: number;
  /** Vouchers decided moments ago, held in place so the change is visible. */
  settling: Set<string>;
  onSelect: (voucherId: string) => void;
  onCursorChange: (index: number) => void;
  /** Columns the uploaded file did not have: their evidence cannot be counted. */
  notInFile?: string[];
}

export function FindingsTable({
  findings,
  selected,
  cursor,
  settling,
  onSelect,
  onCursorChange,
  notInFile = [],
}: Props) {
  const rowRefs = useRef<Array<HTMLTableRowElement | null>>([]);

  // Keep the keyboard cursor in view without yanking the page around.
  useEffect(() => {
    rowRefs.current[cursor]?.scrollIntoView({ block: "nearest" });
  }, [cursor]);

  return (
    // A container query, not a viewport one: what matters is how wide the queue
    // itself is, which shrinks when a finding is open beside it.
    <div className="@container overflow-hidden rounded-lg border border-line bg-surface">
      {/* Fixed layout: the table always fits its container, and long content
          truncates instead of pushing the page sideways. */}
      <table className="w-full table-fixed border-collapse text-sm">
        <thead className="sticky top-0 z-10">
          <tr className="border-b border-line bg-canvas/95 backdrop-blur-sm">
            <Th className="w-[36%] @4xl:w-[24%]">Voucher</Th>
            <Th className="hidden w-[9%] @4xl:table-cell">Date</Th>
            <Th className="w-[24%] text-right @4xl:w-[12%]">Amount</Th>
            <Th className="w-[13%] @4xl:w-[7%]">Risk</Th>
            <Th>Why it was flagged</Th>
            <Th className="hidden w-[10%] @4xl:table-cell">
              <span title="Expected evidence present: document, approval where the amount needs one, narration">
                Evidence
              </span>
            </Th>
            <Th className="hidden w-[10%] @4xl:table-cell">Status</Th>
          </tr>
        </thead>
        <tbody>
          {findings.map((finding, index) => {
            const isSelected = finding.voucher_id === selected;
            const isCursor = index === cursor;
            // A single confirming flash. The reported problem was that deciding
            // looked like nothing had happened until the row silently vanished.
            const justDecided = settling.has(finding.voucher_id);
            return (
              <tr
                key={finding.voucher_id}
                ref={(node) => {
                  rowRefs.current[index] = node;
                }}
                onClick={() => {
                  onCursorChange(index);
                  onSelect(finding.voucher_id);
                }}
                aria-selected={isSelected}
                className={cx(
                  "animate-row cursor-pointer border-b border-line/70 transition-colors duration-100",
                  justDecided
                    ? "animate-confirm"
                    : isSelected
                      ? "bg-accent-soft"
                      : isCursor
                        ? "bg-canvas"
                        : "hover:bg-canvas/70",
                )}
                style={{ animationDelay: `${Math.min(index, 12) * 12}ms` }}
              >
                <Td>
                  <span className="font-mono text-[13px] text-ink">
                    {finding.voucher_id}
                  </span>
                  {/* What the transaction is, so a row can be judged before opening it. */}
                  {finding.accounts.length || finding.narration ? (
                    <span
                      className="block truncate text-[11px] text-ink-muted"
                      title={[finding.accounts.join(" · "), finding.narration]
                        .filter(Boolean)
                        .join(" — ")}
                    >
                      {finding.accounts.slice(0, 2).join(" · ")}
                      {finding.accounts.length > 2 ? " …" : ""}
                      {finding.narration ? (
                        <span className="text-ink-faint"> — {finding.narration}</span>
                      ) : null}
                    </span>
                  ) : null}
                </Td>
                <Td className="hidden text-ink-muted @4xl:table-cell">
                  {ukDate(finding.voucher_date)}
                </Td>
                <Td className="tabular truncate text-right font-medium">
                  {finding.amount_display}
                </Td>
                <Td>
                  <BandBadge band={finding.band} />
                </Td>
                <Td>
                  <div className="flex flex-wrap gap-1">
                    {finding.concerns.slice(0, 3).map((concern) => (
                      <span
                        key={concern}
                        className="rounded bg-canvas px-1.5 py-0.5 text-[11px] text-ink-muted ring-1 ring-inset ring-line"
                      >
                        {concernLabel(concern)}
                      </span>
                    ))}
                    {finding.concerns.length > 3 ? (
                      <span className="px-1 py-0.5 text-[11px] text-ink-faint">
                        +{finding.concerns.length - 3} more
                      </span>
                    ) : null}
                  </div>
                </Td>
                <Td className="hidden @4xl:table-cell">
                  <EvidenceCount finding={finding} notInFile={notInFile} />
                </Td>
                <Td className="hidden @4xl:table-cell">
                  <StatusLabel status={finding.status} />
                </Td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function Th({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <th
      scope="col"
      className={cx(
        "px-3 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wide text-ink-faint",
        className,
      )}
    >
      {children}
    </th>
  );
}

function Td({ children, className }: { children: React.ReactNode; className?: string }) {
  return <td className={cx("px-3 py-2.5 align-middle", className)}>{children}</td>;
}

/**
 * "1 of 3", counted exactly as the explanation card counts: an approval below
 * the limit is not expected, and a column the file never had is not counted —
 * that is a fact about the export, not about the client.
 */
function EvidenceCount({ finding, notInFile }: { finding: Finding; notInFile: string[] }) {
  const checks: boolean[] = [];
  const evidence = finding.evidence;
  if (!notInFile.includes("document_ref")) checks.push(evidence.has_document);
  if (evidence.approval_expected && !notInFile.includes("approved_by")) {
    checks.push(evidence.has_approval);
  }
  if (!notInFile.includes("narration")) checks.push(evidence.has_narration);
  if (!checks.length) {
    return <span className="text-[12px] text-ink-faint">not in file</span>;
  }
  const present = checks.filter(Boolean).length;
  const tone =
    present === checks.length ? "text-rejected" : present === 0 ? "text-high" : "text-medium";
  return (
    <span className={cx("tabular text-[12px] font-medium", tone)}>
      {present} of {checks.length}
    </span>
  );
}
