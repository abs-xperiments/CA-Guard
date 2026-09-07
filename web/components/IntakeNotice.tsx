"use client";

/**
 * What CA-Guard made of the uploaded file's columns.
 *
 * This exists for one reason. If a file has no supporting-document column,
 * every entry looks undocumented — and the queue will say so, loudly, about a
 * client who may have documented everything perfectly well. A limitation of the
 * *file* must never be mistaken for a finding about the *client*, so the
 * caveats are put in front of the reviewer before they read a single finding.
 */

import { useState } from "react";
import { ChevronDown, ChevronRight, Info } from "lucide-react";
import type { IntakeReport } from "@/lib/types";
import { cx } from "./ui";

export function IntakeNotice({ intake }: { intake: IntakeReport }) {
  const [open, setOpen] = useState(false);
  const hasCaveats = intake.notes.length > 0;

  if (!hasCaveats && intake.derived.length === 0) return null;

  return (
    <div
      className={cx(
        "mb-4 rounded-lg border px-4 py-3",
        hasCaveats ? "border-medium/30 bg-medium-soft" : "border-line bg-surface",
      )}
    >
      <button
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-start gap-2 text-left"
      >
        <Info
          size={15}
          className={cx("mt-0.5 shrink-0", hasCaveats ? "text-medium" : "text-ink-faint")}
        />
        <div className="min-w-0 flex-1">
          <p
            className={cx(
              "text-[13px] font-semibold",
              hasCaveats ? "text-medium" : "text-ink",
            )}
          >
            {hasCaveats
              ? "Some checks are limited by what this file contains"
              : "How this file was read"}
          </p>
          <p className="mt-0.5 text-[13px] text-ink-muted">
            {intake.summary} · {intake.rows_used.toLocaleString("en-IN")} of{" "}
            {intake.rows_read.toLocaleString("en-IN")} rows used
          </p>
        </div>
        {open ? (
          <ChevronDown size={15} className="mt-0.5 shrink-0 text-ink-faint" />
        ) : (
          <ChevronRight size={15} className="mt-0.5 shrink-0 text-ink-faint" />
        )}
      </button>

      {hasCaveats ? (
        <ul className="mt-2 space-y-1 pl-7">
          {intake.notes.map((note) => (
            <li key={note} className="text-[13px] leading-relaxed text-medium/90">
              {note}
            </li>
          ))}
        </ul>
      ) : null}

      {open ? (
        <dl className="mt-3 grid gap-3 border-t border-line/60 pt-3 pl-7 sm:grid-cols-3">
          <Detail
            label="Recognised"
            items={Object.entries(intake.mapped).map(([from, to]) => `${from} → ${to}`)}
          />
          <Detail label="Worked out from the data" items={intake.derived} />
          <Detail label="Not present in the file" items={intake.not_in_file} />
        </dl>
      ) : null}
    </div>
  );
}

function Detail({ label, items }: { label: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div>
      <dt className="text-[11px] uppercase tracking-wide text-ink-faint">{label}</dt>
      <dd className="mt-1 space-y-0.5">
        {items.map((item) => (
          <p key={item} className="font-mono text-[11px] text-ink-muted">
            {item}
          </p>
        ))}
      </dd>
    </div>
  );
}
