"""Typer-based command line interface for the redaction pipeline.

The ``run`` command executes the full redaction workflow for plain text files
and is intentionally minimal: read and normalize the input, detect entities,
link/merge spans, build and apply a replacement plan, verify residual PII and
optionally emit an audit bundle.  Heavy dependencies such as spaCy are imported
on demand so that basic invocations remain lightweight.

Exit codes
----------
0 success
3 I/O error (missing reader/writer, filesystem issues)
4 configuration error
5 pipeline error (unexpected exception during detection/link/replace)
6 verification failure (strict mode with residuals > 0)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from time import perf_counter
from types import TracebackType
from typing import Optional

import typer
from pydantic import ValidationError

from .config import ConfigModel, load_config
from .detect.base import DetectionContext, Detector, EntitySpan
from .io import read_file, write_file
from .link import alias_resolver, coref, span_merger
from .preprocess import layout_reconstructor
from .preprocess.normalizer import normalize
from .replace.applier import apply_plan
from .replace.plan_builder import build_replacement_plan
from .utils.errors import UnsupportedFormatError
from .utils.textspan import build_line_starts
from .verify import report as verify_report
from .verify import scanner

if not sys.stdout.isatty():  # pragma: no cover - CLI test context
    os.environ.setdefault("NO_COLOR", "1")
    os.environ.setdefault("RICH_DISABLE_NO_COLOR", "1")

app = typer.Typer(
    name="redactor",
    help="Utilities for the redaction pipeline. Use 'redactor run' to execute the pipeline.",
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _safe_exit(code: int, msg: str | None = None) -> None:
    """Exit the CLI with ``code`` emitting ``msg`` to stderr if provided."""

    if msg:
        typer.echo(msg, err=True)
    raise typer.Exit(code)


def _apply_overrides(
    cfg: ConfigModel,
    *,
    keep_roles: bool | None,
    enable_ner: bool | None,
    enable_coref: bool | None,
    coref_backend: str | None,
) -> ConfigModel:
    """Return a copy of ``cfg`` with CLI overrides applied."""

    new_cfg = cfg.model_copy(deep=True)
    if keep_roles is not None:
        new_cfg.redact.alias_labels = "keep_roles" if keep_roles else "redact"
    if enable_ner is not None:
        new_cfg.detectors.ner.enabled = enable_ner
    if enable_coref is not None:
        new_cfg.detectors.coref.enabled = enable_coref
    if coref_backend is not None:
        new_cfg.detectors.coref.backend = coref_backend  # type: ignore[assignment]
    return new_cfg


class Timing:
    """Context manager measuring elapsed milliseconds."""

    def __init__(self) -> None:
        self._start = 0.0
        self._end = 0.0

    def __enter__(self) -> "Timing":
        self._start = perf_counter()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._end = perf_counter()

    @property
    def ms(self) -> float:
        return (self._end - self._start) * 1000.0


def _run_detectors(text: str, cfg: ConfigModel, context: DetectionContext) -> list[EntitySpan]:
    """Instantiate and run detectors returning detected spans."""

    from .detect.account_ids import AccountIdDetector
    from .detect.address_libpostal import AddressLineDetector
    from .detect.aliases import AliasDetector
    from .detect.bank_org import BankOrgDetector
    from .detect.date_dob import DOBDetector
    from .detect.date_generic import DateGenericDetector
    from .detect.email import EmailDetector
    from .detect.phone import PhoneDetector

    detectors: list[Detector] = [
        EmailDetector(),
        PhoneDetector(),
        AccountIdDetector(),
        BankOrgDetector(),
        AddressLineDetector(),
        DateGenericDetector(),
        DOBDetector(),
        AliasDetector(),
    ]

    if cfg.detectors.ner.enabled:
        from .detect.ner_spacy import SpacyNERDetector

        detectors.append(SpacyNERDetector(cfg))

    spans: list[EntitySpan] = []
    for det in detectors:
        spans.extend(det.detect(text, context))
    return spans


@app.callback()
def main() -> None:
    """Entry point for the redactor command group."""
    pass


@app.command()
def run(  # noqa: PLR0913
    in_path: Path = typer.Option(  # noqa: B008
        ..., "--in", "--input", help="Input file (.txt only for now)"
    ),
    out_path: Path = typer.Option(..., "--out", help="Output file (.txt)"),  # noqa: B008
    config_path: Optional[Path] = typer.Option(  # noqa: B008
        None, "--config", help="YAML config to override defaults"
    ),
    report_dir: Optional[Path] = typer.Option(  # noqa: B008
        None, "--report", help="Directory to write audit artifacts"
    ),
    encoding_in: str = typer.Option("utf-8-sig", help="Input file encoding"),  # noqa: B008
    encoding_out: str = typer.Option("utf-8", help="Output file encoding"),  # noqa: B008
    newline_out: Optional[str] = typer.Option(  # noqa: B008
        "", help="Output newline policy; empty string preserves input newlines"
    ),
    verbose: bool = typer.Option(  # noqa: B008
        False, "--verbose", "-v", help="Emit minimal progress messages to stderr"
    ),
    strict: bool | None = typer.Option(  # noqa: B008
        None,
        "--strict/--no-strict",
        help="Exit non-zero when verification residuals remain",
    ),
    keep_roles: bool | None = typer.Option(  # noqa: B008
        None,
        "--keep-roles/--redact-roles",
        help="Override alias label policy",
    ),
    enable_ner: bool | None = typer.Option(  # noqa: B008
        None,
        "--enable-ner/--disable-ner",
        help="Toggle NER detector",
    ),
    enable_coref: bool | None = typer.Option(  # noqa: B008
        None,
        "--enable-coref/--disable-coref",
        help="Toggle coreference resolver",
    ),
    coref_backend: str | None = typer.Option(  # noqa: B008
        None,
        "--coref-backend",
        help="Select coreference backend [auto|fastcoref|regex]",
    ),
) -> dict[str, str]:
    """Run the full redaction pipeline on ``in_path`` writing to ``out_path``."""

    # Load configuration
    try:
        cfg = load_config(config_path)
    except (ValidationError, Exception) as exc:  # pragma: no cover - diverse
        _safe_exit(4, str(exc).splitlines()[0])
    if verbose:
        typer.echo("Loaded config", err=True)

    cfg = _apply_overrides(
        cfg,
        keep_roles=keep_roles,
        enable_ner=enable_ner,
        enable_coref=enable_coref,
        coref_backend=coref_backend,
    )
    strict_mode = cfg.verification.fail_on_residual if strict is None else strict

    # Read input
    try:
        text = read_file(in_path, encoding=encoding_in)
    except (FileNotFoundError, UnsupportedFormatError, OSError) as exc:
        _safe_exit(3, str(exc))
    if verbose:
        typer.echo(f"Read {len(text)} chars", err=True)

    # Normalize
    with Timing() as t_norm:
        norm = normalize(text)
    normalized = norm.text
    if verbose:
        typer.echo(f"Normalized (changed={norm.changed}) in {t_norm.ms:.1f} ms", err=True)

    line_starts = build_line_starts(normalized)
    context = DetectionContext(locale=cfg.locale, line_starts=line_starts, config=cfg)

    try:
        with Timing() as t_det:
            spans = _run_detectors(normalized, cfg, context)
        if verbose:
            typer.echo(f"Detected {len(spans)} spans in {t_det.ms:.1f} ms", err=True)

        with Timing() as t_addr:
            spans = layout_reconstructor.merge_address_lines_into_blocks(normalized, spans)
        if verbose:
            typer.echo(f"Address merge in {t_addr.ms:.1f} ms", err=True)

        with Timing() as t_alias:
            spans, clusters = alias_resolver.resolve_aliases(normalized, spans, cfg)
        if verbose:
            typer.echo(f"Alias resolve in {t_alias.ms:.1f} ms", err=True)

        if cfg.detectors.coref.enabled:
            with Timing() as t_coref:
                coref_result = coref.compute_coref(normalized, spans, cfg)
                mapping = coref.unify_with_alias_clusters(spans, coref_result, clusters)
                coref.assign_coref_entity_ids(spans, coref_result, mapping)
            if verbose:
                typer.echo(f"Coref in {t_coref.ms:.1f} ms", err=True)
        elif verbose:
            typer.echo("Coref disabled", err=True)

        with Timing() as t_merge:
            merged_spans = span_merger.merge_spans(spans, cfg)
        if verbose:
            typer.echo(
                f"Merged to {len(merged_spans)} spans in {t_merge.ms:.1f} ms",
                err=True,
            )

        with Timing() as t_plan:
            plan = build_replacement_plan(normalized, merged_spans, cfg, clusters=clusters)
        if verbose:
            typer.echo(
                f"Built plan with {len(plan)} entries in {t_plan.ms:.1f} ms",
                err=True,
            )

        with Timing() as t_apply:
            redacted_text, applied_plan = apply_plan(normalized, plan)
        if verbose:
            typer.echo(f"Applied plan in {t_apply.ms:.1f} ms", err=True)

        with Timing() as t_verify:
            verification_report = scanner.scan_text(redacted_text, cfg, applied_plan=applied_plan)
        if verbose:
            typer.echo(
                f"Verification residuals={verification_report.residual_count} "
                f"score={verification_report.score} in {t_verify.ms:.1f} ms",
                err=True,
            )
    except Exception as exc:  # pragma: no cover - unexpected
        msg = str(exc)
        if verbose:
            msg = f"{type(exc).__name__}: {msg}"
        _safe_exit(5, msg)

    # Write outputs
    newline_arg = newline_out if newline_out is not None else ""
    try:
        write_file(out_path, redacted_text, encoding=encoding_out, newline=newline_arg)
    except (UnsupportedFormatError, OSError) as exc:
        _safe_exit(3, str(exc))
    if verbose:
        typer.echo("Wrote output", err=True)

    written: dict[str, str] = {"out": str(out_path)}
    if report_dir is not None:
        bundle = verify_report.write_report_bundle(
            report_dir,
            text_before=normalized,
            text_after=redacted_text,
            plan=applied_plan,
            cfg=cfg,
            verification_report=verification_report,
        )
        written.update(bundle)
        if verbose:
            typer.echo(f"Report written to {report_dir}", err=True)

    if strict_mode and verification_report.residual_count > 0:
        _safe_exit(6, None)

    return written
