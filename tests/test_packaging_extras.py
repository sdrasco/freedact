"""Tests for packaging metadata and optional dependencies."""

from __future__ import annotations

import importlib
import tomllib
from pathlib import Path
from typing import Any, cast


def _load_pyproject() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    with path.open("rb") as fh:
        return tomllib.load(fh)


def _extras(pyproject: dict[str, Any]) -> dict[str, list[str]]:
    return cast(dict[str, list[str]], pyproject.get("project", {}).get("optional-dependencies", {}))


def _flatten_mypy_overrides(pyproject: dict[str, Any]) -> set[str]:
    overrides = pyproject.get("tool", {}).get("mypy", {}).get("overrides", [])
    modules: set[str] = set()
    for entry in overrides:
        modules.update(entry.get("module", []))
    return modules


def test_optional_dependency_groups() -> None:
    pyproject = _load_pyproject()
    extras = _extras(pyproject)
    required = {"dev", "ner", "coref", "addresses", "all"}
    assert required.issubset(extras)
    union = set().union(*(extras[k] for k in ("ner", "coref", "addresses")))
    assert set(extras["all"]).issuperset(union)


def test_console_script_entrypoint() -> None:
    pyproject = _load_pyproject()
    scripts = pyproject.get("project", {}).get("scripts", {})
    assert "redactor" in scripts


def test_import_smoke() -> None:
    importlib.import_module("redactor")
    importlib.import_module("redactor.cli")


def test_mypy_overrides() -> None:
    pyproject = _load_pyproject()
    mods = _flatten_mypy_overrides(pyproject)
    for mod in {"spacy", "spacy.*", "usaddress", "usaddress.*", "fastcoref", "fastcoref.*"}:
        assert mod in mods
