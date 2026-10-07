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
    from caguard.intake.coerce import to_canonical_types
    from caguard.intake.readers import IntakeError, read_table
    from caguard.intake.validation import build_vouchers, frame_to_records, validate_lines

    try:
        frame = read_table(path)
    except IntakeError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from exc

    typer.echo(f"Read {len(frame):,} rows from {path.name}")
    canonical = adapt(frame) if vynfi else to_canonical_types(frame)

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
    from caguard.intake.coerce import to_canonical_types
    from caguard.intake.readers import IntakeError, read_table
    from caguard.money import format_inr

    try:
        frame = read_table(path)
    except IntakeError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from exc

    canonical = adapt(frame) if vynfi else to_canonical_types(frame)
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


@app.command()
def analyse(
    path: Annotated[Path, typer.Argument(help="Ledger file (.csv/.xlsx/.parquet)")],
    vynfi: Annotated[bool, typer.Option("--vynfi", help="Treat input as the VynFi corpus")] = False,
) -> None:
    """Run all three layers separately and report what each contributes.

    Rules, statistics and the model are shown side by side rather than blended.
    Combining them into one score is Phase 4; seeing them apart is what tells a
    reviewer whether the model is earning its place on their data.
    """
    from caguard.adapters.vynfi import adapt
    from caguard.detect.statistics import benford_by_account
    from caguard.evaluation.baselines import build_approaches
    from caguard.intake.coerce import to_canonical_types
    from caguard.intake.readers import IntakeError, read_table

    try:
        frame = read_table(path)
    except IntakeError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from exc

    canonical = adapt(frame) if vynfi else to_canonical_types(frame)
    context, approaches = build_approaches(canonical)
    total = len(context)

    typer.echo(f"\n{total:,} vouchers\n")
    typer.echo(f"  {'approach':20s} {'flagged':>9s} {'share':>8s}")
    for name in ("rules", "statistics", "model", "all"):
        found = approaches[name]
        typer.echo(f"  {name:20s} {len(found):9,} {len(found) / total:8.1%}")

    only_model = approaches["model"] - approaches["rules"]
    typer.echo(
        f"\n  The model flags {len(only_model):,} vouchers the rules do not. "
        "On the project benchmark these are statistically unusual but legitimate; "
        "on your data, check a sample before trusting them."
    )

    benford = [r for r in benford_by_account(context) if r.conformity == "non-conforming"]
    if benford:
        typer.echo("\n  Accounts not conforming to Benford's law:")
        for result in benford[:5]:
            typer.echo(f"    {result.summary()}")


@app.command()
def review(
    path: Annotated[Path, typer.Argument(help="Ledger file (.csv/.xlsx/.parquet)")],
    vynfi: Annotated[bool, typer.Option("--vynfi", help="Treat input as the VynFi corpus")] = False,
    approval_limit: Annotated[
        int, typer.Option(help="Delegation-of-authority limit in rupees (firm-specific)")
    ] = 50_000,
    top: Annotated[int, typer.Option(help="How many findings to show")] = 10,
    weights: Annotated[bool, typer.Option("--weights", help="Print the weight table")] = False,
) -> None:
    """Build the prioritised review queue, highest priority first.

    Every finding shows its priority, the concerns behind it, how complete its
    evidence trail is, and the ledger lines it came from — so the ranking can be
    argued with rather than taken on trust.
    """
    from caguard.adapters.vynfi import adapt
    from caguard.detect.types import DetectorConfig
    from caguard.intake.coerce import to_canonical_types
    from caguard.intake.readers import IntakeError, read_table
    from caguard.money import format_inr
    from caguard.review.finding import RiskBand
    from caguard.review.fusion import build_findings, explain_weights

    if weights:
        typer.echo("\nSignal weights (frozen in ADR-0006):\n")
        typer.echo(explain_weights())
        typer.echo("")

    try:
        frame = read_table(path)
    except IntakeError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from exc

    canonical = adapt(frame) if vynfi else to_canonical_types(frame)
    config = DetectorConfig(approval_limit_paise=approval_limit * 100)
    findings = build_findings(canonical, config)

    total = canonical["voucher_id"].nunique()
    bands = {band: sum(f.band is band for f in findings) for band in RiskBand}
    typer.echo(
        f"\n{len(findings):,} of {total:,} vouchers need review "
        f"({len(findings) / total:.1%})   "
        f"high {bands[RiskBand.HIGH]} · medium {bands[RiskBand.MEDIUM]} · "
        f"low {bands[RiskBand.LOW]}\n"
    )

    colours = {
        RiskBand.HIGH: typer.colors.RED,
        RiskBand.MEDIUM: typer.colors.YELLOW,
        RiskBand.LOW: typer.colors.WHITE,
    }
    for finding in findings[:top]:
        typer.secho(
            f"  [{finding.band.value.upper():6s}] {finding.voucher_id}  "
            f"{format_inr(finding.amount_paise):>18s}  {finding.voucher_date}  "
            f"priority {finding.priority:.2f}",
            fg=colours[finding.band],
            bold=finding.band is RiskBand.HIGH,
        )
        for reason in finding.reasons:
            typer.echo(f"        · {reason}")
        typer.echo(
            f"        evidence {finding.evidence.completeness:.0%} — {finding.evidence.summary()}"
        )
        typer.echo(f"        lines: {', '.join(finding.line_ids)}")
        typer.echo("")


