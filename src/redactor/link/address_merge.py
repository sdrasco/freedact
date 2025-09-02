"""Merge contiguous address lines into ADDRESS_BLOCK spans.

This module groups adjacent address line spans into multi-line address blocks
while preserving the original line spans. Blocks are recognised when street or
PO Box lines are followed by a ``city_state_zip`` line separated by at most one
blank line. The merged span's ``attrs`` describe each participating line and
whether a blank line was present.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from typing import List, Sequence, Tuple, cast

from redactor.detect.base import EntityLabel, EntitySpan

__all__ = ["merge_address_lines_into_blocks"]


@dataclass(slots=True)
class _LineInfo:
    span: EntitySpan
    line_no: int
    kind: str
    start_trim: int
    end_trim: int
    text: str


def _split_lines(text: str) -> Tuple[List[int], List[Tuple[int, int, str, str]]]:
    """Return (line_starts, line_info) for ``text``.

    ``line_info`` entries contain ``(start, end_no_eol, line_text, eol)`` where
    ``line_text`` excludes any end-of-line marker. ``line_starts`` lists the
    start offset of each line for binary searching.
    """

    starts: List[int] = []
    info: List[Tuple[int, int, str, str]] = []
    pos = 0
    for raw in text.splitlines(keepends=True):
        line = raw.rstrip("\r\n")
        eol = raw[len(line) :]
        start = pos
        end_no_eol = start + len(line)
        starts.append(start)
        info.append((start, end_no_eol, line, eol))
        pos += len(raw)
    return starts, info


def _line_for_pos(pos: int, starts: Sequence[int]) -> int:
    idx = bisect_right(starts, pos) - 1
    if idx < 0:
        idx = 0
    return idx


def merge_address_lines_into_blocks(text: str, line_spans: list[EntitySpan]) -> list[EntitySpan]:
    """Return ``line_spans`` plus merged ADDRESS_BLOCK spans.

    ``line_spans`` must contain per-line address spans as produced by
    :mod:`redactor.detect.address_libpostal`. Newly created block spans are
    appended and no original spans are removed.
    """

    if not line_spans:
        return []

    starts, line_info = _split_lines(text)

    infos: List[_LineInfo] = []
    for sp in line_spans:
        line_no = _line_for_pos(sp.start, starts)
        start_line, end_no_eol, line_text, _eol = line_info[line_no]
        left = len(line_text) - len(line_text.lstrip())
        right = len(line_text.rstrip())
        start_trim = start_line + left
        end_trim = start_line + right
        kind = cast(str, sp.attrs.get("line_kind", ""))
        infos.append(
            _LineInfo(
                span=sp,
                line_no=line_no,
                kind=kind,
                start_trim=start_trim,
                end_trim=end_trim,
                text=text[start_trim:end_trim],
            )
        )

    infos.sort(key=lambda li: li.line_no)

    candidates: List[Tuple[EntitySpan, set[int]]] = []

    for idx, info in enumerate(infos):
        if info.kind != "city_state_zip":
            continue
        block_lines: List[_LineInfo] = [info]
        used_lines: set[int] = {info.line_no}
        had_blank = False
        line_no = info.line_no
        j = idx - 1
        while j >= 0:
            prev = infos[j]
            gap = line_no - prev.line_no
            if gap == 1 and prev.kind in {"street", "unit", "po_box"}:
                block_lines.insert(0, prev)
                used_lines.add(prev.line_no)
                line_no = prev.line_no
                j -= 1
                continue
            if gap == 2 and prev.kind in {"street", "unit", "po_box"}:
                between = line_info[line_no - 1][2].strip()
                if not between:
                    had_blank = True
                    block_lines.insert(0, prev)
                    used_lines.add(prev.line_no)
                    line_no = prev.line_no
                    j -= 1
                    continue
            break
        if len(block_lines) < 2:
            continue
        start = block_lines[0].start_trim
        end = block_lines[-1].end_trim
        lines_attr = [
            {
                "kind": bl.kind,
                "text": bl.text,
                "start": bl.start_trim,
                "end": bl.end_trim,
            }
            for bl in block_lines
        ]
        components = cast(dict[str, str], block_lines[-1].span.attrs.get("components", {}))
        zip_code = components.get("ZipCode", "")
        zip_kind = "zip9" if len(zip_code.replace("-", "")) > 5 else "zip5" if zip_code else ""
        confidence = min(0.99, max(bl.span.confidence for bl in block_lines) + 0.01)
        attrs: dict[str, object] = {
            "lines": lines_attr,
            "zip_kind": zip_kind or None,
            "had_blank_line_between": had_blank,
            "source_hint": "contiguous_merge_v1",
        }
        block_span = EntitySpan(
            start,
            end,
            text[start:end],
            EntityLabel.ADDRESS_BLOCK,
            "address_block_merge",
            confidence,
            attrs,
        )
        candidates.append((block_span, used_lines))

    selected: List[EntitySpan] = []
    taken: set[int] = set()
    for span, lines_set in sorted(candidates, key=lambda t: t[0].end - t[0].start, reverse=True):
        if lines_set.isdisjoint(taken):
            selected.append(span)
            taken.update(lines_set)

    result = list(line_spans) + selected
    result.sort(key=lambda s: s.start)
    return result
