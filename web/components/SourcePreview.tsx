"use client";

/**
 * The uploaded file, as it was read — rows numbered the way Excel numbers them.
 *
 * This is where "where exactly did this finding come from?" gets answered: a
 * finding opens this at its own rows, highlighted, among their neighbours. The
 * file is shown as data in a table, never rendered as a document, so nothing in
 * a client's file can run in the browser.
 */

import { useEffect, useState } from "react";
import { ChevronLeft, ChevronRight, Download } from "lucide-react";
import { ApiError, api } from "@/lib/api";
import type { SourcePreview as Preview } from "@/lib/types";
import { Button, ErrorState, Modal, Spinner, cx } from "./ui";

const PAGE = 50;
/** Rows shown above a highlighted one, so it is seen in context. */
const CONTEXT = 8;
const FIRST_DATA_ROW = 2;

export function SourcePreview({
  engagementId,
  sourceId,
  filename,
  highlightRows = [],
  onClose,
}: {
  engagementId: string;
  sourceId: string;
  filename: string;
  highlightRows?: number[];
  onClose: () => void;
}) {
  const first = highlightRows.length ? Math.min(...highlightRows) : FIRST_DATA_ROW;
  const [offset, setOffset] = useState(Math.max(0, first - FIRST_DATA_ROW - CONTEXT));
  const [page, setPage] = useState<Preview | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    setError(null);
    api
      .preview(engagementId, sourceId, offset, PAGE)
      .then((result) => live && setPage(result))
      .catch((caught) =>
        live &&
        setError(caught instanceof ApiError ? caught.message : "The file could not be shown."),
      );
    return () => {
      live = false;
    };
  }, [engagementId, sourceId, offset]);

  const highlighted = new Set(highlightRows);
  const total = page?.total_rows ?? 0;
  const lastRow = Math.min(offset + PAGE, total) + FIRST_DATA_ROW - 1;

  return (
    <Modal
      wide
      title={filename}
      subtitle={
        highlightRows.length ? (
          <>
            Showing the {highlightRows.length === 1 ? "row" : "rows"} behind this finding,
            highlighted. Row numbers match the file when opened in Excel.
          </>
        ) : (
          "As uploaded, before CA-Guard mapped any column. Row numbers match Excel."
        )
      }
      onClose={onClose}
      footer={
        <div className="flex items-center justify-between gap-3">
          <span className="tabular text-[12px] text-ink-muted">
            {page
              ? `Rows ${(offset + FIRST_DATA_ROW).toLocaleString("en-IN")}–${lastRow.toLocaleString("en-IN")} of ${(total + 1).toLocaleString("en-IN")} (row 1 is the header)`
              : " "}
          </span>
          <div className="flex items-center gap-2">
            <Button
              variant="quiet"
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - PAGE))}
              title="Previous rows"
            >
              <ChevronLeft size={14} /> Previous
            </Button>
            <Button
              variant="quiet"
              disabled={!page || offset + PAGE >= total}
              onClick={() => setOffset(offset + PAGE)}
              title="Next rows"
            >
              Next <ChevronRight size={14} />
            </Button>
            <a href={api.originalUrl(engagementId, sourceId)} download>
              <Button title="Download the file exactly as it was uploaded">
                <Download size={14} /> Download original
              </Button>
            </a>
          </div>
        </div>
      }
    >
      {error ? (
        <div className="p-5">
          <ErrorState message={error} />
        </div>
      ) : !page ? (
        <div className="p-5">
          <Spinner label="Opening the file…" />
        </div>
      ) : (
        <table className="min-w-full border-separate border-spacing-0 text-[12px]">
          <thead className="sticky top-0 z-10 bg-canvas">
            <tr>
              <th className="sticky left-0 z-20 border-b border-line bg-canvas px-3 py-2 text-right font-medium text-ink-faint">
                Row
              </th>
              {page.columns.map((column) => (
                <th
                  key={column}
                  className="whitespace-nowrap border-b border-line px-3 py-2 text-left font-medium text-ink-muted"
                >
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {page.rows.map((row) => {
              const hit = highlighted.has(row.row);
              return (
                <tr
                  key={row.row}
                  ref={hit ? (node) => node?.scrollIntoView({ block: "center" }) : undefined}
                  className={cx(hit ? "bg-accent-soft" : "even:bg-canvas/40")}
                >
                  <td
                    className={cx(
                      "tabular sticky left-0 border-b border-line px-3 py-1.5 text-right",
                      hit ? "bg-accent-soft font-semibold text-accent" : "bg-surface text-ink-faint",
                    )}
                  >
                    {row.row.toLocaleString("en-IN")}
                  </td>
                  {row.values.map((value, index) => (
                    <td
                      key={index}
                      className="max-w-[22rem] truncate whitespace-nowrap border-b border-line px-3 py-1.5 text-ink"
                      title={value ?? ""}
                    >
                      {value ?? <span className="text-ink-faint">—</span>}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </Modal>
  );
}