@app.command()
def explain(
    path: Annotated[Path, typer.Argument(help="Ledger file (.csv/.xlsx/.parquet)")],
    top: Annotated[int, typer.Option(help="How many findings to explain")] = 3,
    model: Annotated[
        str, typer.Option(help="Local Ollama model tag, or 'none' for no model")
    ] = "none",
) -> None:
    """Explain the top findings in plain language.

    Works with no model installed — that is the normal configuration, not a
    degraded one. When a local model is used, its output is checked against the
    finding's own facts before it is shown, and rejected text is replaced by
    CA-Guard's own wording.
    """
    from caguard.explain.ollama import OllamaProvider
    from caguard.explain.service import ExplanationService
    from caguard.intake.coerce import to_canonical_types
    from caguard.intake.readers import IntakeError, read_table
    from caguard.review.fusion import build_findings

    try:
        frame = read_table(path)
    except IntakeError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from exc

    provider = None if model == "none" else OllamaProvider(model=model)
    service = ExplanationService(provider)
    findings = build_findings(to_canonical_types(frame))

    if provider is not None and not provider.available():
        typer.secho(
            f"  {provider.name} is not available; using CA-Guard's own wording.",
            fg=typer.colors.YELLOW,
        )

    for finding in findings[:top]:
        result = service.explain(finding)
        typer.secho(f"\n{'─' * 72}", fg=typer.colors.BRIGHT_BLACK)
        typer.echo(result.text)
        typer.secho(
            f"\n  {result.provenance()}  [{result.latency_seconds:.2f}s]",
            fg=typer.colors.BRIGHT_BLACK,
        )


@app.command()
def serve(
    host: Annotated[str, typer.Option(help="Bind address. Loopback only.")] = "127.0.0.1",
    port: Annotated[int, typer.Option(help="Port to listen on")] = 8000,
    store: Annotated[Path, typer.Option(help="Where review decisions are kept")] = Path(
        "data/review.db"
    ),
    model: Annotated[
        str, typer.Option(help="Local model tag, or 'none' for CA-Guard's own wording")
    ] = "none",
) -> None:
    """Run the review workspace API on this machine.

    Loopback only. A client's ledger must not appear on the office network
    because a bind address was mistyped, so a non-local host is refused rather
    than warned about.
    """
    import uvicorn

    from caguard.api.app import create_app
    from caguard.explain.ollama import NotLocalError, require_loopback

    try:
        require_loopback(f"http://{host}:{port}", purpose="serve the workspace")
    except NotLocalError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from exc

    typer.secho(f"\n  CA-Guard workspace  →  http://{host}:{port}", fg=typer.colors.GREEN)
    typer.echo(f"  API docs            →  http://{host}:{port}/docs")
    typer.echo(f"  decisions stored in →  {store}")
    typer.echo(f"  explanation model   →  {model}\n")
    from caguard.observability import configure_logging

    configure_logging()
    uvicorn.run(create_app(store, model=model), host=host, port=port, log_level="warning")


@app.command()
def export(
    path: Annotated[Path, typer.Argument(help="Ledger file to analyse")],
    out: Annotated[Path, typer.Option(help="Where to write the report")] = Path(
        "review-report.html"
    ),
    store: Annotated[Path, typer.Option(help="Review decisions database")] = Path("data/review.db"),
) -> None:
    """Write a review report, including any decisions already recorded."""
    from caguard.api.app import load_ledger
    from caguard.intake.readers import IntakeError
    from caguard.review.engagement import open_engagement
    from caguard.review.fusion import build_findings
    from caguard.review.report import build_rows, to_csv, to_html
    from caguard.review.store import ReviewStore

    try:
        lines = load_ledger(path)
    except IntakeError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from exc

    reviews = ReviewStore(store)
    engagement = reviews.open_engagement(open_engagement(lines, source=path))
    rows = build_rows(build_findings(lines), reviews.current(engagement.id))

    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix.lower() == ".csv":
        out.write_text(to_csv(rows))
    else:
        out.write_text(to_html(engagement, rows))

    reviewed = sum(1 for row in rows if row.decision is not None)
    typer.echo(f"Wrote {len(rows):,} findings ({reviewed:,} reviewed) to {out}")


@app.command()
def benchmark(
    out: Annotated[Path | None, typer.Option(help="Write the results markdown here")] = None,
    vouchers: Annotated[int, typer.Option(help="Ledger size per seed")] = 4000,
    seeds: Annotated[
        str, typer.Option(help="Comma-separated held-out seeds")
    ] = "101,102,103,104,105",
) -> None:
    """Regenerate every number this project claims.

    Runs held-out seeds against frozen thresholds and prints what it finds.
    There is deliberately no option that improves the result: a benchmark you
    can adjust is one that will be adjusted.
    """
    from caguard.evaluation.benchmark import TuningSeedError, as_markdown
    from caguard.evaluation.benchmark import run as run_benchmark

    chosen = tuple(int(value) for value in seeds.split(",") if value.strip())
    typer.echo(f"\nRunning {len(chosen)} held-out seeds at {vouchers:,} vouchers each…\n")

    try:
        result = run_benchmark(seeds=chosen, vouchers=vouchers)
    except TuningSeedError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from exc

    typer.echo(result.signals.to_string())
    typer.echo("")
    typer.echo(result.approaches.to_string())
    typer.echo("")
    typer.echo(result.ranking.to_string())
    typer.echo("")
    typer.secho(
        f"  Trap false positives: {int(result.signals.trap_false_positives.sum())}",
        fg=typer.colors.GREEN,
    )
    typer.secho(
        f"  Anomalies the model found that the rules missed: {result.model_unique_finds}",
        fg=typer.colors.GREEN if result.model_adds_nothing else typer.colors.YELLOW,
    )
    typer.echo(f"  Fingerprint: {result.fingerprint()}")

    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(as_markdown(result))
        typer.echo(f"\n  Wrote {out}")


if __name__ == "__main__":
    app()
