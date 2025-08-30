import pytest

from redactor.detect.base import EntityLabel, EntitySpan
from redactor.utils.errors import OverlapError
from redactor.utils.textspan import (
    build_line_starts,
    char_to_line_col,
    detect_text_case,
    ensure_non_overlapping,
    sort_spans_for_replacement,
    span_contains,
    spans_overlap,
)


def test_line_starts_and_char_to_line_col() -> None:
    text = "John\nDoe\n\n"
    line_starts = build_line_starts(text)
    assert line_starts == (0, 5, 9, 10)
    assert char_to_line_col(0, line_starts) == (0, 0)
    assert char_to_line_col(5, line_starts) == (1, 0)
    assert char_to_line_col(9, line_starts) == (2, 0)


def test_spans_overlap_truth_table() -> None:
    assert spans_overlap((0, 2), (1, 3)) is True
    assert spans_overlap((0, 2), (2, 4)) is False
    assert spans_overlap((2, 4), (0, 2)) is False


def test_span_contains() -> None:
    assert span_contains((0, 5), (1, 3)) is True
    assert span_contains((0, 5), (0, 5)) is True
    assert span_contains((0, 5), (5, 5)) is False


def test_sort_spans_for_replacement_ordering() -> None:
    spans = [
        EntitySpan(0, 3, "abc", EntityLabel.OTHER, "s", 1.0),
        EntitySpan(5, 7, "de", EntityLabel.OTHER, "s", 1.0),
        EntitySpan(5, 8, "def", EntityLabel.OTHER, "s", 1.0),
    ]
    ordered = sort_spans_for_replacement(spans)
    assert [s.start for s in ordered] == [5, 5, 0]
    assert [s.length for s in ordered] == [3, 2, 3]


def test_ensure_non_overlapping() -> None:
    spans = [
        EntitySpan(0, 3, "abc", EntityLabel.OTHER, "s", 1.0),
        EntitySpan(2, 5, "cde", EntityLabel.OTHER, "s", 1.0),
    ]
    with pytest.raises(OverlapError):
        ensure_non_overlapping(spans)


def test_detect_text_case() -> None:
    assert detect_text_case("JOHN DOE") == "UPPER"
    assert detect_text_case("john doe") == "LOWER"
    assert detect_text_case("John Doe") == "TITLE"
    assert detect_text_case("JoHn") == "MIXED"
