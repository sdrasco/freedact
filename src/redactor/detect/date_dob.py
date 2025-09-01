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

_SEP_CLASS = ":-–—"
_DOB_PATTERNS: List[Tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            rf"\bD(?:\.\s*O\.\s*B|OB)\.?\b(?:\s{{0,2}}[{_SEP_CLASS}]\s{{0,2}})?$",
            re.IGNORECASE,
        ),
        "dob",
    ),
    (
        re.compile(
            rf"\bdate\s+of\s+birth\b(?:\s{{0,2}}[{_SEP_CLASS}]\s{{0,2}})?$",
            re.IGNORECASE,
        ),
        "date_of_birth",
    ),
    (
        re.compile(
            rf"(?:\bbirth\s*date\b|\bbirthdate\b)(?:\s{{0,2}}[{_SEP_CLASS}]\s{{0,2}})?$",
            re.IGNORECASE,
        ),
        "birthdate",
    ),
]

_BORN_PATTERN = re.compile(r"\bborn\b", re.IGNORECASE)

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
        candidates = sorted(self._date_detector.detect(text, context), key=lambda s: s.start)
        line_index: LineIndex = build_line_index(text)
        spans: list[EntitySpan] = []
        seen_by_line: dict[int, list[int]] = {}

        for span in candidates:
            normalized = cast(str | None, span.attrs.get("normalized"))
            if not normalized:
                continue
            components = cast(dict[str, str] | None, span.attrs.get("components"))
            line_no = find_line_for_char(span.start, line_index)
            line_start, _, _ = line_index[line_no]
            line_text = text[line_start : span.start]
            last_period = line_text.rfind(".")
            segment = line_text[last_period + 1 :] if last_period != -1 else line_text
            segment = segment.rstrip()
            trigger: str | None = None
            trigger_pos: int | None = None
            line_scope = "same_line"

            for pattern, name in _DOB_PATTERNS:
                m = pattern.search(segment)
                if m:
                    trigger = name
                    offset = last_period + 1 if last_period != -1 else 0
                    trigger_pos = line_start + offset + m.start()
                    break

            if not trigger:
                m = _BORN_PATTERN.search(segment)
                if m:
                    trigger = "born"
                    offset = last_period + 1 if last_period != -1 else 0
                    trigger_pos = line_start + offset + m.start()

            if not trigger and line_no > 0:
                prev_start, prev_end, _ = line_index[line_no - 1]
                prev_segment = text[prev_start:prev_end].rstrip()
                for pattern, name in _DOB_PATTERNS:
                    m = pattern.search(prev_segment)
                    if m:
                        trigger = name
                        trigger_pos = prev_start + m.start()
                        line_scope = "prev_line"
                        break
                if not trigger:
                    m = _BORN_PATTERN.search(prev_segment)
                    if m:
                        trigger = "born"
                        trigger_pos = prev_start + m.start()
                        line_scope = "prev_line"

            line_seen = seen_by_line.setdefault(line_no, [])
            if not trigger:
                line_seen.append(span.start)
                continue

            skip = False
            if line_scope == "same_line" and trigger_pos is not None:
                if any(s >= trigger_pos for s in line_seen):
                    skip = True
            elif line_scope == "prev_line":
                if line_seen:
                    skip = True
            if skip:
                line_seen.append(span.start)
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
            line_seen.append(span.start)

        spans.sort(key=lambda s: s.start)
        return spans


def get_detector() -> DOBDetector:
    """Return a :class:`DOBDetector` instance."""

    return DOBDetector()
