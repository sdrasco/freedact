from __future__ import annotations

from evaluation.perf import profile_fixtures, profile_pipeline
from redactor.config import load_config
from typing import cast


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
