"""The review report: what was flagged, what was decided, and why.

This is the artefact that leaves CA-Guard and goes into a working-paper file, so
it has to stand on its own months later. That means carrying the reasoning and
the evidence position for every finding — not just a list of voucher numbers —
and being explicit that these are observations rather than conclusions.

Two formats, both dependency-free. CSV goes into a spreadsheet; the HTML is a
single self-contained file with the styles inline, so it survives being emailed
or dropped into a folder with nothing alongside it.
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import UTC, datetime

import pandas as pd

from caguard import __version__
from caguard.money import format_inr
from caguard.review.decisions import DECISION_LABELS, Decision, ReviewAction
from caguard.review.engagement import Engagement
from caguard.review.finding import HIGH_THRESHOLD, MEDIUM_THRESHOLD, Finding, RiskBand
from caguard.review.store import SourceFile

DISCLAIMER = (
    "CA-Guard prioritises transactions for professional review. The observations "
    "below are not conclusions, not allegations, and not accounting or legal "
    "advice. Every decision recorded here was made by the named reviewer."
)

#: How the items in this report were selected — the SA 230 question "what was
#: tested, and why these?". Stated once, in words a file reviewer can follow.
SELECTION = (
    "Every voucher in the ledger was analysed. A voucher appears here when at least one "
    "review signal fired on it (rule-based, statistical, or — only in support of another — "
    "an anomaly model). Each is ranked by a priority that combines its signals and the "
    "gaps in its supporting evidence; bands are high from {high:.2f} and medium from "
    "{medium:.2f}. This is risk-based selection for review, not statistical sampling (SA 530)."
)


@dataclass(frozen=True)
class ReportRow:
    """One finding as it appears in the report."""

    finding: Finding
    decision: Decision | None

    @property
    def status(self) -> str:
        """The stored decision code, e.g. ``accept``. Stable for machines."""
        return self.decision.action.value if self.decision else "not yet reviewed"

    @property
    def status_label(self) -> str:
        """What a person reads, e.g. "Exception — follow up"."""
        return DECISION_LABELS[self.decision.action] if self.decision else "Not yet reviewed"

    @property
    def decided_at(self) -> str:
        if self.decision is None:
            return ""
        return self.decision.decided_at.strftime("%d-%m-%Y %H:%M UTC")

    @property
    def reviewer(self) -> str:
        return self.decision.reviewer if self.decision else ""

    @property
    def note(self) -> str:
        return (self.decision.note if self.decision else "") or ""


def build_rows(findings: list[Finding], decisions: dict[str, Decision]) -> list[ReportRow]:
    """Pair every finding with its latest decision, if there is one."""
    return [ReportRow(f, decisions.get(f.voucher_id)) for f in findings]


def to_frame(rows: list[ReportRow]) -> pd.DataFrame:
    """The report as a table, for CSV export or a spreadsheet."""
    return pd.DataFrame(
        [
            {
                "voucher_id": row.finding.voucher_id,
                "date": row.finding.voucher_date,
                "amount": format_inr(row.finding.amount_paise),
                "amount_paise": row.finding.amount_paise,
                "priority": round(row.finding.priority, 3),
                "band": row.finding.band.value,
                "concerns": "; ".join(k.value for k in row.finding.kinds),
                "reasons": " | ".join(row.finding.reasons),
                "evidence_completeness": row.finding.evidence.completeness,
                "evidence_missing": ", ".join(row.finding.evidence.missing),
                "source_lines": ", ".join(row.finding.line_ids),
                "reviewer_decision": row.status_label,
                "status_code": row.status,
                "reviewer": row.reviewer,
                "decided_at": row.decided_at,
                "note": row.note,
            }
            for row in rows
        ]
    )


def to_csv(rows: list[ReportRow]) -> str:
    """The report as CSV, safe to open in Excel.

    Every text cell that a spreadsheet would treat as a formula is neutralised.
    The cells come from a client's ledger (voucher numbers, narrations), from
    reviewers (notes) and from account holders (display names) — any of which
    could otherwise plant ``=HYPERLINK(...)`` or DDE that runs when a CA opens
    the export.
    """
    frame = to_frame(rows)
    for column in frame.columns:
        # pandas 3 stores text in its own string dtype, not ``object``; test
        # for both, or the check silently matches nothing.
        if frame[column].dtype == object or pd.api.types.is_string_dtype(frame[column]):
            frame[column] = frame[column].map(neutralise_formula)
    return frame.to_csv(index=False)


#: Characters that make a spreadsheet read a cell as a formula (OWASP CSV injection).
_FORMULA_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")


def neutralise_formula(value: object) -> object:
    """Prefix an apostrophe to text a spreadsheet would execute; leave the rest."""
    if not isinstance(value, str):
        return value
    if value.startswith(("\t", "\r")) or value.lstrip().startswith(_FORMULA_TRIGGERS):
        return "'" + value
    return value


def to_html(
    engagement: Engagement,
    rows: list[ReportRow],
    *,
    generated_at: datetime | None = None,
    generated_by: str = "",
    sources: list[SourceFile] | None = None,
) -> str:
    """A single self-contained HTML file: no external styles, fonts or scripts.

    Laid out so that what CA-Guard observed and what the reviewer decided are
    never mistaken for each other: they sit in separately headed column groups,
    and the header says how the items were selected and from which file.
    """
    stamp = (generated_at or datetime.now(UTC)).strftime("%d-%m-%Y %H:%M UTC")
    selection = SELECTION.format(high=HIGH_THRESHOLD, medium=MEDIUM_THRESHOLD)

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CA-Guard review — {html.escape(engagement.name)}</title>
<style>{_STYLES}</style></head>
<body>
<header>
  <p class="kicker">CA-Guard review report</p>
  <h1>{html.escape(engagement.name)}</h1>
  <dl class="meta">
    <div><dt>Entity</dt><dd>{html.escape(engagement.entity_id or "—")}</dd></div>
    <div><dt>Fiscal year</dt><dd>{html.escape(engagement.fiscal_year or "—")}</dd></div>
    <div><dt>Vouchers analysed</dt><dd>{engagement.voucher_count:,}</dd></div>
    <div><dt>Flagged for review</dt><dd>{len(rows):,}</dd></div>
    <div><dt>Generated</dt><dd>{stamp}</dd></div>
    <div><dt>Generated by</dt><dd>{html.escape(generated_by or "—")}</dd></div>
  </dl>
  {_sources_html(engagement, sources or [])}
  <h2>How these items were selected</h2>
  <p class="selection">{html.escape(selection)}</p>
  <p class="version">CA-Guard {html.escape(__version__)} · signal thresholds frozen in
  ADR-0004 · fusion weights in ADR-0006.</p>
  <h2>Where the review stands</h2>
  {_tally_html(rows)}
</header>
<p class="disclaimer">{html.escape(DISCLAIMER)}</p>
<table>
  <colgroup><col span="5"><col span="2" class="human"></colgroup>
  <thead>
    <tr class="groups">
      <th colspan="5">What CA-Guard observed</th>
      <th colspan="2" class="human">What the reviewer decided</th>
    </tr>
    <tr>
      <th>Voucher</th><th>Date</th><th class="num">Amount</th><th>Priority</th>
      <th>Why it was flagged · evidence</th>
      <th class="human">Decision</th><th class="human">Reviewer · note</th>
    </tr>
  </thead>
  <tbody>
{"".join(_row_html(row) for row in rows)}
  </tbody>
</table>
<footer>Produced by CA-Guard {html.escape(__version__)}. CA-Guard prioritises entries for
review; it does not issue audit opinions. Professional judgement remains with the
reviewer named against each decision.</footer>
</body></html>"""


