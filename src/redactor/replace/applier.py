"""Replacement plan applier.

Plan entries reference half‑open character ranges ``[start, end)`` in the
original text.  To avoid shifting indices the applier sorts plan entries in
reverse order by start position and performs replacements from the end of the
text towards the beginning.  Basic validation ensures spans do not overlap and
fall within bounds.  Applying the same plan to already‑redacted text is
idempotent: if the target slice already matches the replacement it is left
untouched.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from redactor.utils.errors import OverlapError, SpanOutOfBoundsError

from .plan_builder import PlanEntry

__all__ = ["apply_plan"]


def _validate_plan(plan: Iterable[PlanEntry], text_len: int) -> None:
    ordered = sorted(plan, key=lambda p: p.start)
    prev_end = 0
    for entry in ordered:
        if entry.start < prev_end:
            msg = f"plan entries overlap: {prev_end} > {entry.start}"
            raise OverlapError(msg)
        if not (0 <= entry.start <= entry.end <= text_len):
            msg = f"plan entry out of bounds: {entry.start}-{entry.end}"
            raise SpanOutOfBoundsError(msg)
        prev_end = entry.end


def apply_plan(text: str, plan: list[PlanEntry]) -> tuple[str, list[PlanEntry]]:
    """Apply ``plan`` to ``text`` returning ``(new_text, applied_plan)``."""

    if not plan:
        return text, []

    _validate_plan(plan, len(text))
    ordered = sorted(plan, key=lambda p: (p.start, p.end), reverse=True)

    pieces: list[str] = []
    cursor = len(text)
    applied: list[PlanEntry] = []

    for idx, entry in enumerate(ordered):
        start = entry.start
        end = entry.end
        repl = entry.replacement
        existing_end = start + len(repl)
        if text[start:existing_end] == repl:
            pieces.append(text[existing_end:cursor])
            pieces.append(repl)
            cursor = start
        else:
            pieces.append(text[end:cursor])
            pieces.append(repl)
            cursor = start
        applied_meta = dict(entry.meta)
        applied_meta["applied_index"] = idx
        applied.append(
            replace(
                entry,
                meta=applied_meta,
            )
        )
    pieces.append(text[:cursor])
    new_text = "".join(reversed(pieces))
    return new_text, applied
