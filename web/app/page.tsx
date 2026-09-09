"use client";

/**
 * The way in: open a ledger, or return to one already being reviewed.
 *
 * Deliberately plain. The interesting screen is the workspace; this one only
 * has to be obvious, and to say clearly when CA-Guard is not running — the most
 * likely thing to go wrong on a first attempt.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { FileUp, FolderOpen, LogOut, ShieldCheck } from "lucide-react";
import { ApiError, api, auth } from "@/lib/api";
import type { Engagement, User } from "@/lib/types";
import { Button, EmptyState, ErrorState, Spinner } from "@/components/ui";

export default function Home() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [engagements, setEngagements] = useState<Engagement[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setUser(await auth.me());
    } catch {
      // Not signed in, or the session has expired. Both mean: sign in.
      router.replace("/login");
      return;
    }
    try {
      setEngagements(await api.engagements());
    } catch (caught) {
      setEngagements([]);
      setError(caught instanceof ApiError ? caught.message : "Cannot reach CA-Guard.");
    }
  }, [router]);

  useEffect(() => {
    void load();
  }, [load]);

  async function open(file: File) {
    setUploading(true);
    setError(null);
    try {
      const queue = await api.upload(file);
      router.push(`/review/${queue.engagement.id}`);
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "Could not read that file.",
      );
      setUploading(false);
    }
  }

  return (
    <main className="mx-auto max-w-3xl px-6 py-16">
      <header className="mb-10">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-accent">
            <ShieldCheck size={20} />
            <span className="text-sm font-semibold tracking-tight">CA-Guard</span>
          </div>
          {user ? (
            <div className="flex items-center gap-3">
              <div className="text-right">
                <p className="text-[12px] font-medium text-ink">{user.display_name}</p>
                <p className="text-[11px] text-ink-faint">{user.email}</p>
              </div>
              <Button
                variant="quiet"
                title="Sign out"
                onClick={async () => {
                  await auth.logout().catch(() => undefined);
                  router.replace("/login");
                }}
              >
                <LogOut size={14} />
              </Button>
            </div>
          ) : null}
        </div>
        <h1 className="mt-3 text-2xl font-semibold tracking-tight text-ink">
          Open a ledger for review
        </h1>
        <p className="mt-2 max-w-xl text-sm leading-relaxed text-ink-muted">
          CA-Guard reads a general ledger, prioritises the entries that deserve
          attention, and shows you why. Everything stays on this machine.
        </p>
      </header>

      {error ? (
        <div className="mb-6">
          <ErrorState message={error} retry={() => void load()} />
        </div>
      ) : null}

      <div
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          const file = event.dataTransfer.files[0];
          if (file) void open(file);
        }}
        className={`rounded-xl border-2 border-dashed px-8 py-14 text-center transition-colors duration-150 ${
          dragging ? "border-accent bg-accent-soft" : "border-line bg-surface"
        }`}
      >
        <FileUp size={28} className="mx-auto text-ink-faint" />
        <p className="mt-3 text-sm font-medium text-ink">
          Drop a ledger here, or choose a file
        </p>
        <p className="mt-1 text-[13px] text-ink-muted">
          CSV, Excel or Parquet. Nothing is uploaded anywhere — it is read on this
          machine.
        </p>
        <div className="mt-5 flex justify-center">
          {uploading ? (
            <Spinner label="Reading and analysing the ledger…" />
          ) : (
            <Button variant="primary" onClick={() => input.current?.click()}>
              Choose a file
            </Button>
          )}
        </div>
        <input
          ref={input}
          type="file"
          accept=".csv,.xlsx,.xls,.parquet"
          className="hidden"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) void open(file);
          }}
        />
      </div>

      <section className="mt-10">
        <h2 className="mb-3 text-[11px] font-semibold uppercase tracking-wide text-ink-faint">
          Reviews in progress
        </h2>
        {engagements === null ? (
          <Spinner label="Loading…" />
        ) : engagements.length === 0 ? (
          <EmptyState
            icon={<FolderOpen size={22} />}
            title="No reviews yet"
            detail="Open a ledger above to start one. Your decisions are kept on this machine and will be here when you come back."
          />
        ) : (
          <ul className="divide-y divide-line overflow-hidden rounded-lg border border-line bg-surface">
            {engagements.map((engagement) => (
              <li key={engagement.id}>
                <button
                  onClick={() => router.push(`/review/${engagement.id}`)}
                  className="flex w-full items-center justify-between px-4 py-3 text-left transition-colors hover:bg-canvas"
                >
                  <div>
                    <p className="text-sm font-medium text-ink">{engagement.name}</p>
                    <p className="text-[13px] text-ink-muted">
                      {engagement.source_name} · {engagement.voucher_count.toLocaleString("en-IN")}{" "}
                      vouchers
                    </p>
                  </div>
                  <span className="font-mono text-[11px] text-ink-faint">
                    {engagement.short_hash}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
