from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from redactor.cli import app


def test_cli_run_basic(tmp_path: Path) -> None:
    text = "He said, “Done.” co\u00adoperate\n"
    in_txt = tmp_path / "in.txt"
    in_txt.write_text(text, encoding="utf-8")
    out_txt = tmp_path / "out.txt"

    runner = CliRunner()
    result = runner.invoke(app, ["run", "--in", str(in_txt), "--out", str(out_txt)])
    assert result.exit_code == 0
    assert out_txt.read_text(encoding="utf-8") == 'He said, "Done." cooperate\n'

    report_dir = tmp_path / "report"
    result = runner.invoke(
        app,
        ["run", "--in", str(in_txt), "--out", str(out_txt), "--report", str(report_dir)],
    )
    assert result.exit_code == 0
    data = json.loads((report_dir / "preprocess.json").read_text())
    assert "changed" in data
