"""Typer-based command line interface for the redactor pipeline.

This module exposes a minimal CLI focused on the early preprocessing stage
`read -> normalize -> write`.  Only plain text (``.txt``) files are supported
at the moment.  Future milestones will expand this interface without changing
its surface.

Exit codes
----------
0 - success
3 - I/O error (read/write/unsupported format)
4 - configuration error
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer

from .config import load_config
from .io import read_file, write_file
from .preprocess.normalizer import normalize
from .utils.errors import UnsupportedFormatError

app = typer.Typer(
    name="redactor",
    help="Utilities for the redaction pipeline. Use 'redactor run' to execute the pipeline.",
)


@app.callback()  # type: ignore[misc]
def main() -> None:
    """Entry point for the redactor command group."""
    pass


@app.command()  # type: ignore[misc]
def run(
    in_path: Path = typer.Option(..., "--in", help="Input file (.txt only for now)"),  # noqa: B008
    out_path: Path = typer.Option(..., "--out", help="Output file (.txt)"),  # noqa: B008
    config_path: Optional[Path] = typer.Option(  # noqa: B008
        None, "--config", help="YAML config to override defaults"
    ),
    report_dir: Optional[Path] = typer.Option(  # noqa: B008
        None, "--report", help="Optional directory to write a small preprocessing report"
    ),
    encoding_in: str = typer.Option("utf-8-sig", help="Input file encoding"),  # noqa: B008
    encoding_out: str = typer.Option("utf-8", help="Output file encoding"),  # noqa: B008
    newline_out: Optional[str] = typer.Option(  # noqa: B008
        "", help="Output newline policy; empty string preserves input newlines"
    ),
    verbose: bool = typer.Option(  # noqa: B008
        False, "--verbose", "-v", help="Emit minimal progress messages to stderr"
    ),
) -> None:
    """Run the preprocessing pipeline: read -> normalize -> write.

    Only plain text files are handled.  This command performs no redaction yet;
    it simply normalizes text.  Exit codes: 0 success, 3 I/O error, 4 config
    error.
    """

    # Load configuration
    try:
        load_config(config_path)
    except Exception as exc:  # pragma: no cover - diverse exceptions
        typer.echo(str(exc).splitlines()[0], err=True)
        raise typer.Exit(code=4) from None
    if verbose:
        typer.echo("Loaded config", err=True)

    # Read input
    try:
        text = read_file(in_path, encoding=encoding_in)
        input_bytes = in_path.stat().st_size
    except (FileNotFoundError, UnsupportedFormatError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from None
    if verbose:
        typer.echo(f"Read {len(text)} chars", err=True)

    # Normalize
    norm = normalize(text)
    if verbose:
        typer.echo(f"Normalized (changed={norm.changed})", err=True)

    # Write output
    newline_arg = newline_out if newline_out is not None else ""
    try:
        write_file(out_path, norm.text, encoding=encoding_out, newline=newline_arg)
    except (UnsupportedFormatError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from None
    if verbose:
        typer.echo("Wrote output", err=True)

    # Optional report
    if report_dir is not None:
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / "preprocess.json"
        report = {
            "doc_id": None,
            "input_bytes": input_bytes,
            "input_chars": len(text),
            "output_chars": len(norm.text),
            "changed": norm.changed,
            "removed_zero_width_chars": None,
            "dehyphenations": None,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        if verbose:
            typer.echo(f"Report written to {report_path}", err=True)
