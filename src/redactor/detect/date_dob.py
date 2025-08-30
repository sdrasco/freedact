"""Contextual date-of-birth detector.

This detector promotes generic date spans to :class:`~redactor.detect.base.EntityLabel.DOB`
when explicit lexical cues suggest the date refers to a person's birth.  It
reuses :class:`DateGenericDetector` to obtain candidate dates and then searches
for triggers such as ``DOB``, ``Date of Birth`` or ``born`` on the same line or
immediately preceding line.  Only dates that normalise successfully to
``YYYY-MM-DD`` are eligible.

Confidence is ``0.99`` for explicit ``DOB``/``Date of Birth``/``birthdate``
triggers and ``0.98`` when relying solely on ``born``.  The resulting span
shares the exact boundaries of the underlying date and carries through the
``normalized`` and ``components`` attributes from the generic detector while
adding ``trigger`` and ``line_scope`` metadata.
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple, cast

from redactor.preprocess.layout_reconstructor import (
    LineIndex,
    build_line_index,
    find_line_for_char,
)

from .base import DetectionContext, EntityLabel, EntitySpan
from .date_generic import DateGenericDetector

__all__ = ["DOBDetector", "get_detector"]

# ---------------------------------------------------------------------------
# Trigger patterns
# ---------------------------------------------------------------------------

_DOB_PATTERNS: List[Tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bD(?:\.\s*O\.\s*B|OB)\b", re.IGNORECASE), "dob"),
    (re.compile(r"\bdate\s+of\s+birth\b", re.IGNORECASE), "date_of_birth"),
    (re.compile(r"\bbirth\s*date\b|\bbirthdate\b", re.IGNORECASE), "birthdate"),
]

_BORN_PATTERN = re.compile(r"\bborn\b", re.IGNORECASE)

_WINDOW_CHARS = 40

# ---------------------------------------------------------------------------
# Detector implementation
# ---------------------------------------------------------------------------


class DOBDetector:
    """Classify dates of birth based on context."""

    _confidence_explicit: float = 0.99
    _confidence_born: float = 0.98

    def __init__(self) -> None:
        self._date_detector = DateGenericDetector()

    def name(self) -> str:  # pragma: no cover - trivial
        return "date_dob"

    def detect(self, text: str, context: DetectionContext | None = None) -> list[EntitySpan]:
        """Detect DOB mentions in ``text``."""

        _ = context
        candidates = self._date_detector.detect(text, context)
        line_index: LineIndex = build_line_index(text)
        spans: list[EntitySpan] = []

        for span in candidates:
            normalized = cast(str | None, span.attrs.get("normalized"))
            if not normalized:
                continue
            components = cast(dict[str, str] | None, span.attrs.get("components"))
            line_no = find_line_for_char(span.start, line_index)
            line_start, _, _ = line_index[line_no]
            window_start = max(line_start, span.start - _WINDOW_CHARS)
            left_context = text[window_start : span.start]
            trigger: str | None = None
            line_scope = "same_line"

            for pattern, name in _DOB_PATTERNS:
                if pattern.search(left_context):
                    trigger = name
                    break

            if not trigger and _BORN_PATTERN.search(left_context):
                trigger = "born"

            if not trigger and line_no > 0:
                prev_start, prev_end, _ = line_index[line_no - 1]
                prev_text = text[prev_start:prev_end]
                for pattern, name in _DOB_PATTERNS:
                    if pattern.search(prev_text):
                        trigger = name
                        line_scope = "prev_line"
                        break
                if not trigger and _BORN_PATTERN.search(prev_text):
                    trigger = "born"
                    line_scope = "prev_line"

            if not trigger:
                continue

            confidence = self._confidence_explicit if trigger != "born" else self._confidence_born

            attrs: Dict[str, object] = {
                "normalized": normalized,
                "components": components,
                "trigger": trigger,
                "line_scope": line_scope,
            }
            spans.append(
                EntitySpan(
                    span.start,
                    span.end,
                    span.text,
                    EntityLabel.DOB,
                    "date_dob",
                    confidence,
                    attrs,
                )
            )

        spans.sort(key=lambda s: s.start)
        return spans


def get_detector() -> DOBDetector:
    """Return a :class:`DOBDetector` instance."""

    return DOBDetector()