def _sources_html(engagement: Engagement, sources: list[SourceFile]) -> str:
    """Which file the findings came from, with fingerprints that prove it."""
    if not sources:
        return (
            '<p class="source">Source ledger: '
            f"{html.escape(engagement.source_name)} · ledger fingerprint "
            f'<span class="mono">{html.escape(engagement.content_sha256)}</span></p>'
        )
    items = "".join(
        f"<li>{html.escape(s.filename)} — uploaded {s.uploaded_at:%d-%m-%Y %H:%M} UTC by "
        f"{html.escape(s.uploaded_by)}; {s.rows_used:,} of {s.rows_read:,} rows used; "
        f'SHA-256 <span class="mono">{html.escape(s.sha256)}</span>'
        + (
            f" <em>(file deleted {s.deleted_at:%d-%m-%Y} by {html.escape(s.deleted_by or '')})</em>"
            if s.deleted_at
            else ""
        )
        + "</li>"
        for s in sources
    )
    return (
        '<div class="source"><p>Source files (the original upload can be re-verified '
        "against its SHA-256):</p>"
        f"<ul>{items}</ul><p>Ledger content fingerprint: "
        f'<span class="mono">{html.escape(engagement.content_sha256)}</span></p></div>'
    )


def _row_html(row: ReportRow) -> str:
    finding = row.finding
    reasons = "".join(f"<li>{html.escape(reason)}</li>" for reason in finding.reasons)
    missing = ", ".join(finding.evidence.missing)
    evidence = (
        f'<div class="miss">Evidence {finding.evidence.completeness:.0%} complete'
        + (f" — no {html.escape(missing)}" if missing else "")
        + "</div>"
    )
    decision = (
        f'<span class="status {row.status.replace(" ", "-")}">'
        f"{html.escape(row.status_label)}</span>"
        + (f'<div class="when">{html.escape(row.decided_at)}</div>' if row.decided_at else "")
    )
    who = (f'<div class="who">{html.escape(row.reviewer)}</div>' if row.reviewer else "") + (
        f'<div class="note">{html.escape(row.note)}</div>' if row.note else ""
    )
    return f"""    <tr class="band-{finding.band.value}">
      <td class="mono">{html.escape(finding.voucher_id)}</td>
      <td>{html.escape(_uk_date(finding.voucher_date))}</td>
      <td class="num">{html.escape(format_inr(finding.amount_paise))}</td>
      <td><span class="band {finding.band.value}">{finding.band.value}</span>
          <div class="pri">{finding.priority:.2f}</div></td>
      <td><ul>{reasons}</ul>{evidence}</td>
      <td class="human">{decision}</td>
      <td class="human">{who or '<span class="none">—</span>'}</td>
    </tr>
"""


