"""Explicit date-of-birth detector.

This detector searches for lexical triggers such as ``DOB`` or ``Date of Birth``
followed by a date on the same line (or the immediately following line).
Only the first date token to the right of a trigger is captured and the
resulting span preserves the original date text without including the trigger.
"""

from __future__ import annotations

import re

from redactor.preprocess.layout_reconstructor import build_line_index
from redactor.utils.datefmt import parse_like

from .base import DetectionContext, EntityLabel, EntitySpan

__all__ = ["DOBDetector", "get_detector"]

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

_TRIGGERS: list[tuple[re.Pattern[str], str, bool]] = [
    (re.compile(r"\bD(?:\.\s*O\.\s*B|OB)\.?", re.IGNORECASE), "dob", True),
    (re.compile(r"\bdate\s+of\s+birth\b", re.IGNORECASE), "date_of_birth", True),
    (
        re.compile(r"\bbirth\s*date\b|\bbirthdate\b", re.IGNORECASE),
        "birthdate",
        True,
    ),
    (re.compile(r"\bborn\b", re.IGNORECASE), "born", False),
]

_SEP_AFTER = re.compile(r"\s{0,2}[:\-–—]\s{0,2}")
_BORN_SKIP = re.compile(r"\s{0,2}(?:on\s+)?")

_MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
_RX_NUMERIC = re.compile(r"\d{1,2}/\d{1,2}/\d{4}")
_RX_MONTH = re.compile(rf"(?:{_MONTHS})\s+\d{{1,2}},\s*\d{{4}}", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Detector implementation
# ---------------------------------------------------------------------------


class DOBDetector:
    """Detect DOB mentions based on explicit triggers."""

    _confidence: float = 0.99

    def name(self) -> str:  # pragma: no cover - trivial
        return "date_dob"

    def detect(self, text: str, context: DetectionContext | None = None) -> list[EntitySpan]:
        _ = context
        line_index = build_line_index(text)
        spans: list[EntitySpan] = []

        for idx, (l_start, l_end, _) in enumerate(line_index):
            line = text[l_start:l_end]
            for rx, trig_name, need_sep in _TRIGGERS:
                for m in rx.finditer(line):
                    after = line[m.end() :]
                    sep_match = _BORN_SKIP.match(after) if not need_sep else _SEP_AFTER.match(after)
                    if not sep_match:
                        continue
                    remainder = after[sep_match.end() :]
                    scope = "same_line"
                    if not remainder.strip() and idx + 1 < len(line_index):
                        n_start, n_end, _ = line_index[idx + 1]
                        remainder = text[n_start:n_end]
                        scope = "prev_line"
                        search_start = n_start
                    else:
                        search_start = l_start + m.end() + sep_match.end()
                    period = remainder.find(".")
                    segment = remainder[:period] if period != -1 else remainder
                    m_num = _RX_NUMERIC.search(segment)
                    m_mon = _RX_MONTH.search(segment)
                    cand = None
                    if m_num and m_mon:
                        cand = m_num if m_num.start() < m_mon.start() else m_mon
                    else:
                        cand = m_num or m_mon
                    if not cand:
                        continue
                    date_text = cand.group().strip()
                    parsed = parse_like(date_text)
                    if not parsed:
                        continue
                    start = search_start + cand.start()
                    end = start + len(date_text)
                    attrs: dict[str, object] = {
                        "normalized": parsed[0].isoformat(),
                        "trigger": trig_name,
                        "line_scope": scope,
                    }
                    spans.append(
                        EntitySpan(
                            start,
                            end,
                            date_text,
                            EntityLabel.DOB,
                            "date_dob",
                            self._confidence,
                            attrs,
                        )
                    )
                    break
        spans.sort(key=lambda s: s.start)
        return spans


def get_detector() -> DOBDetector:
    """Return a :class:`DOBDetector` instance."""

    return DOBDetector()
