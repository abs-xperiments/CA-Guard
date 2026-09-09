"use client";

/**
 * The shell both sign-in and sign-up sit in.
 *
 * Deliberately quiet. This is the first thing a CA sees, and it should look
 * like software their firm would licence rather than a consumer sign-up: one
 * column, no illustration, no marketing, and a sentence saying where the data
 * goes — which is the question a person handing over a client ledger actually
 * has.
 */

import type { ReactNode } from "react";
import { ShieldCheck } from "lucide-react";

export function AuthShell({
  title,
  subtitle,
  children,
  footer,
}: {
  title: string;
  subtitle: string;
  children: ReactNode;
  footer: ReactNode;
}) {
  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-12">
      <div className="w-full max-w-sm">
        <div className="mb-7 text-center">
          <div className="mb-3 inline-flex items-center gap-2 text-accent">
            <ShieldCheck size={20} />
            <span className="text-sm font-semibold tracking-tight">CA-Guard</span>
          </div>
          <h1 className="text-xl font-semibold tracking-tight text-ink">{title}</h1>
          <p className="mt-1.5 text-[13px] leading-relaxed text-ink-muted">{subtitle}</p>
        </div>

        <div className="rounded-xl border border-line bg-surface p-6 shadow-sm">
          {children}
        </div>

        <p className="mt-5 text-center text-[13px] text-ink-muted">{footer}</p>

        <p className="mt-6 text-center text-[12px] leading-relaxed text-ink-faint">
          Ledgers are read on this machine and are not sent anywhere. Your account
          exists only on this installation.
        </p>
      </div>
    </main>
  );
}

export function Field({
  label,
  type = "text",
  value,
  onChange,
  placeholder,
  hint,
  autoComplete,
  autoFocus,
  required = true,
}: {
  label: string;
  type?: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  hint?: string;
  autoComplete?: string;
  autoFocus?: boolean;
  required?: boolean;
}) {
  return (
    <label className="mb-4 block">
      <span className="mb-1 block text-[12px] font-medium text-ink">{label}</span>
      <input
        type={type}
        value={value}
        required={required}
        autoFocus={autoFocus}
        autoComplete={autoComplete}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-md border border-line bg-surface px-3 py-2 text-[14px] text-ink transition-colors placeholder:text-ink-faint focus:border-accent focus:outline-none"
      />
      {hint ? <span className="mt-1 block text-[11px] text-ink-faint">{hint}</span> : null}
    </label>
  );
}

export function FormError({ message }: { message: string }) {
  return (
    <p
      role="alert"
      className="mb-4 rounded-md border border-high/25 bg-high-soft px-3 py-2 text-[13px] text-high"
    >
      {message}
    </p>
  );
}
