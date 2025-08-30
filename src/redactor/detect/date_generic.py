"""Generic date detector with lightweight normalisation.

This detector focuses on a small set of high‑precision date patterns and
avoids heavy parsing libraries.  Supported formats (case‑insensitive) are::

    Month D, YYYY   e.g. "July 4, 1982" (comma optional)
    D Month YYYY    e.g. "4 July 1982"
    YYYY-MM-DD      ISO style with four digit year
    M/D/YYYY        or ``M-D-YYYY`` with a four digit year (US ordering)

Normalisation is best‑effort and yields a ``YYYY-MM-DD`` string when the
components form a valid Gregorian date.  The numeric format assumes the
first number is the month (US default).  Invalid combinations still emit a
``DATE_GENERIC`` span but with ``normalized`` set to ``None``.
"""

from __future__ import annotations

import re
from typing import Dict, Tuple

from .base import DetectionContext, EntityLabel, EntitySpan

__all__ = ["DateGenericDetector", "get_detector"]

# ---------------------------------------------------------------------------
# Helpers and regular expressions
# ---------------------------------------------------------------------------

TRAILING_PUNCTUATION = ")]};:,.!?»”’>"

_MONTHS: Dict[str, str] = {
    "january": "01",
    "jan": "01",
    "february": "02",
    "feb": "02",
    "march": "03",
    "mar": "03",
    "april": "04",
    "apr": "04",
    "may": "05",
    "june": "06",
    "jun": "06",
    "july": "07",
    "jul": "07",
    "august": "08",
    "aug": "08",
    "september": "09",
    "sep": "09",
    "sept": "09",
    "october": "10",
    "oct": "10",
    "november": "11",
    "nov": "11",
    "december": "12",
    "dec": "12",
}

_MONTH_NAME_PATTERN = "|".join(sorted(_MONTHS.keys(), key=len, reverse=True))

_MONTH_NAME_MDY_RE = re.compile(
    rf"\b({_MONTH_NAME_PATTERN})\s+(\d{{1,2}}(?:st|nd|rd|th)?),?\s+(\d{{4}})\b",
    re.IGNORECASE,
)

_MONTH_NAME_DMY_RE = re.compile(
    rf"\b(\d{{1,2}}(?:st|nd|rd|th)?)\s+({_MONTH_NAME_PATTERN})\s+(\d{{4}})\b",
    re.IGNORECASE,
)

_ISO_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")

_NUMERIC_RE = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b")


def _is_leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def _days_in_month(year: int, month: int) -> int:
    if month in {1, 3, 5, 7, 8, 10, 12}:
        return 31
    if month in {4, 6, 9, 11}:
        return 30
    if month == 2:
        return 29 if _is_leap(year) else 28
    return 0


def _normalize(year: str, month: str, day: str) -> Tuple[str | None, Dict[str, str] | None]:
    """Return normalised date and components if valid."""

    try:
        y = int(year)
        m = int(month)
        d = int(day)
    except ValueError:
        return None, None
    if not 1 <= m <= 12:
        return None, None
    if not 1 <= d <= _days_in_month(y, m):
        return None, None
    normalized = f"{y:04d}-{m:02d}-{d:02d}"
    components = {"year": f"{y:04d}", "month": f"{m:02d}", "day": f"{d:02d}"}
    return normalized, components


# ---------------------------------------------------------------------------
# Detector implementation
# ---------------------------------------------------------------------------


class DateGenericDetector:
    """Detect generic dates within text."""

    _confidence_named: float = 0.97
    _confidence_numeric: float = 0.94

    def name(self) -> str:  # pragma: no cover - trivial
        return "date_generic"

    def detect(self, text: str, context: DetectionContext | None = None) -> list[EntitySpan]:
        """Detect dates in ``text``."""

        _ = context
        spans: list[EntitySpan] = []

        for match in _MONTH_NAME_MDY_RE.finditer(text):
            month_name, day_raw, year = match.groups()
            start, end = match.span()
            date_text = text[start:end]
            while date_text and date_text[-1] in TRAILING_PUNCTUATION:
                end -= 1
                date_text = date_text[:-1]
            day = re.sub(r"(?i)(st|nd|rd|th)$", "", day_raw)
            month_num = _MONTHS.get(month_name.lower(), "00")
            normalized, components = _normalize(year, month_num, day)
            attrs: Dict[str, object] = {"format": "month_name_mdY", "normalized": normalized}
            if components:
                attrs["components"] = components
            spans.append(
                EntitySpan(
                    start,
                    end,
                    date_text,
                    EntityLabel.DATE_GENERIC,
                    "date_generic",
                    self._confidence_named,
                    attrs,
                )
            )

        for match in _MONTH_NAME_DMY_RE.finditer(text):
            day_raw, month_name, year = match.groups()
            start, end = match.span()
            date_text = text[start:end]
            while date_text and date_text[-1] in TRAILING_PUNCTUATION:
                end -= 1
                date_text = date_text[:-1]
            day = re.sub(r"(?i)(st|nd|rd|th)$", "", day_raw)
            month_num = _MONTHS.get(month_name.lower(), "00")
            normalized, components = _normalize(year, month_num, day)
            attrs = {"format": "month_name_dmY", "normalized": normalized}
            if components:
                attrs["components"] = components
            spans.append(
                EntitySpan(
                    start,
                    end,
                    date_text,
                    EntityLabel.DATE_GENERIC,
                    "date_generic",
                    self._confidence_named,
                    attrs,
                )
            )

        for match in _ISO_RE.finditer(text):
            year, month, day = match.groups()
            start, end = match.span()
            date_text = text[start:end]
            while date_text and date_text[-1] in TRAILING_PUNCTUATION:
                end -= 1
                date_text = date_text[:-1]
            normalized, components = _normalize(year, month, day)
            attrs = {"format": "iso", "normalized": normalized}
            if components:
                attrs["components"] = components
            spans.append(
                EntitySpan(
                    start,
                    end,
                    date_text,
                    EntityLabel.DATE_GENERIC,
                    "date_generic",
                    self._confidence_named,
                    attrs,
                )
            )

        for match in _NUMERIC_RE.finditer(text):
            month, day, year = match.groups()
            start, end = match.span()
            date_text = text[start:end]
            while date_text and date_text[-1] in TRAILING_PUNCTUATION:
                end -= 1
                date_text = date_text[:-1]
            normalized, components = _normalize(year, month, day)
            attrs = {"format": "mdY_numeric", "normalized": normalized}
            if components:
                attrs["components"] = components
            spans.append(
                EntitySpan(
                    start,
                    end,
                    date_text,
                    EntityLabel.DATE_GENERIC,
                    "date_generic",
                    self._confidence_numeric,
                    attrs,
                )
            )

        unique: Dict[Tuple[int, int], EntitySpan] = {}
        for span in spans:
            key = (span.start, span.end)
            if key not in unique:
                unique[key] = span
        return sorted(unique.values(), key=lambda s: s.start)


def get_detector() -> DateGenericDetector:
    """Return a :class:`DateGenericDetector` instance."""

    return DateGenericDetector()
