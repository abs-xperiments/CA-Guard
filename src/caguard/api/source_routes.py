"""The uploaded files: list them, download the exact original, preview, delete.

Answers the two questions a reviewer should never have to ask: "where did my
ledger go?" and "which file did this finding come from?".

Every route checks that the file belongs to the engagement in the URL, so an id
from one engagement cannot be used to reach another's file. The original is
re-hashed before it is sent, so what is downloaded is provably what was
uploaded.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from caguard.api.models import PreviewOut, PreviewRowOut, SourceFileOut
from caguard.api.workspace import Workspace
from caguard.auth.users import User
from caguard.intake.normalise import FIRST_DATA_ROW
from caguard.intake.readers import IntakeError, read_table
from caguard.observability import event
from caguard.review.sources import SourceIntegrityError
from caguard.review.store import SourceFile

logger = logging.getLogger("caguard.api")

#: Rows returned per preview request. A page, not the ledger.
MAX_PREVIEW_ROWS = 200

_MEDIA_TYPES = {
    ".csv": "text/csv",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
    ".parquet": "application/vnd.apache.parquet",
}


def build_source_router(workspace: Workspace, signed_in: Any) -> APIRouter:
    """Routes for an engagement's files. ``signed_in`` is the app's session dependency."""
    router = APIRouter(prefix="/api/engagements/{engagement_id}/sources", tags=["sources"])

    def owned(engagement_id: str, source_id: str) -> SourceFile:
        source = workspace.store.source(source_id)
        if source is None or source.engagement_id != engagement_id:
            raise HTTPException(404, "There is no such file in this engagement.")
        return source

    @router.get("", response_model=list[SourceFileOut])
    def list_sources(engagement_id: str, user: User = signed_in) -> list[SourceFileOut]:
        if workspace.store.engagement(engagement_id) is None:
            raise HTTPException(404, "There is no such engagement.")
        return [
            SourceFileOut.build(s, available=workspace.vault.exists(s.sha256, s.suffix))
            for s in workspace.store.sources(engagement_id, include_deleted=True)
        ]

    @router.get("/{source_id}/original")
    def download_original(
        engagement_id: str, source_id: str, user: User = signed_in
    ) -> FileResponse:
        """The file exactly as it was uploaded — verified, never regenerated."""
        source = owned(engagement_id, source_id)
        if source.is_deleted:
            raise HTTPException(410, f"{source.filename} was deleted and cannot be downloaded.")
        try:
            path = workspace.vault.verified_path(source.sha256, source.suffix)
        except FileNotFoundError as exc:
            raise HTTPException(410, f"The stored copy of {source.filename} is missing.") from exc
        except SourceIntegrityError as exc:
            event(logger, "source.download_refused", logging.ERROR, source=source.id)
            raise HTTPException(
                409,
                f"The stored copy of {source.filename} no longer matches what was uploaded, "
                "so it is not being sent. Upload the original again.",
            ) from exc

        event(logger, "source.downloaded", source=source.id, user=user.id)
        return FileResponse(
            path,
            media_type=_MEDIA_TYPES.get(source.suffix, "application/octet-stream"),
            filename=_download_name(source),
            headers={
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "no-store",
                # Lets anyone holding the download check it against the record.
                "X-Content-SHA256": source.sha256,
            },
        )

    @router.get("/{source_id}/preview", response_model=PreviewOut)
    def preview(
        engagement_id: str,
        source_id: str,
        offset: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=MAX_PREVIEW_ROWS),
        user: User = signed_in,
    ) -> PreviewOut:
        """A page of the file as it was read, with spreadsheet row numbers.

        Served as data, never as the file itself, so nothing in a client's file
        is ever rendered by the browser as markup.
        """
        source = owned(engagement_id, source_id)
        if source.is_deleted:
            raise HTTPException(410, f"{source.filename} was deleted.")
        raw = _raw_for(workspace, engagement_id, source)

        window = raw.iloc[offset : offset + limit]
        rows = [
            PreviewRowOut(row=int(index) + FIRST_DATA_ROW, values=[_cell(v) for v in values])
            for index, values in zip(window.index, window.itertuples(index=False), strict=True)
        ]
        return PreviewOut(
            source_id=source.id,
            filename=source.filename,
            columns=[str(c) for c in raw.columns],
            rows=rows,
            total_rows=len(raw),
            offset=offset,
        )

    @router.delete("/{source_id}", response_model=SourceFileOut)
    def delete_source(engagement_id: str, source_id: str, user: User = signed_in) -> SourceFileOut:
        """Delete a stored original. The record and the decision trail remain."""
        if not user.is_admin:
            raise HTTPException(403, "Only an administrator can delete original files.")
        source = owned(engagement_id, source_id)
        updated = workspace.store.mark_source_deleted(source.id, user.display_name) or source
        if not workspace.store.sha_still_referenced(source.sha256):
            workspace.vault.remove(source.sha256, source.suffix)
        if not workspace.store.sources(engagement_id):
            # Nothing left to analyse from; the next open says so plainly.
            workspace.forget(engagement_id)
        event(logger, "source.deleted", source=source.id, user=user.id)
        return SourceFileOut.build(updated, available=False)

    return router


def _raw_for(workspace: Workspace, engagement_id: str, source: SourceFile) -> pd.DataFrame:
    analysis = workspace.require(engagement_id)
    if analysis.raw is not None and analysis.source is not None and analysis.source.id == source.id:
        return analysis.raw
    # Another upload of the same book (say, the .xlsx beside the .csv).
    try:
        path = workspace.vault.verified_path(source.sha256, source.suffix)
        return read_table(path, display_name=source.filename)
    except (FileNotFoundError, SourceIntegrityError, IntakeError) as exc:
        raise HTTPException(410, f"{source.filename} cannot be previewed.") from exc


def _download_name(source: SourceFile) -> str:
    """The user's own filename, made safe for a response header."""
    stem = re.sub(r"[^\w .()\-]", "_", source.filename).strip() or "ledger"
    return stem if stem.lower().endswith(source.suffix) else f"{stem}{source.suffix}"


def _cell(value: object) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return str(value)
