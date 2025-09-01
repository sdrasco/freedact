from __future__ import annotations

import pytest

from redactor.detect.base import EntityLabel
from redactor.replace.applier import apply_plan
from redactor.replace.plan_builder import PlanEntry
from redactor.utils.errors import OverlapError, SpanOutOfBoundsError


def _entry(start: int, end: int, repl: str) -> PlanEntry:
    return PlanEntry(start, end, repl, EntityLabel.PERSON, None, None, {})


def test_reverse_application_and_applied_index() -> None:
    text = "AAAA BBBB CCCC"
    plan = [_entry(5, 9, "X"), _entry(0, 4, "YY")]
    new_text, applied = apply_plan(text, plan)
    assert new_text == "YY X CCCC"
    assert applied[0].replacement == "YY"
    assert applied[0].meta["applied_index"] == 1
    assert applied[1].replacement == "X"
    assert applied[1].meta["applied_index"] == 2


def test_boundary_touching_allowed() -> None:
    text = "abcdef"
    plan = [_entry(0, 3, "X"), _entry(3, 6, "Y")]
    new_text, _ = apply_plan(text, plan)
    assert new_text == "XY"


def test_overlap_raises() -> None:
    text = "abcde"
    plan = [_entry(0, 4, "X"), _entry(3, 5, "Y")]
    with pytest.raises(OverlapError):
        apply_plan(text, plan)


def test_out_of_bounds_raises() -> None:
    text = "short"
    plan = [_entry(0, 999, "X")]
    with pytest.raises(SpanOutOfBoundsError):
        apply_plan(text, plan)


def test_empty_plan_returns_original() -> None:
    text = "unchanged"
    new_text, applied = apply_plan(text, [])
    assert new_text == text
    assert applied == []
