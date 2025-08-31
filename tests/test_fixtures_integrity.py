from __future__ import annotations

from typing import Any, cast

from evaluation.fixtures.loader import list_fixtures, load_fixture, validate_spans
from redactor.detect.base import EntityLabel


def test_fixture_integrity() -> None:
    for name in list_fixtures():
        text, ann = load_fixture(name)
        errors = validate_spans(text, ann)
        assert not errors, f"{name} errors: {errors}"
        spans = cast(list[dict[str, Any]], ann.get("spans", []))
        assert spans, f"{name} has no spans"
        labels = {cast(str, sp["label"]) for sp in spans}
        valid_labels = {label.value for label in EntityLabel}
        assert labels <= valid_labels
