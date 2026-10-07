"use client";

import { useState } from "react";
import { Pencil } from "lucide-react";
import { ApiError } from "@/lib/api";
import { useToast } from "./Toast";

/** The engagement's name, editable in place — "Sharma Traders — FY25" beats a derived id. */
export function EngagementTitle({
  name,
  onRename,
}: {
  name: string;
  onRename: (name: string) => Promise<void>;
}) {
  const toast = useToast();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(name);

  async function save() {
    setEditing(false);
    if (draft.trim() === name) return;
    try {
      await onRename(draft.trim());
    } catch (caught) {
      setDraft(name);
      toast.show({
        tone: "error",
        message: "The name was not changed",
        detail: caught instanceof ApiError ? caught.message : "Nothing has changed.",
      });
    }
  }

  if (editing) {
    return (
      <input
        autoFocus
        value={draft}
        maxLength={120}
        aria-label="Engagement name"
        onChange={(event) => setDraft(event.target.value)}
        onBlur={() => void save()}
        onKeyDown={(event) => {
          if (event.key === "Enter") void save();
          if (event.key === "Escape") {
            setDraft(name);
            setEditing(false);
          }
        }}
        className="w-80 rounded border border-accent bg-surface px-1.5 py-0.5 text-sm font-semibold text-ink focus:outline-none"
      />
    );
  }
  return (
    <h1 className="group flex items-center gap-1.5 truncate text-sm font-semibold text-ink">
      <button
        type="button"
        onClick={() => {
          setDraft(name);
          setEditing(true);
        }}
        title="Rename this engagement"
        className="truncate text-left hover:underline hover:decoration-line-strong"
      >
        {name}
      </button>
      <Pencil size={12} className="shrink-0 text-ink-faint opacity-0 group-hover:opacity-100" />
    </h1>
  );
}
