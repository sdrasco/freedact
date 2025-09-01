from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from redactor.cli import _run_detectors, app
from redactor.config import ConfigModel
from redactor.detect.base import DetectionContext, EntityLabel, EntitySpan

SAMPLE_TEXT = (
    "John Doe\n"
    "Address: 366 Broadway\n"
    "San Francisco, CA 94105\n"
    'Hereinafter "Morgan"\n'
    "Date of Birth: July 4, 1982\n"
    "Email: john@acme.com\n"
    "Phone: (415) 555-0000\n"
    "Card: 4111 1111 1111 1111\n"
)


def _run_cli(
    tmp_path: Path,
    text: str,
    extra: list[str] | None = None,
    *,
    env: dict[str, str] | None = None,
) -> tuple[int, Path, Path]:
    in_txt = tmp_path / "in.txt"
    in_txt.write_text(text, encoding="utf-8")
    out_txt = tmp_path / "out.txt"
    report_dir = tmp_path / "report"
    cmd = [
        "run",
        "--in",
        str(in_txt),
        "--out",
        str(out_txt),
        "--report",
        str(report_dir),
        "--strict",
    ]
    if extra:
        cmd.extend(extra)
    runner = CliRunner()
    result = runner.invoke(app, cmd, env=env)
    return result.exit_code, out_txt, report_dir


def test_basic_success(tmp_path: Path) -> None:
    code, out_txt, rep = _run_cli(tmp_path, SAMPLE_TEXT)
    assert code == 0
    assert out_txt.exists()
    assert out_txt.read_text(encoding="utf-8") != SAMPLE_TEXT
    assert (rep / "audit.json").exists()
    assert (rep / "diff.html").exists()
    verification = json.loads((rep / "verification.json").read_text())
    assert verification["residual_count"] == 0
    plan = json.loads((rep / "plan.json").read_text())
    labels = {p["label"] for p in plan}
    assert {
        "PERSON",
        "ADDRESS_BLOCK",
        "ALIAS_LABEL",
        "DOB",
        "EMAIL",
        "PHONE",
        "ACCOUNT_ID",
    } <= labels


def test_seed_present_in_audit(tmp_path: Path) -> None:
    in_txt = tmp_path / "in.txt"
    in_txt.write_text("Email: john@acme.com\n", encoding="utf-8")
    out_txt = tmp_path / "out.txt"
    report_dir = tmp_path / "report"
    cmd = [
        "run",
        "--in",
        str(in_txt),
        "--out",
        str(out_txt),
        "--report",
        str(report_dir),
        "--no-strict",
    ]
    runner = CliRunner()
    result = runner.invoke(
        app,
        cmd,
        env={"REDACTOR_SEED_SECRET": "unit-test-secret", "PYTHONPATH": "src:."},
    )
    assert result.exit_code == 0
    audit_text = (report_dir / "audit.json").read_text(encoding="utf-8")
    audit = json.loads(audit_text)
    assert audit["summary"]["seed_present"]
    assert "unit-test-secret" not in audit_text


def test_alias_policy_keep_roles(tmp_path: Path) -> None:
    code, out_txt, rep = _run_cli(tmp_path, SAMPLE_TEXT, ["--keep-roles"])
    assert code == 0
    plan = json.loads((rep / "plan.json").read_text())
    assert any(p["label"] == "ALIAS_LABEL" for p in plan)


def test_disable_ner(tmp_path: Path) -> None:
    code, out_txt, rep = _run_cli(tmp_path, SAMPLE_TEXT, ["--disable-ner"])
    assert code == 0
    verification = json.loads((rep / "verification.json").read_text())
    assert verification["residual_count"] == 0
    plan = json.loads((rep / "plan.json").read_text())
    labels = {p["label"] for p in plan}
    assert {"ADDRESS_BLOCK", "DOB", "EMAIL", "PHONE", "ACCOUNT_ID"} <= labels


def test_strict_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def stub(text: str, cfg: ConfigModel, context: DetectionContext) -> list[EntitySpan]:
        spans = _run_detectors(text, cfg, context)
        return [sp for sp in spans if sp.label is not EntityLabel.EMAIL]

    monkeypatch.setattr("redactor.cli._run_detectors", stub)
    text = "Email: user@acme.com\n"
    code, out_txt, rep = _run_cli(tmp_path, text)
    assert code == 6
    verification = json.loads((rep / "verification.json").read_text())
    assert verification["residual_count"] == 1


def test_verbose_smoke(tmp_path: Path) -> None:
    in_txt = tmp_path / "in.txt"
    in_txt.write_text(SAMPLE_TEXT, encoding="utf-8")
    out_txt = tmp_path / "out.txt"
    report_dir = tmp_path / "report"
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
            str(report_dir),
            "--verbose",
            "--strict",
        ],
    )
    assert "Loaded config" in result.stderr
    assert "Detected" in result.stderr
    assert "Applied plan" in result.stderr


def test_idempotence(tmp_path: Path) -> None:
    code, out_txt, rep = _run_cli(tmp_path, SAMPLE_TEXT)
    assert code == 0
    text1 = out_txt.read_text(encoding="utf-8")
    code2, out2, rep2 = _run_cli(tmp_path, text1)
    assert code2 == 0
    assert out2.read_text(encoding="utf-8") == text1
    verification = json.loads((rep2 / "verification.json").read_text())
    assert verification["residual_count"] == 0