def _tally_html(rows: list[ReportRow]) -> str:
    bands = {band: sum(r.finding.band is band for r in rows) for band in RiskBand}
    states = {
        action: sum(r.decision is not None and r.decision.action is action for r in rows)
        for action in ReviewAction
    }
    outstanding = sum(r.decision is None for r in rows)
    band_text = " · ".join(f"{n:,} {b.value}" for b, n in bands.items() if n)
    decided = [f"{n:,} {DECISION_LABELS[a].lower()}" for a, n in states.items() if n]
    if outstanding:
        decided.append(f"{outstanding:,} not yet reviewed")
    return (
        f'<p class="tally">By priority: {band_text or "none"}.<br>'
        f"By decision: {' · '.join(decided) or 'none'}.</p>"
    )


def _uk_date(iso: str) -> str:
    parts = iso.split("-")
    return f"{parts[2]}-{parts[1]}-{parts[0]}" if len(parts) == 3 else iso


_STYLES = """
:root{--ink:#16202c;--muted:#64748b;--line:#e2e8f0;--bg:#fff;
      --high:#b42318;--medium:#b54708;--low:#475467}
*{box-sizing:border-box}
body{margin:0;padding:32px;background:var(--bg);color:var(--ink);
     font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
h1{margin:0 0 14px;font-size:22px;letter-spacing:-.01em}
h2{margin:18px 0 6px;font-size:12px;text-transform:uppercase;letter-spacing:.05em;
   color:var(--muted)}
.kicker{margin:0 0 2px;color:var(--muted);font-size:12px;text-transform:uppercase;
        letter-spacing:.05em}
.source,.selection,.version{color:var(--ink);font-size:13px;margin:6px 0}
.source ul{margin:4px 0}
.version{color:var(--muted);font-size:12px}
.groups th{border-bottom:1px solid var(--line);font-size:11px;color:var(--ink)}
th.human,td.human{background:#f6f8fb}
.when{color:var(--muted);font-size:11px;margin-top:2px}
.none{color:var(--muted)}
.meta{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
      gap:12px;margin:0 0 14px;padding:14px;border:1px solid var(--line);border-radius:8px}
.meta div{margin:0}
dt{font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}
dd{margin:2px 0 0;font-weight:600}
.tally{margin:0 0 18px;color:var(--muted)}
.disclaimer{padding:10px 12px;border-left:3px solid var(--medium);
            background:#fffaf0;color:#7a4a08;border-radius:0 6px 6px 0;margin:0 0 18px}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;padding:8px;border-bottom:2px solid var(--line);
   font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}
td{padding:10px 8px;border-bottom:1px solid var(--line);vertical-align:top}
.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px}
ul{margin:0;padding-left:16px}
li{margin-bottom:3px}
.band{display:inline-block;padding:1px 7px;border-radius:99px;font-size:11px;
      font-weight:700;text-transform:uppercase;letter-spacing:.03em}
.band.high{background:#fef3f2;color:var(--high)}
.band.medium{background:#fffaeb;color:var(--medium)}
.band.low{background:#f2f4f7;color:var(--low)}
.pri{color:var(--muted);font-size:11px;margin-top:3px}
.miss,.who,.note{color:var(--muted);font-size:12px;margin-top:3px}
.status{font-weight:600}
.status.accept{color:var(--high)}
.status.reject{color:#067647}
.status.investigate{color:#6941c6}
.status.not-yet-reviewed{color:var(--muted);font-weight:400}
footer{margin-top:22px;padding-top:12px;border-top:1px solid var(--line);
       color:var(--muted);font-size:12px}
@media print{body{padding:0;font-size:11px}.meta{break-inside:avoid}tr{break-inside:avoid}
  thead{display:table-header-group}th.human,td.human{background:none}
  .disclaimer{background:none}}
"""
