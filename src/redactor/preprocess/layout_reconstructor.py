"""Layout-aware address block reconstruction.

This module provides helpers to reason about physical line layout in a piece
of text and a merger that combines consecutive address line detections into a
single multi-line ``ADDRESS_BLOCK`` span.  Adjacent address lines are merged
when they appear on subsequent lines or are separated by exactly one blank
line.  A ``unit`` line may also precede a ``street`` line and still be merged
into the same block.  Trailing end-of-line characters are excluded from merged
spans so that redaction replaces only visible characters.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, cast

from redactor.detect.base import EntityLabel, EntitySpan

LineIndex = tuple[tuple[int, int, str], ...]


def build_line_index(text: str) -> LineIndex:
    """Return start/end offsets for each line in ``text``.

    Each entry contains ``(line_start, line_end_no_eol, eol_str)``.  The end
    offset excludes any trailing line ending characters.  ``eol_str`` is ``""``
    when the line does not terminate with a newline sequence.
    """

    lines: list[tuple[int, int, str]] = []
    i = 0
    length = len(text)
    while i < length:
        line_start = i
        while i < length and text[i] not in "\n\r":
            i += 1
        line_end = i
        eol = ""
        if i < length:
            ch = text[i]
            if ch == "\r" and i + 1 < length and text[i + 1] == "\n":
                eol = "\r\n"
                i += 2
            else:
                eol = ch
                i += 1
        lines.append((line_start, line_end, eol))
    return tuple(lines)


def find_line_for_char(index: int, line_index: LineIndex) -> int:
    """Return the 0-based line number containing ``index`` via binary search."""

    lo = 0
    hi = len(line_index) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        start, end_no_eol, eol = line_index[mid]
        end_with_eol = end_no_eol + len(eol)
        if index < start:
            hi = mid - 1
        elif index >= end_with_eol:
            lo = mid + 1
        else:
            return mid
    raise ValueError("index out of range")


@dataclass(slots=True)
class _LineInfo:
    span: EntitySpan
    line_no: int
    line_kind: str


def _merge_block(lines: List[_LineInfo], text: str, line_index: LineIndex) -> EntitySpan:
    start = min(li.span.start for li in lines)
    last_line_no = lines[-1].line_no
    end = line_index[last_line_no][1]
    block_text = text[start:end]

    backends = {cast(str, li.span.attrs.get("backend", "")) for li in lines}
    backend = backends.pop() if len(backends) == 1 else "mixed"

    line_kinds = [li.line_kind for li in lines]
    components = [cast(dict[str, str], li.span.attrs.get("components", {})) for li in lines]
    normalized_parts = [
        cast(str, li.span.attrs.get("normalized", "")).strip()
        for li in lines
        if cast(str, li.span.attrs.get("normalized", "")).strip()
    ]
    normalized_block = ", ".join(normalized_parts)

    confidence = min(0.99, max(li.span.confidence for li in lines) + 0.01)

    attrs = {
        "backend": backend,
        "lines_count": len(lines),
        "line_kinds": line_kinds,
        "components": components,
        "normalized_block": normalized_block,
        "has_unit": any(k == "unit" for k in line_kinds),
        "has_city_state_zip": any(k == "city_state_zip" for k in line_kinds),
        "merged_from": [{"start": li.span.start, "end": li.span.end} for li in lines],
    }

    return EntitySpan(
        start,
        end,
        block_text,
        EntityLabel.ADDRESS_BLOCK,
        "address_block_merge",
        confidence,
        attrs,
    )


def merge_address_lines_into_blocks(text: str, spans: list[EntitySpan]) -> list[EntitySpan]:
    """Merge adjacent address line spans into multi-line blocks.

    Non-address spans are returned unchanged.  The function tolerates a single
    blank line between address components and excludes trailing newline
    characters from the resulting block spans.
    """

    line_index = build_line_index(text)
    address_lines: list[_LineInfo] = []
    others: list[EntitySpan] = []

    for span in spans:
        if span.label is EntityLabel.ADDRESS_BLOCK and span.source == "address_line":
            line_kind = cast(str, span.attrs.get("line_kind", ""))
            line_no = find_line_for_char(span.start, line_index)
            address_lines.append(_LineInfo(span, line_no, line_kind))
        else:
            others.append(span)

    address_lines.sort(key=lambda li: (li.line_no, li.span.start))

    merged: list[EntitySpan] = []
    i = 0
    n = len(address_lines)
    while i < n:
        current = address_lines[i]
        block_lines: list[_LineInfo] = [current]
        j = i + 1

        if (
            current.line_kind == "unit"
            and j < n
            and address_lines[j].line_no == current.line_no + 1
            and address_lines[j].line_kind == "street"
        ):
            block_lines.append(address_lines[j])
            j += 1

        while j < n:
            next_line = address_lines[j]
            prev_line = block_lines[-1]
            gap = next_line.line_no - prev_line.line_no
            if gap == 0:
                if next_line.line_kind in {"unit", "city_state_zip", "street"}:
                    block_lines.append(next_line)
                    j += 1
                else:
                    break
            elif gap == 1:
                if next_line.line_kind in {"unit", "city_state_zip"}:
                    block_lines.append(next_line)
                    j += 1
                else:
                    break
            elif gap == 2:
                idx = prev_line.line_no + 1
                if (
                    idx < len(line_index)
                    and line_index[idx][0] == line_index[idx][1]
                    and next_line.line_kind in {"unit", "city_state_zip"}
                ):
                    block_lines.append(next_line)
                    j += 1
                else:
                    break
            else:
                break

        merged.append(_merge_block(block_lines, text, line_index))
        i = j

    result = others + merged
    result.sort(key=lambda s: s.start)
    return result


__all__ = [
    "build_line_index",
    "find_line_for_char",
    "merge_address_lines_into_blocks",
]
