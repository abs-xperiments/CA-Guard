"use client";

/** The queue's search and filter controls, and the matching rule behind search. */

import type { RefObject } from "react";
import { Search } from "lucide-react";
import type { Finding } from "@/lib/types";
import { concernLabel } from "@/lib/types";
import { cx } from "./ui";

/**
 * A search a reviewer would type: a voucher number, part of a narration, an
 * account name, or an amount in any format ("2,51,082", "251082", "₹2.5").
 * Every word must match somewhere.
 */
export function matcher(query: string): (finding: Finding) => boolean {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  if (!words.length) return () => true;
  return (finding) => {
    const text = [
      finding.voucher_id,
      finding.narration ?? "",
      finding.prepared_by ?? "",
      ...finding.accounts,
    ]
      .join(" ")
      .toLowerCase();
    const digits = finding.amount_display.replace(/[^0-9]/g, "");
    return words.every((word) => {
      if (text.includes(word)) return true;
      const wordDigits = word.replace(/[^0-9]/g, "");
      return wordDigits.length >= 3 && digits.includes(wordDigits);
    });
  };
}

export function Filters({
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

/** Narrow the queue by reason, by missing document, or by what a reviewer types. */
export function NarrowingControls({
  concern,
  concernCounts,
  onConcern,
  onlyUndocumented,
  onToggleUndocumented,
  search,
  onSearch,
  searchBox,
}: {
  concern: string;
  concernCounts: Array<[string, number]>;
  onConcern: (kind: string) => void;
  onlyUndocumented: boolean;
  onToggleUndocumented: () => void;
  search: string;
  onSearch: (text: string) => void;
  searchBox: RefObject<HTMLInputElement | null>;
}) {
  return (
    <>
              <select
                value={concern}
                onChange={(event) => onConcern(event.target.value)}
                aria-label="Filter by reason"
                className="rounded-md bg-surface px-2 py-1 text-[12px] text-ink ring-1 ring-inset ring-line focus:outline-none focus:ring-accent"
              >
                <option value="all">Any reason</option>
                {concernCounts.map(([kind, count]) => (
                  <option key={kind} value={kind}>
                    {concernLabel(kind)} ({count})
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={() => onToggleUndocumented()}
                aria-pressed={onlyUndocumented}
                className={cx(
                  "rounded-md px-2 py-1 text-[12px] ring-1 ring-inset transition-colors",
                  onlyUndocumented
                    ? "bg-accent text-white ring-accent"
                    : "bg-surface text-ink ring-line hover:bg-canvas",
                )}
              >
                No document
              </button>
              <label className="relative">
                <Search
                  size={13}
                  className="pointer-events-none absolute left-2 top-1/2 -translate-y-1/2 text-ink-faint"
                />
                <input
                  ref={searchBox}
                  type="search"
                  value={search}
                  onChange={(event) => onSearch(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Escape") {
                      onSearch("");
                      event.currentTarget.blur();
                    }
                  }}
                  placeholder="Voucher, amount, account, narration, preparer  /"
                  aria-label="Search findings"
                  className="w-64 rounded-md bg-surface py-1 pl-7 pr-2 text-[12px] text-ink ring-1 ring-inset ring-line placeholder:text-ink-faint focus:outline-none focus:ring-accent"
                />
              </label>
    </>
  );
}
