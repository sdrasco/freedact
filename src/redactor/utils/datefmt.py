"""Lightweight helpers for parsing and formatting dates by style."""

from __future__ import annotations

import calendar
import re
from datetime import date

__all__ = ["parse_like", "format_like"]

_MONTHS: dict[str, int] = {name.lower(): i for i, name in enumerate(calendar.month_name) if name}

_RX_NUMERIC = re.compile(r"^\s*(\d{1,2})/(\d{1,2})/(\d{4})\s*$")
_RX_MONTH_NAME = re.compile(r"^\s*([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})\s*$")


Style = str


def parse_like(source: str) -> tuple[date, Style] | None:
    """Parse ``source`` into a :class:`date` and style tag.

    The function recognises numeric ``M/D/YYYY`` or ``MM/DD/YYYY`` forms and
    month name forms such as ``July 4, 1982``.  Whitespace around the date is
    ignored.  ``None`` is returned when parsing fails.
    """

    m = _RX_NUMERIC.fullmatch(source)
    if m:
        month, day, year = map(int, m.groups())
        try:
            return date(year, month, day), "MDY_NUMERIC"
        except ValueError:
            return None

    m = _RX_MONTH_NAME.fullmatch(source)
    if m:
        month_name, day_str, year_str = m.groups()
        month_val = _MONTHS.get(month_name.lower())
        if month_val is None:
            return None
        day = int(day_str)
        year = int(year_str)
        try:
            return date(year, month_val, day), "MONTH_NAME_COMMA_Y"
        except ValueError:
            return None

    return None


def format_like(d: date, style: Style) -> str:
    """Format ``d`` according to ``style`` returned by :func:`parse_like`."""

    if style == "MDY_NUMERIC":
        return f"{d.month:02d}/{d.day:02d}/{d.year:04d}"
    if style == "MONTH_NAME_COMMA_Y":
        month_name = calendar.month_name[d.month]
        return f"{month_name} {d.day}, {d.year}"
    raise ValueError(f"unsupported style: {style}")
