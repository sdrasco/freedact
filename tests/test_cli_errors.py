from __future__ import annotations

from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from redactor.cli import app


def test_missing_file(tmp_path: Path) -> None:
    out_txt = tmp_path / "out.txt"
    missing = tmp_path / "missing.txt"
    runner = CliRunner()
    result = runner.invoke(app, ["run", "--in", str(missing), "--out", str(out_txt)])
    assert result.exit_code == 3
    assert str(missing) in result.stderr


def test_unsupported_extension(tmp_path: Path) -> None:
    in_path = tmp_path / "foo.bin"
    in_path.write_text("data", encoding="utf-8")
    out_path = tmp_path / "out.txt"
    runner = CliRunner()
    result = runner.invoke(app, ["run", "--in", str(in_path), "--out", str(out_path)])
    assert result.exit_code == 3


def test_bad_config(tmp_path: Path) -> None:
    in_path = tmp_path / "in.txt"
    in_path.write_text("hello", encoding="utf-8")
    out_path = tmp_path / "out.txt"
    bad_cfg = tmp_path / "bad.yml"
    bad_cfg.write_text("unknown: true\n", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "run",
            "--in",
            str(in_path),
            "--out",
            str(out_path),
            "--config",
            str(bad_cfg),
        ],
    )
    assert result.exit_code == 4


def test_require_secret_missing(tmp_path: Path, monkeypatch: Any) -> None:
    in_path = tmp_path / "in.txt"
    in_path.write_text("hello", encoding="utf-8")
    out_path = tmp_path / "out.txt"
    monkeypatch.delenv("REDACTOR_SEED_SECRET", raising=False)
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["run", "--in", str(in_path), "--out", str(out_path), "--require-secret"],
    )
    assert result.exit_code == 4


def test_require_secret_present(tmp_path: Path, monkeypatch: Any) -> None:
    in_path = tmp_path / "in.txt"
    in_path.write_text("hello", encoding="utf-8")
    out_path = tmp_path / "out.txt"
    monkeypatch.setenv("REDACTOR_SEED_SECRET", "unit-test-secret")
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["run", "--in", str(in_path), "--out", str(out_path), "--require-secret"],
    )
    assert result.exit_code == 0
    assert out_path.exists()
