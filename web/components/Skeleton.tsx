"use client";

/**
 * Loading placeholders shaped like the thing that is coming.
 *
 * A spinner tells a reviewer that something is happening; a skeleton tells them
 * *what* is happening and roughly how much of it there is. On a queue that
 * takes a moment to analyse, the second is materially calmer — the page does
 * not jump when the content lands, because the space was already the right size.
 */

import { cx } from "./ui";

function Bar({ className }: { className?: string }) {
  return (
    <span
      className={cx(
        "animate-shimmer relative block overflow-hidden rounded bg-line/70",
        className,
      )}
    />
  );
}

export function QueueSkeleton({ rows = 8 }: { rows?: number }) {
  return (
    <div
      aria-busy="true"
      aria-label="Loading the review queue"
      className="overflow-hidden rounded-lg border border-line bg-surface"
    >
      <div className="flex gap-4 border-b border-line bg-canvas/60 px-3 py-3">
        {["w-24", "w-20", "w-24", "w-14", "w-40", "w-20", "w-20"].map((width, index) => (
          <Bar key={index} className={cx("h-2.5", width)} />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, row) => (
        <div key={row} className="flex items-center gap-4 border-b border-line/60 px-3 py-4">
          <Bar className="h-3 w-24" />
          <Bar className="h-3 w-20" />
          <Bar className="h-3 w-24" />
          <Bar className="h-4 w-14 rounded-full" />
          <Bar className="h-3 flex-1" />
          <Bar className="h-2 w-16 rounded-full" />
          <Bar className="h-3 w-20" />
        </div>
      ))}
    </div>
  );
}

export function DrawerSkeleton() {
  return (
    <div aria-busy="true" className="space-y-5 p-5">
      <Bar className="h-5 w-40" />
      <Bar className="h-8 w-56" />
      <div className="space-y-2 pt-2">
        {[0, 1, 2].map((index) => (
          <Bar key={index} className="h-16 w-full rounded-md" />
        ))}
      </div>
    </div>
  );
}
