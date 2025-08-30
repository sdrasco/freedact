"""Typed configuration schema and loader for the redactor package."""

from __future__ import annotations

import os
from collections.abc import Mapping
from importlib import resources as importlib_resources
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, SecretStr, confloat, conint

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class RedactOptions(BaseModel):
    """Options controlling which entities are redacted."""

    person_names: bool
    alias_labels: Literal["redact", "keep_roles"]
    addresses: bool
    phones: bool
    emails: bool
    bank_names: bool
    account_numbers: bool
    DOB: bool
    generic_dates: bool

    model_config = ConfigDict(extra="forbid")


class PreserveOptions(BaseModel):
    """Options for entities preserved during redaction."""

    money: bool
    durations: bool
    section_refs: bool

    model_config = ConfigDict(extra="forbid")


class SeedSettings(BaseModel):
    """Settings for pseudonym generation seed values."""

    secret_env: str
    secret: SecretStr | None = None

    model_config = ConfigDict(extra="forbid")


class PseudonymSettings(BaseModel):
    """Pseudonym generation settings."""

    cross_doc_consistency: bool
    seed: SeedSettings

    model_config = ConfigDict(extra="forbid")


class VerificationSettings(BaseModel):
    """Verification behaviour after redaction."""

    fail_on_residual: bool
    min_confidence: confloat(ge=0.0, le=1.0) = 0.5

    model_config = ConfigDict(extra="forbid")


class NERSettings(BaseModel):
    """Named-entity recognizer configuration."""

    enabled: bool
    model: str
    require: bool

    model_config = ConfigDict(extra="forbid")


class AddressSettings(BaseModel):
    """Address detector backend settings."""

    backend: Literal["usaddress", "libpostal", "auto"]
    require: bool

    model_config = ConfigDict(extra="forbid")


class DetectorsSettings(BaseModel):
    """Configuration for detector backends."""

    ner: NERSettings
    address: AddressSettings

    model_config = ConfigDict(extra="forbid")


class ConfigModel(BaseModel):
    """Top-level configuration model."""

    schema_version: conint(ge=1)
    locale: str
    redact: RedactOptions
    preserve: PreserveOptions
    pseudonyms: PseudonymSettings
    verification: VerificationSettings
    detectors: DetectorsSettings
    precedence: list[str]

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Loader utilities
# ---------------------------------------------------------------------------


def deep_merge_dicts(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge mapping ``b`` onto ``a`` returning a new dict."""

    result: dict[str, Any] = dict(a)
    for key, b_val in b.items():
        if key in result and isinstance(result[key], dict) and isinstance(b_val, dict):
            result[key] = deep_merge_dicts(result[key], b_val)
        else:
            result[key] = b_val
    return result


def load_config(
    path: str | os.PathLike[str] | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> ConfigModel:
    """Load configuration from defaults and optional user overrides.

    Precedence of sources: package ``defaults.yml`` < user-provided YAML < environment
    variable for the pseudonym seed secret.
    """

    with (
        importlib_resources.files("redactor.config")
        .joinpath("defaults.yml")
        .open("r", encoding="utf-8") as f
    ):
        defaults = yaml.safe_load(f) or {}

    if path is not None:
        with Path(path).open("r", encoding="utf-8") as f:
            overrides = yaml.safe_load(f) or {}
        merged = deep_merge_dicts(defaults, overrides)
    else:
        merged = defaults

    cfg = ConfigModel.model_validate(merged)

    environ = env if env is not None else os.environ
    secret_env = cfg.pseudonyms.seed.secret_env
    if secret_env in environ:
        cfg.pseudonyms.seed.secret = SecretStr(environ[secret_env])

    return cfg


__all__ = [
    "ConfigModel",
    "RedactOptions",
    "PreserveOptions",
    "SeedSettings",
    "PseudonymSettings",
    "VerificationSettings",
    "NERSettings",
    "AddressSettings",
    "DetectorsSettings",
    "deep_merge_dicts",
    "load_config",
]
