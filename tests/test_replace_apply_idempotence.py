from __future__ import annotations

from redactor.detect.base import EntityLabel
from redactor.replace.applier import apply_plan
from redactor.replace.plan_builder import PlanEntry


def _entry(start: int, end: int, repl: str) -> PlanEntry:
    return PlanEntry(start, end, repl, EntityLabel.PERSON, None, None, {})


def test_apply_plan_idempotence() -> None:
    text = "John Doe met Jane."
    plan = [_entry(0, 8, "Alex Carter"), _entry(13, 17, "Taylor")]
    text2, _ = apply_plan(text, plan)
    text3, _ = apply_plan(text2, plan)
    assert text3 == text2
    orig_total = sum(e.end - e.start for e in plan)
    repl_total = sum(len(e.replacement) for e in plan)
    assert len(text2) == len(text) - orig_total + repl_total
