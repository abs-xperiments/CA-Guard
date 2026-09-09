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
import { BandBadge, EvidenceMeter, StatusLabel, cx } from "./ui";

interface Props {
  findings: Finding[];
  selected: string | null;
  cursor: number;
  /** Vouchers decided moments ago, held in place so the change is visible. */
  settling: Set<string>;
  onSelect: (voucherId: string) => void;
  onCursorChange: (index: number) => void;
}

export function FindingsTable({
  findings,
  selected,
  cursor,
  settling,
  onSelect,
  onCursorChange,
}: Props) {
  const rowRefs = useRef<Array<HTMLTableRowElement | null>>([]);

  // Keep the keyboard cursor in view without yanking the page around.
  useEffect(() => {
    rowRefs.current[cursor]?.scrollIntoView({ block: "nearest" });
  }, [cursor]);

  return (
    <div className="overflow-hidden rounded-lg border border-line bg-surface">
      <table className="w-full border-collapse text-sm">
        <thead className="sticky top-0 z-10">
          <tr className="border-b border-line bg-canvas/95 backdrop-blur-sm">
            <Th className="w-[13%]">Voucher</Th>
            <Th className="w-[10%]">Date</Th>
            <Th className="w-[13%] text-right">Amount</Th>
            <Th className="w-[9%]">Risk</Th>
            <Th>Why it was flagged</Th>
            <Th className="w-[12%]">Evidence</Th>
            <Th className="w-[11%]">Status</Th>
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
                </Td>
                <Td className="text-ink-muted">{ukDate(finding.voucher_date)}</Td>
                <Td className="tabular text-right font-medium">
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
                <Td>
                  <EvidenceMeter completeness={finding.evidence.completeness} />
                </Td>
                <Td>
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
