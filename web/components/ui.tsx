/**
 * The small pieces everything else is built from.
 *
 * Written here rather than pulled from a component library: the project owns
 * its interface code, and these are simple enough that a dependency would cost
 * more than it saves. The shapes follow shadcn/ui conventions so anyone who
 * knows those will recognise them.
 */

import type { ReactNode } from "react";
import type { RiskBand } from "@/lib/types";

export function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

const BAND_STYLES: Record<RiskBand, string> = {
  high: "bg-high-soft text-high ring-high/20",
  medium: "bg-medium-soft text-medium ring-medium/20",
  low: "bg-low-soft text-low ring-low/20",
};

export function BandBadge({ band }: { band: RiskBand }) {
  return (
    <span
      className={cx(
        "inline-flex items-center rounded-full px-2 py-0.5 text-[11px]",
        "font-semibold uppercase tracking-wide ring-1 ring-inset",
        BAND_STYLES[band],
      )}
    >
      {band}
    </span>
  );
}

const STATUS_STYLES: Record<string, string> = {
  accept: "text-accepted",
  reject: "text-rejected",
  investigate: "text-investigating",
  adjust: "text-ink-muted",
};

/** Reads as a sentence, because "accept" alone is ambiguous in a table. */
const STATUS_WORDS: Record<string, string> = {
  accept: "Accepted",
  reject: "Rejected",
  investigate: "Investigating",
  adjust: "Re-banded",
};

export function StatusLabel({ status }: { status: string }) {
  if (status === "not yet reviewed") {
    return <span className="text-ink-faint">Not reviewed</span>;
  }
  return (
    <span className={cx("font-medium", STATUS_STYLES[status] ?? "text-ink")}>
      {STATUS_WORDS[status] ?? status}
    </span>
  );
}

/** A quiet bar. Evidence completeness is a judgement aid, not a score to chase. */
export function EvidenceMeter({ completeness }: { completeness: number }) {
  const percent = Math.round(completeness * 100);
  const tone =
    percent >= 80 ? "bg-rejected" : percent >= 40 ? "bg-medium" : "bg-high";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-14 overflow-hidden rounded-full bg-line">
        <div
          className={cx("h-full rounded-full transition-[width] duration-300", tone)}
          style={{ width: `${Math.max(percent, 3)}%` }}
        />
      </div>
      <span className="tabular text-xs text-ink-muted">{percent}%</span>
    </div>
  );
}

export function Button({
  children,
  onClick,
  variant = "ghost",
  disabled,
  title,
  type = "button",
}: {
  children: ReactNode;
  onClick?: () => void;
  variant?: "primary" | "ghost" | "danger" | "quiet";
  disabled?: boolean;
  title?: string;
  type?: "button" | "submit";
}) {
  const styles = {
    primary: "bg-accent text-white hover:bg-accent/90 shadow-sm",
    ghost: "bg-surface text-ink ring-1 ring-inset ring-line hover:bg-canvas",
    danger: "bg-surface text-high ring-1 ring-inset ring-high/25 hover:bg-high-soft",
    quiet: "text-ink-muted hover:text-ink hover:bg-canvas",
  }[variant];

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={cx(
        "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium",
        "transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-45",
        styles,
      )}
    >
      {children}
    </button>
  );
}

/** A keyboard hint. Present throughout, because this is a keyboard tool. */
export function Key({ children }: { children: ReactNode }) {
  return (
    <kbd className="rounded border border-line-strong bg-canvas px-1.5 py-0.5 font-mono text-[10px] text-ink-muted">
      {children}
    </kbd>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-ink-muted">
      <span className="animate-pulse-soft inline-block size-2 rounded-full bg-accent" />
      {label ?? "Working…"}
    </div>
  );
}

/**
 * Empty states carry their own instruction. An empty queue in an audit tool is
 * ambiguous — it could mean "nothing to review" or "something went wrong" — so
 * it always says which.
 */
export function EmptyState({
  title,
  detail,
  action,
  icon,
}: {
  title: string;
  detail: string;
  action?: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-line bg-surface px-8 py-16 text-center">
      {icon ? <div className="text-ink-faint">{icon}</div> : null}
      <h3 className="text-sm font-semibold text-ink">{title}</h3>
      <p className="max-w-md text-sm text-ink-muted">{detail}</p>
      {action}
    </div>
  );
}

export function ErrorState({ message, retry }: { message: string; retry?: () => void }) {
  return (
    <div className="rounded-lg border border-high/25 bg-high-soft px-5 py-4">
      <p className="text-sm font-semibold text-high">Something went wrong</p>
      <p className="mt-1 text-sm text-high/85">{message}</p>
      {retry ? (
        <div className="mt-3">
          <Button onClick={retry}>Try again</Button>
        </div>
      ) : null}
    </div>
  );
}

export function Stat({ label, value, tone }: { label: string; value: ReactNode; tone?: string }) {
  return (
    <div>
      <dt className="text-[11px] uppercase tracking-wide text-ink-faint">{label}</dt>
      <dd className={cx("tabular mt-0.5 text-sm font-semibold", tone ?? "text-ink")}>
        {value}
      </dd>
    </div>
  );
}
