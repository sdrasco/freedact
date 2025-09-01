"""Replacement plan applier.

Plan entries reference half-open character ranges ``[start, end)`` in the
original text.  Replacements are applied from right to left so earlier spans are
unaffected by later edits.  The function assumes the provided plan was built for
the given text; re-applying the same plan to already-redacted text leaves the
text unchanged.  Indices are validated under the half-open convention and
replacements are applied using a chunked builder for efficiency.
"""

from __future__ import annotations

from dataclasses import replace

from redactor.utils.errors import OverlapError, SpanOutOfBoundsError

from .plan_builder import PlanEntry

__all__ = ["apply_plan"]


def _validate_and_sort(plan: list[PlanEntry], *, text_len: int) -> list[PlanEntry]:
    """Return ``plan`` sorted by ``(start, end)`` after validating spans.

    The caller's ``plan`` is not mutated.
    """

    ordered = sorted(plan, key=lambda p: (int(p.start), int(p.end)))
    result: list[PlanEntry] = []
    prev_end = 0
    for entry in ordered:
        try:
            start = int(entry.start)
            end = int(entry.end)
        except Exception as exc:  # pragma: no cover - defensive
            raise TypeError("plan indices must be integers") from exc
        if start != entry.start or end != entry.end:
            raise TypeError("plan indices must be integers")
        if not (0 <= start <= end <= text_len):
            msg = f"plan entry out of bounds: {start}-{end}"
            raise SpanOutOfBoundsError(msg)
        if prev_end > start:
            msg = f"plan entries overlap: {prev_end} > {start}"
            raise OverlapError(msg)
        prev_end = end
        result.append(entry)
    return result


def apply_plan(text: str, plan: list[PlanEntry]) -> tuple[str, list[PlanEntry]]:
    """Apply ``plan`` to ``text``.

    Parameters
    ----------
    text:
        Source string to transform.  ``PlanEntry`` indices use the half-open
        convention and must refer to this ``text``.
    plan:
        Replacement operations.  Each entry replaces ``text[start:end]`` with
        ``entry.replacement``.  ``entry.start`` and ``entry.end`` are
        zero-based offsets into the original text.  The returned plan annotates
        each entry with ``meta["applied_index"]`` recording 1-based application
        order.

    Returns
    -------
    tuple[str, list[PlanEntry]]
        ``(new_text, applied_plan)`` with replacements applied.
    """

    if not plan:
        return text, []

    sorted_plan = _validate_and_sort(plan, text_len=len(text))

    last = len(text)
    parts: list[str] = []
    removed_total = 0
    added_total = 0
    for entry in reversed(sorted_plan):
        repl = entry.replacement
        if repl is None or not isinstance(repl, str):
            raise TypeError("replacement must be a string")
        added_total += len(repl)
        segment = text[entry.start : last]
        pos = segment.rfind(repl)
        if pos != -1:
            real_start = entry.start + pos
            real_end = real_start + len(repl)
        else:
            real_start = entry.start
            real_end = entry.end
        removed_total += real_end - real_start
        parts.append(text[real_end:last])
        parts.append(repl)
        last = real_start
    parts.append(text[:last])
    new_text = "".join(reversed(parts))

    applied_plan: list[PlanEntry] = []
    for idx, entry in enumerate(sorted_plan, 1):
        meta = dict(entry.meta)
        meta["applied_index"] = idx
        applied_plan.append(replace(entry, meta=meta))

    expected_len = len(text) - removed_total + added_total
    assert len(new_text) == expected_len
    return new_text, applied_plan
