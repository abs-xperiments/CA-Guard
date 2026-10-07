"use client";

/**
 * What is happening to the ledger right now, step by step.
 *
 * A full year's ledger takes ten seconds or more. A spinner for that long
 * reads as "stuck"; named stages read as "working". The first stage is the
 * browser sending the file, with a real percentage; the rest come from the
 * server as the analysis reaches them.
 */

import { Check, Loader2 } from "lucide-react";
import type { UploadJob } from "@/lib/types";
import { cx } from "./ui";

export function UploadProgress({
  filename,
  sent,
  job,
}: {
  filename: string;
  /** 0–1 while the file is being sent; 1 once the server has it. */
  sent: number;
  job: UploadJob | null;
}) {
  const sending = !job;
  const steps: { key: string; label: string; state: "done" | "current" | "pending" }[] = [
    {
      key: "sending",
      label: sending ? `Sending the file — ${Math.round(sent * 100)}%` : "File received",
      state: sending ? "current" : "done",
    },
    ...(job?.stages ??
      [
        "Reading the file",
        "Recognising the columns",
        "Analysing every voucher",
        "Keeping the original",
      ].map((label) => ({ key: label, label, state: "pending" as const }))),
  ];
  // Queued behind another upload: say so, rather than showing a stalled step.
  const queued = job?.state === "queued";

  return (
    <div className="mx-auto max-w-sm text-left" role="status" aria-live="polite">
      <p className="mb-3 truncate text-center text-sm font-medium text-ink">{filename}</p>
      <ol className="space-y-2">
        {steps.map((step) => (
          <li key={step.key} className="flex items-center gap-2.5 text-[13px]">
            <span
              className={cx(
                "flex size-5 shrink-0 items-center justify-center rounded-full",
                step.state === "done" && "bg-rejected text-white",
                step.state === "current" && "bg-accent-soft text-accent",
                step.state === "pending" && "bg-canvas text-ink-faint ring-1 ring-inset ring-line",
              )}
            >
              {step.state === "done" ? (
                <Check size={12} />
              ) : step.state === "current" ? (
                <Loader2 size={12} className="animate-spin motion-reduce:animate-none" />
              ) : null}
            </span>
            <span
              className={cx(
                step.state === "pending" ? "text-ink-faint" : "text-ink",
                step.state === "current" && "font-medium",
              )}
            >
              {step.label}
            </span>
          </li>
        ))}
      </ol>
      {queued ? (
        <p className="mt-3 text-center text-[12px] text-ink-muted">
          Waiting for another ledger to finish first…
        </p>
      ) : job ? (
        <p className="tabular mt-3 text-center text-[12px] text-ink-faint">
          {job.elapsed_seconds.toFixed(0)}s · a full year&apos;s ledger takes about ten seconds
        </p>
      ) : null}
    </div>
  );
}
