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

        by_line: dict[int, list[tuple[int, EntitySpan]]] = {}
        for idx, span in enumerate(candidates):
            by_line.setdefault(find_line_for_char(span.start, line_index), []).append((idx, span))

        sep_rx = re.compile(r"^[\s:\-–—]{0,3}$")
        used: set[int] = set()
        pending: tuple[str, bool] | None = None

        for line_no, (l_start, l_end, _) in enumerate(line_index):
            entries = by_line.get(line_no, [])
            entries.sort(key=lambda x: x[1].start)
            date_idx = 0

            if pending and entries:
                trig, _ = pending
                span_idx, span = entries[date_idx]
                prefix = text[l_start : span.start]
                if prefix.strip() == "":
                    normalized = cast(str | None, span.attrs.get("normalized"))
                    if normalized:
                        components = cast(dict[str, str] | None, span.attrs.get("components"))
                        prev_attrs: Dict[str, object] = {
                            "normalized": normalized,
                            "components": components,
                            "trigger": trig,
                            "line_scope": "prev_line",
                        }
                        spans.append(
                            EntitySpan(
                                span.start,
                                span.end,
                                span.text,
                                EntityLabel.DOB,
                                "date_dob",
                                self._confidence_explicit,
                                prev_attrs,
                            )
                        )
                        used.add(span_idx)
                        date_idx += 1
                pending = None

            trigger_matches: list[tuple[int, int, str]] = []
            line_text = text[l_start:l_end]
            for pattern, name in _DOB_PATTERNS:
                for m in pattern.finditer(line_text):
                    trigger_matches.append((l_start + m.start(), l_start + m.end(), name))
            trigger_matches.sort()

            for _t_start, t_end, name in trigger_matches:
                while date_idx < len(entries) and entries[date_idx][1].start < t_end:
                    date_idx += 1
                if date_idx >= len(entries):
                    pending = (name, True)
                    break
                span_idx, span = entries[date_idx]
                between = text[t_end : span.start]
                if "." in between or not sep_rx.fullmatch(between):
                    continue
                normalized = cast(str | None, span.attrs.get("normalized"))
                if not normalized:
                    continue
                components = cast(dict[str, str] | None, span.attrs.get("components"))
                attrs: Dict[str, object] = {
                    "normalized": normalized,
                    "components": components,
                    "trigger": name,
                    "line_scope": "same_line",
                }
                spans.append(
                    EntitySpan(
                        span.start,
                        span.end,
                        span.text,
                        EntityLabel.DOB,
                        "date_dob",
                        self._confidence_explicit,
                        attrs,
                    )
                )
                used.add(span_idx)
                date_idx += 1

        for idx, span in enumerate(candidates):
            if idx in used:
                continue
            normalized = cast(str | None, span.attrs.get("normalized"))
            if not normalized:
                continue
            components = cast(dict[str, str] | None, span.attrs.get("components"))
            line_no = find_line_for_char(span.start, line_index)
            line_start, _, _ = line_index[line_no]
            window_start = max(line_start, span.start - _WINDOW_CHARS)
            left_context = text[window_start : span.start]
            trigger = None
            scope = "same_line"
            if _BORN_PATTERN.search(left_context):
                trigger = "born"
            elif line_no > 0:
                prev_start, prev_end, _ = line_index[line_no - 1]
                prev_text = text[prev_start:prev_end]
                if _BORN_PATTERN.search(prev_text):
                    trigger = "born"
                    scope = "prev_line"
            if not trigger:
                continue
            attrs = {
                "normalized": normalized,
                "components": components,
                "trigger": trigger,
                "line_scope": scope,
            }
            spans.append(
                EntitySpan(
                    span.start,
                    span.end,
                    span.text,
                    EntityLabel.DOB,
                    "date_dob",
                    self._confidence_born,
                    attrs,
                )
            )

        spans.sort(key=lambda s: s.start)
        return spans


def get_detector() -> DOBDetector:
    """Return a :class:`DOBDetector` instance."""

    return DOBDetector()
