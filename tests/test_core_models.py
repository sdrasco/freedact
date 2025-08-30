from dataclasses import FrozenInstanceError

import pytest

from redactor.detect.base import EntityLabel, EntitySpan


def test_entity_span_fields_and_length() -> None:
    span = EntitySpan(
        start=0,
        end=4,
        text="John",
        label=EntityLabel.PERSON,
        source="dummy",
        confidence=0.9,
    )
    assert span.start == 0
    assert span.end == 4
    assert span.text == "John"
    assert span.length == 4


def test_entity_span_immutable() -> None:
    span = EntitySpan(
        start=0,
        end=1,
        text="J",
        label=EntityLabel.PERSON,
        source="dummy",
        confidence=0.5,
    )
    with pytest.raises(FrozenInstanceError):
        span.start = 1  # type: ignore[misc]


@pytest.mark.parametrize(
    "start,end,confidence",
    [(-1, 2, 0.5), (5, 5, 0.5), (0, 1, 1.5), (0, 1, -0.1)],
)
def test_entity_span_validation(start: int, end: int, confidence: float) -> None:
    with pytest.raises(ValueError):
        EntitySpan(
            start=start,
            end=end,
            text="x",
            label=EntityLabel.OTHER,
            source="dummy",
            confidence=confidence,
        )
