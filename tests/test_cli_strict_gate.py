from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from redactor.cli import _run_detectors, app
from redactor.config import ConfigModel
from redactor.detect.base import DetectionContext, EntityLabel, EntitySpan


def _prep(tmp_path: Path, text: str) -> tuple[Path, Path, Path]:
    in_txt = tmp_path / "in.txt"
    in_txt.write_text(text, encoding="utf-8")
    out_txt = tmp_path / "out.txt"
    rep_dir = tmp_path / "rep"
    return in_txt, out_txt, rep_dir


def test_strict_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def stub(text: str, cfg: ConfigModel, context: DetectionContext) -> list[EntitySpan]:
        spans = _run_detectors(text, cfg, context)
        return [sp for sp in spans if sp.label is not EntityLabel.EMAIL]

    monkeypatch.setattr("redactor.cli._run_detectors", stub)
    in_txt, out_txt, rep = _prep(tmp_path, "Email: user@acme.com\n")
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "run",
            "--in",
            str(in_txt),
            "--out",
            str(out_txt),
            "--report",
            str(rep),
            "--strict",
        ],
        env={"REDACTOR_SEED_SECRET": "unit-test-secret", "PYTHONPATH": "src:."},
    )
    assert result.exit_code == 6
    assert out_txt.exists()
    verification = json.loads((rep / "verification.json").read_text())
    assert verification["residual_count"] > 0


def test_strict_success(tmp_path: Path) -> None:
    in_txt, out_txt, rep = _prep(tmp_path, "Email: user@acme.com\n")
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "run",
            "--in",
            str(in_txt),
            "--out",
            str(out_txt),
            "--report",
            str(rep),
            "--strict",
        ],
        env={"REDACTOR_SEED_SECRET": "unit-test-secret", "PYTHONPATH": "src:."},
    )
    assert result.exit_code == 0
    assert out_txt.exists()
    verification = json.loads((rep / "verification.json").read_text())
    assert verification["residual_count"] == 0
