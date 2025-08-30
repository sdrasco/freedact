from pathlib import Path
from typing import Any

from redactor.config import load_config


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
