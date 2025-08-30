from __future__ import annotations

from typer.testing import CliRunner

from redactor.cli import app


def test_global_help() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert "redactor run" in result.stdout
    assert "--in" in result.stdout


def test_run_help() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["run", "--help"])
    assert "--in" in result.stdout
    assert "--out" in result.stdout
    assert "--config" in result.stdout
    assert "--report" in result.stdout
