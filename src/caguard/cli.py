"""Command line entry points.

Deliberately thin: every command is a few lines of orchestration over library
functions, so that anything worth testing is testable without invoking a CLI.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

app = typer.Typer(
    add_completion=False,
    help="CA-Guard — private financial review tooling for Indian CAs.",
)


@app.command()
def generate(
    out: Annotated[Path, typer.Option(help="Directory to write the ledger into")] = Path(
        "data/generated"
    ),
    seed: Annotated[
        int, typer.Option(help="Fixed seed; the same seed reproduces the ledger")
    ] = 20250906,
    vouchers: Annotated[int, typer.Option(help="Number of vouchers to generate")] = 4000,
    anomaly_rate: Annotated[float, typer.Option(help="Planted anomaly rate (0.01-0.03)")] = 0.02,
) -> None:
    """Generate a reproducible synthetic Indian ledger with planted ground truth.

    Writes three files: the ledger, the ground truth, and a manifest carrying the
    content hash. The ground truth is a separate file on purpose — no detector
    may read it (ADR-0003).
    """
    from caguard.benchmark.generator import GeneratorConfig
    from caguard.benchmark.generator import generate as run

    cfg = GeneratorConfig(seed=seed, n_vouchers=vouchers, anomaly_rate=anomaly_rate)
    ledger = run(cfg)

    out.mkdir(parents=True, exist_ok=True)
    stem = f"{cfg.entity_id.lower()}_{cfg.fiscal_year.lower()}_seed{seed}"
    ledger.lines.to_parquet(out / f"{stem}.parquet", index=False)
    ledger.truth.write(out / f"{stem}.truth.json")
    (out / f"{stem}.manifest.json").write_text(json.dumps(ledger.manifest, indent=2))

    facts = ledger.manifest
    typer.echo(f"Wrote {facts['lines']:,} lines / {facts['vouchers']:,} vouchers")
    typer.echo(
        f"  anomalous: {facts['anomalous_vouchers']} ({facts['anomaly_rate']:.1%})"
        f"   decoys: {facts['decoy_vouchers']}"
    )
    typer.echo(f"  sha256:    {str(facts['content_sha256'])[:16]}…")
    typer.echo(f"  -> {out / stem}.{{parquet,truth.json,manifest.json}}")


@app.command()
def ingest(
    path: Annotated[Path, typer.Argument(help="Ledger file (.csv/.xlsx/.parquet)")],
    vynfi: Annotated[bool, typer.Option("--vynfi", help="Treat input as the VynFi corpus")] = False,
    show: Annotated[int, typer.Option(help="How many row errors to print")] = 10,
) -> None:
    """Read a ledger, convert it to the canonical schema, and report data quality."""
    from caguard.adapters.vynfi import adapt
    from caguard.intake.readers import IntakeError, read_table
    from caguard.intake.validation import build_vouchers, frame_to_records, validate_lines

    try:
        frame = read_table(path)
    except IntakeError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from exc

    typer.echo(f"Read {len(frame):,} rows from {path.name}")
    canonical = adapt(frame) if vynfi else frame

    report = validate_lines(frame_to_records(canonical))
    typer.echo(report.summary())
    for err in report.errors[:show]:
        typer.echo(f"  {err}")

    vouchers, rejected = build_vouchers(report.lines)
    typer.echo(f"{len(vouchers):,} balanced vouchers; {len(rejected):,} rejected as unbalanced")


@app.command()
def columns(
    path: Annotated[Path, typer.Argument(help="Ledger file to inspect")],
) -> None:
    """Show how a file's headers map onto the canonical schema."""
    from caguard.intake.mapping import explain_ambiguity, infer_mapping
    from caguard.intake.readers import IntakeError, read_table

    try:
        frame = read_table(path)
    except IntakeError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from exc

    mapping = infer_mapping(list(frame.columns))
    for header, canonical in sorted(mapping.resolved.items()):
        typer.echo(f"  {header:32s} -> {canonical}")
    for header, options in sorted(mapping.ambiguous.items()):
        note = explain_ambiguity(header)
        typer.secho(
            f"  {header:32s} -> AMBIGUOUS {options}" + (f"  ({note})" if note else ""),
            fg=typer.colors.YELLOW,
        )
    if mapping.unmapped:
        typer.echo(f"  unmapped: {', '.join(mapping.unmapped)}")
    if mapping.missing_required:
        typer.secho(f"Missing required: {', '.join(mapping.missing_required)}", fg=typer.colors.RED)
    else:
        typer.secho("Mapping is usable.", fg=typer.colors.GREEN)


@app.command()
def detect(
    path: Annotated[Path, typer.Argument(help="Ledger file (.csv/.xlsx/.parquet)")],
    vynfi: Annotated[bool, typer.Option("--vynfi", help="Treat input as the VynFi corpus")] = False,
    approval_limit: Annotated[
        int, typer.Option(help="Delegation-of-authority limit in rupees (firm-specific)")
    ] = 50_000,
    top: Annotated[int, typer.Option(help="How many findings to show")] = 15,
) -> None:
    """Run the audit-review signals over a ledger and print the review queue.

    Signals are reported separately, never blended into one number — a reviewer
    needs to see which concern fired, not a score they cannot argue with.
    """
    from caguard.adapters.vynfi import adapt
    from caguard.detect import DetectorConfig, run_signals
    from caguard.detect.runner import count_by_kind, group_by_voucher
    from caguard.intake.readers import IntakeError, read_table
    from caguard.money import format_inr

    try:
        frame = read_table(path)
    except IntakeError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from exc

    canonical = adapt(frame) if vynfi else frame
    config = DetectorConfig(approval_limit_paise=approval_limit * 100)
    hits = run_signals(canonical, config)
    grouped = group_by_voucher(hits)

    total = canonical["voucher_id"].nunique()
    typer.echo(
        f"\n{len(grouped):,} of {total:,} vouchers flagged "
        f"({len(grouped) / total:.1%}) — approval limit {format_inr(config.approval_limit_paise)}\n"
    )
    for kind, count in sorted(count_by_kind(hits).items(), key=lambda kv: -kv[1]):
        if count:
            typer.echo(f"  {kind.value:28s} {count:6,}")

    ranked = sorted(grouped.items(), key=lambda kv: -sum(h.strength for h in kv[1]))
    typer.echo(f"\nTop {min(top, len(ranked))} for review:\n")
    for voucher_id, voucher_hits in ranked[:top]:
        concerns = ", ".join(sorted(h.kind.value for h in voucher_hits))
        typer.secho(f"  {voucher_id}  [{concerns}]", fg=typer.colors.YELLOW)
        for hit in voucher_hits:
            typer.echo(f"      {hit.reason}")


if __name__ == "__main__":
    app()
