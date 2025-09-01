import subprocess
import sys
import tarfile
import tomllib
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

pytest.importorskip("build", reason="'build' extra not installed")

ROOT = Path(__file__).resolve().parents[1]
with (ROOT / "pyproject.toml").open("rb") as f:
    pyproject = tomllib.load(f)
project_name = pyproject["project"]["name"]
has_readme = "readme" in pyproject["project"]


def test_build_sanity() -> None:
    with TemporaryDirectory() as tmpdir:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "build",
                "--sdist",
                "--wheel",
                "--outdir",
                tmpdir,
            ],
            check=True,
            cwd=str(ROOT),
            capture_output=True,
        )

        tmp_path = Path(tmpdir)
        wheels = list(tmp_path.glob("*.whl"))
        sdists = list(tmp_path.glob("*.tar.gz"))
        assert len(wheels) == 1
        assert len(sdists) == 1

        wheel_path = wheels[0]
        with zipfile.ZipFile(wheel_path) as zf:
            metadata_files = [n for n in zf.namelist() if n.endswith(".dist-info/METADATA")]
            assert metadata_files, "METADATA not found in wheel"
            metadata_text = zf.read(metadata_files[0]).decode()
            lines = metadata_text.splitlines()
            assert f"Name: {project_name}" in lines
            version_line = next((line for line in lines if line.startswith("Version:")), "")
            assert version_line.split(":", 1)[1].strip()
            summary_line = next((line for line in lines if line.startswith("Summary:")), "")
            assert summary_line
            summary_value = summary_line.split(":", 1)[1].strip()
            assert summary_value or not has_readme
            classifiers = [line for line in lines if line.startswith("Classifier:")]
            assert classifiers

            entry_files = [n for n in zf.namelist() if n.endswith(".dist-info/entry_points.txt")]
            assert entry_files, "entry_points.txt not found"
            entry_text = zf.read(entry_files[0]).decode()
            assert "[console_scripts]" in entry_text
            assert "redactor = redactor.cli:app" in entry_text

        sdist_path = sdists[0]
        with tarfile.open(sdist_path) as tf:
            names = tf.getnames()
            assert any(name.endswith("pyproject.toml") for name in names)
            assert any(name.endswith("src/redactor/__init__.py") for name in names)
