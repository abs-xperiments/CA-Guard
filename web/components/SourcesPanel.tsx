"use client";

/**
 * Every file uploaded to this engagement, and what became of it.
 *
 * The reviewer should never have to wonder where their ledger went. Each file
 * shows what it was, who brought it in and how much of it was used, with the
 * exact original one click away. Deleting is deliberate — two steps, and only
 * for an administrator — because it cannot be undone.
 */

import { useCallback, useEffect, useState } from "react";
import { Download, Eye, FileSpreadsheet, Trash2 } from "lucide-react";
import { ApiError, api } from "@/lib/api";
import type { SourceFile } from "@/lib/types";
import { fileSize, whenIST } from "@/lib/types";
import { SourcePreview } from "./SourcePreview";
import { useToast } from "./Toast";
import { Button, EmptyState, ErrorState, Modal, Spinner } from "./ui";

export function SourcesPanel({
  engagementId,
  canDelete,
  onClose,
}: {
  engagementId: string;
  canDelete: boolean;
  onClose: () => void;
}) {
  const toast = useToast();
  const [sources, setSources] = useState<SourceFile[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [previewing, setPreviewing] = useState<SourceFile | null>(null);
  const [confirming, setConfirming] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setSources(await api.sources(engagementId));
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not list the files.");
    }
  }, [engagementId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function remove(source: SourceFile) {
    try {
      await api.deleteSource(engagementId, source.id);
      toast.show({
        tone: "success",
        message: `Deleted ${source.filename}`,
        detail: "The file is deleted from CA-Guard’s storage. Decisions already recorded are kept.",
      });
      setConfirming(null);
      await load();
    } catch (caught) {
      toast.show({
        tone: "error",
        message: "The file was not deleted",
        detail: caught instanceof ApiError ? caught.message : "Nothing has changed.",
      });
    }
  }

  if (previewing) {
    return (
      <SourcePreview
        engagementId={engagementId}
        sourceId={previewing.id}
        filename={previewing.filename}
        onClose={() => setPreviewing(null)}
      />
    );
  }

  return (
    <Modal
      title="Source documents"
      subtitle="The files this review was built from, kept exactly as they were uploaded."
      onClose={onClose}
    >
      <div className="p-5">
        {error ? (
          <ErrorState message={error} retry={() => void load()} />
        ) : !sources ? (
          <Spinner label="Loading files…" />
        ) : sources.length === 0 ? (
          <EmptyState
            title="No stored files"
            detail="This engagement was opened before CA-Guard kept original files. Upload the ledger again to store it; decisions already recorded are kept."
          />
        ) : (
          <ul className="space-y-3">
            {sources.map((source) => (
              <li key={source.id} className="rounded-md border border-line px-4 py-3">
                <div className="flex items-start gap-3">
                  <FileSpreadsheet size={18} className="mt-0.5 shrink-0 text-ink-faint" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold text-ink">{source.filename}</p>
                    <p className="mt-0.5 text-[12px] text-ink-muted">
                      {source.file_type} · {fileSize(source.size_bytes)} · uploaded{" "}
                      {whenIST(source.uploaded_at)} by {source.uploaded_by}
                    </p>
                    <p className="tabular mt-0.5 text-[12px] text-ink-muted">
                      {source.rows_used.toLocaleString("en-IN")} of{" "}
                      {source.rows_read.toLocaleString("en-IN")} rows used ·{" "}
                      <span className="font-mono" title={`SHA-256 ${source.sha256}`}>
                        fingerprint {source.sha256.slice(0, 12)}
                      </span>
                    </p>
                    {source.deleted_at ? (
                      <p className="mt-1 text-[12px] font-medium text-high">
                        Deleted {whenIST(source.deleted_at)} by {source.deleted_by}
                      </p>
                    ) : null}
                  </div>
                </div>

                {source.available ? (
                  <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-line pt-3">
                    <Button onClick={() => setPreviewing(source)} title="Look through the file">
                      <Eye size={14} /> View
                    </Button>
                    <a href={api.originalUrl(engagementId, source.id)} download>
                      <Button title="Download the file exactly as it was uploaded">
                        <Download size={14} /> Download original
                      </Button>
                    </a>
                    {canDelete ? (
                      confirming === source.id ? (
                        <span className="ml-auto flex items-center gap-2">
                          <span className="text-[12px] text-high">
                            Delete permanently? This cannot be undone.
                          </span>
                          <Button variant="danger" onClick={() => void remove(source)}>
                            Delete
                          </Button>
                          <Button variant="quiet" onClick={() => setConfirming(null)}>
                            Keep
                          </Button>
                        </span>
                      ) : (
                        <span className="ml-auto">
                          <Button
                            variant="quiet"
                            onClick={() => setConfirming(source.id)}
                            title="Delete this file from CA-Guard’s storage"
                          >
                            <Trash2 size={14} /> Delete
                          </Button>
                        </span>
                      )
                    ) : null}
                  </div>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </div>
    </Modal>
  );
}
