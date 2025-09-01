"""Shared character tables and helpers for detector modules."""

from __future__ import annotations

__all__ = [
    "RIGHT_TRIM_CHARS",
    "LEFT_WRAP_CHARS",
    "RIGHT_TRIM",
    "LEFT_WRAP",
    "rtrim_index",
]

RIGHT_TRIM_CHARS: str = ")]};:,.!?»”’>"
LEFT_WRAP_CHARS: str = "«“‘(<[{"

RIGHT_TRIM: frozenset[str] = frozenset(RIGHT_TRIM_CHARS)
LEFT_WRAP: frozenset[str] = frozenset(LEFT_WRAP_CHARS)


def rtrim_index(text: str, end: int) -> int:
    """Return ``end`` moved left past trailing ``RIGHT_TRIM`` characters."""

    while end > 0 and text[end - 1] in RIGHT_TRIM:
        end -= 1
    return end
