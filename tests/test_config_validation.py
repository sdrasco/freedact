from pathlib import Path

import pytest
from pydantic import ValidationError

from redactor.config import load_config


def test_invalid_min_confidence(tmp_path: Path) -> None:
    cfg_file = tmp_path / "bad.yml"
    cfg_file.write_text("verification:\n  min_confidence: 2.0\n")
    with pytest.raises(ValidationError):
        load_config(cfg_file)


def test_unknown_key(tmp_path: Path) -> None:
    cfg_file = tmp_path / "bad.yml"
    cfg_file.write_text("unknown:\n  foo: 1\n")
    with pytest.raises(ValidationError):
        load_config(cfg_file)
