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

from caguard.money import format_inr
from caguard.review.decisions import Decision, ReviewAction
from caguard.review.engagement import Engagement
from caguard.review.finding import Finding, RiskBand

DISCLAIMER = (
    "CA-Guard prioritises transactions for professional review. The observations "
    "below are not conclusions, not allegations, and not accounting or legal "
    "advice. Every decision recorded here was made by the named reviewer."
)


@dataclass(frozen=True)
class ReportRow:
    """One finding as it appears in the report."""

    finding: Finding
    decision: Decision | None

    @property
    def status(self) -> str:
        return self.decision.action.value if self.decision else "not yet reviewed"

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
                "status": row.status,
                "reviewer": row.reviewer,
                "note": row.note,
            }
            for row in rows
        ]
    )


def to_csv(rows: list[ReportRow]) -> str:
    return to_frame(rows).to_csv(index=False)


def to_html(
    engagement: Engagement, rows: list[ReportRow], *, generated_at: datetime | None = None
) -> str:
    """A single self-contained HTML file: no external styles, fonts or scripts."""
    stamp = (generated_at or datetime.now(UTC)).strftime("%d-%m-%Y %H:%M UTC")
    tally = _tally(rows)

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>CA-Guard review — {html.escape(engagement.name)}</title>
<style>{_STYLES}</style></head>
<body>
<header>
  <h1>Review report</h1>
  <p class="sub">{html.escape(engagement.name)} · {html.escape(engagement.source_name)}</p>
  <dl class="meta">
    <div><dt>Entity</dt><dd>{html.escape(engagement.entity_id or "—")}</dd></div>
    <div><dt>Fiscal year</dt><dd>{html.escape(engagement.fiscal_year or "—")}</dd></div>
    <div><dt>Vouchers in ledger</dt><dd>{engagement.voucher_count:,}</dd></div>
    <div><dt>Flagged for review</dt><dd>{len(rows):,}</dd></div>
    <div><dt>Ledger fingerprint</dt><dd class="mono">{engagement.short_hash}</dd></div>
    <div><dt>Generated</dt><dd>{stamp}</dd></div>
  </dl>
  <p class="tally">{tally}</p>
</header>
<p class="disclaimer">{html.escape(DISCLAIMER)}</p>
<table>
  <thead><tr>
    <th>Voucher</th><th>Date</th><th class="num">Amount</th><th>Band</th>
    <th>Why it was flagged</th><th>Evidence</th><th>Decision</th>
  </tr></thead>
  <tbody>
{"".join(_row_html(row) for row in rows)}
  </tbody>
</table>
<footer>Produced by CA-Guard. Professional judgement remains with the reviewer.</footer>
</body></html>"""


def _row_html(row: ReportRow) -> str:
    finding = row.finding
    reasons = "".join(f"<li>{html.escape(reason)}</li>" for reason in finding.reasons)
    missing = ", ".join(finding.evidence.missing) or "complete"
    decision = (
        f'<span class="status {row.status.replace(" ", "-")}">{html.escape(row.status)}</span>'
        + (f'<div class="who">{html.escape(row.reviewer)}</div>' if row.reviewer else "")
        + (f'<div class="note">{html.escape(row.note)}</div>' if row.note else "")
    )
    return f"""    <tr class="band-{finding.band.value}">
      <td class="mono">{html.escape(finding.voucher_id)}</td>
      <td>{html.escape(_uk_date(finding.voucher_date))}</td>
      <td class="num">{html.escape(format_inr(finding.amount_paise))}</td>
      <td><span class="band {finding.band.value}">{finding.band.value}</span>
          <div class="pri">{finding.priority:.2f}</div></td>
      <td><ul>{reasons}</ul></td>
      <td>{finding.evidence.completeness:.0%}<div class="miss">{html.escape(missing)}</div></td>
      <td>{decision}</td>
    </tr>
"""


def _tally(rows: list[ReportRow]) -> str:
    bands = {band: sum(r.finding.band is band for r in rows) for band in RiskBand}
    states = {
        action: sum(r.decision is not None and r.decision.action is action for r in rows)
        for action in ReviewAction
    }
    outstanding = sum(r.decision is None for r in rows)
    band_text = " · ".join(f"{n} {b.value}" for b, n in bands.items() if n)
    state_text = " · ".join(f"{n} {a.value}ed" for a, n in states.items() if n)
    parts = [band_text] if band_text else []
    if state_text:
        parts.append(state_text)
    if outstanding:
        parts.append(f"{outstanding} not yet reviewed")
    return " — ".join(parts)


def _uk_date(iso: str) -> str:
    parts = iso.split("-")
    return f"{parts[2]}-{parts[1]}-{parts[0]}" if len(parts) == 3 else iso


_STYLES = """
:root{--ink:#16202c;--muted:#64748b;--line:#e2e8f0;--bg:#fff;
      --high:#b42318;--medium:#b54708;--low:#475467}
*{box-sizing:border-box}
body{margin:0;padding:32px;background:var(--bg);color:var(--ink);
     font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
h1{margin:0;font-size:22px;letter-spacing:-.01em}
.sub{margin:4px 0 18px;color:var(--muted)}
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
.status.not-yet-reviewed{color:var(--muted);font-weight:400}
footer{margin-top:22px;padding-top:12px;border-top:1px solid var(--line);
       color:var(--muted);font-size:12px}
@media print{body{padding:0}.meta{break-inside:avoid}tr{break-inside:avoid}}
"""
