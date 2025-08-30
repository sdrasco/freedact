"""Utility functions for working with text spans.

The helpers in this module are pure and framework agnostic.  Spans are
represented as half‑open intervals ``[start, end)`` where ``start`` is inclusive
and ``end`` is exclusive.  Boundary touching spans therefore do not overlap.
"""

from __future__ import annotations

from bisect import bisect_right
from typing import Literal

from redactor.detect.base import EntitySpan
from redactor.utils.errors import OverlapError


def build_line_starts(text: str) -> tuple[int, ...]:
    """Return the starting character index for each line in ``text``."""

    starts = [0]
    for idx, char in enumerate(text):
        if char == "\n":
            starts.append(idx + 1)
    return tuple(starts)


def char_to_line_col(index: int, line_starts: tuple[int, ...]) -> tuple[int, int]:
    """Convert a character index to ``(line, col)`` using ``line_starts``.

    Line and column numbers are zero‑based.
    """

    if index < 0:
        raise ValueError("index must be non‑negative")
    line = bisect_right(line_starts, index) - 1
    if line < 0:
        line = 0
    col = index - line_starts[line]
    return line, col


def spans_overlap(a: tuple[int, int], b: tuple[int, int]) -> bool:
    """Return ``True`` if span ``a`` overlaps span ``b``."""

    return not (a[1] <= b[0] or b[1] <= a[0])


def span_contains(outer: tuple[int, int], inner: tuple[int, int]) -> bool:
    """Return ``True`` if ``outer`` fully contains ``inner``.

    A span is considered contained only if ``inner`` is not positioned entirely
    at ``outer``'s end boundary.
    """

    return outer[0] <= inner[0] < outer[1] and inner[1] <= outer[1]


def sort_spans_for_replacement(
    spans: list[EntitySpan], *, reverse: bool = True
) -> list[EntitySpan]:
    """Return ``spans`` sorted for safe replacement.

    By default spans are sorted in descending order by ``start`` and then by
    length.  This ordering allows in‑place text replacement without affecting
    subsequent span offsets.
    """

    return sorted(spans, key=lambda s: (s.start, s.length), reverse=reverse)


def ensure_non_overlapping(spans: list[EntitySpan]) -> None:
    """Ensure that ``spans`` do not overlap.

    Raises :class:`OverlapError` if any pair of spans overlaps.
    """

    ordered = sorted(spans, key=lambda s: s.start)
    for prev, cur in zip(ordered, ordered[1:], strict=False):
        if spans_overlap((prev.start, prev.end), (cur.start, cur.end)):
            msg = f"Spans overlap: {prev} and {cur}"
            raise OverlapError(msg)


def detect_text_case(s: str) -> Literal["UPPER", "LOWER", "TITLE", "MIXED"]:
    """Detect the predominant case of ``s``."""

    if s.isupper():
        return "UPPER"
    if s.islower():
        return "LOWER"
    if s.istitle():
        return "TITLE"
    return "MIXED"
