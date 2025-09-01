from pathlib import Path
from typing import Any

import pytest

from redactor.config import load_config
from redactor.pseudo.seed import ensure_secret_present


def test_env_secret(monkeypatch: Any) -> None:
    monkeypatch.setenv("REDACTOR_SEED_SECRET", "test-secret")
    cfg = load_config()
    assert cfg.pseudonyms.seed.secret is not None
    assert cfg.pseudonyms.seed.secret.get_secret_value() == "test-secret"


def test_custom_env_override(monkeypatch: Any, tmp_path: Path) -> None:
    cfg_file = tmp_path / "cfg.yml"
    cfg_file.write_text('pseudonyms:\n  seed:\n    secret_env: "CUSTOM_ENV"\n')
    monkeypatch.setenv("CUSTOM_ENV", "custom")
    cfg = load_config(cfg_file)
    assert cfg.pseudonyms.seed.secret_env == "CUSTOM_ENV"
    assert cfg.pseudonyms.seed.secret is not None
    assert cfg.pseudonyms.seed.secret.get_secret_value() == "custom"


def test_ensure_secret_present(monkeypatch: Any) -> None:
    monkeypatch.delenv("REDACTOR_SEED_SECRET", raising=False)
    cfg = load_config(env={})
    assert ensure_secret_present(cfg, strict=False) is False
    with pytest.raises(ValueError):
        ensure_secret_present(cfg, strict=True)


def test_ensure_secret_present_env(monkeypatch: Any) -> None:
    monkeypatch.setenv("REDACTOR_SEED_SECRET", "unit-test-secret")
    cfg = load_config()
    assert ensure_secret_present(cfg, strict=True) is True
