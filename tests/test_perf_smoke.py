from __future__ import annotations

import os
from typing import cast

import pytest

from evaluation.fixtures import loader as fixtures_loader
from evaluation.perf import profile_fixtures, profile_pipeline
from redactor.config import load_config

if os.getenv("SKIP_PERF_TESTS") == "1":
    pytest.skip("Performance tests skipped by SKIP_PERF_TESTS", allow_module_level=True)


def _get_env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, "").strip() or default)
    except ValueError:
        return default


def _get_env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "").strip() or default)
    except ValueError:
        return default


def _synth_text(names: list[str], repeat: int) -> str:
    parts = [fixtures_loader.load_fixture(n)[0] for n in names]
    base = "\n\n".join(parts)
    return "\n\n".join([base] * repeat)


def _required_keys() -> set[str]:
    return {
        "normalize",
        "detect",
        "address_merge",
        "alias_resolve",
        "coref",
        "merge_spans",
        "plan_build",
        "apply",
        "verify",
        "total",
    }


def test_profile_pipeline_smoke() -> None:
    text = "Contact john@example.com or 555-123-4567 on 2024-01-01."
    cfg = load_config()
    cfg.detectors.ner.enabled = False
    timings = profile_pipeline(text, cfg)
    assert set(timings) == _required_keys()
    for value in timings.values():
        assert isinstance(value, float)
        assert value >= 0.0
    total = timings["total"]
    subtotal = sum(v for k, v in timings.items() if k != "total")
    assert total >= subtotal - 0.005


def test_profile_fixtures_smoke() -> None:
    res = profile_fixtures(names=["emails_phones"], ner=False, repeat=2)
    assert len(res) == 1
    item = res[0]
    stages = cast(dict[str, float], item["stages"])
    assert set(stages) == _required_keys()
    for value in stages.values():
        assert isinstance(value, float)
        assert value >= 0.0


def test_profile_pipeline_budget() -> None:
    repeat = _get_env_int("PERF_REPEAT", 80)
    text = _synth_text(["banks_ids", "emails_phones"], repeat)
    cfg = load_config()
    cfg = cfg.model_copy(
        update={
            "detectors": cfg.detectors.model_copy(
                update={
                    "ner": cfg.detectors.ner.model_copy(
                        update={"enabled": False, "require": False}
                    ),
                    "coref": cfg.detectors.coref.model_copy(
                        update={
                            "enabled": False,
                            "backend": "regex",
                            "require": False,
                        }
                    ),
                }
            )
        }
    )
    stages = profile_pipeline(text, cfg)
    budget = _get_env_float("PERF_MAX_SEC", 5.0)
    assert (
        stages["total"] <= budget
    ), f"pipeline total {stages['total']:.3f}s (budget {budget:.3f}s)"
    assert set(stages) == _required_keys()
    for key in ["detect", "plan_build", "apply"]:
        assert stages[key] >= 0.0
    subtotal = sum(v for k, v in stages.items() if k != "total")
    assert stages["total"] >= subtotal - 0.001
