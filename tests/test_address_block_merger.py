from __future__ import annotations

from typing import cast

from redactor.detect.base import EntityLabel, EntitySpan
from redactor.preprocess.layout_reconstructor import merge_address_lines_into_blocks


def _make_span(
    text: str,
    start: int,
    end: int,
    line_kind: str,
    backend: str = "usaddress",
    confidence: float = 0.9,
) -> EntitySpan:
    attrs: dict[str, object] = {
        "backend": backend,
        "line_kind": line_kind,
        "components": {},
        "normalized": text[start:end],
    }
    return EntitySpan(
        start,
        end,
        text[start:end],
        EntityLabel.ADDRESS_BLOCK,
        "address_line",
        confidence,
        attrs,
    )


def test_two_line_address() -> None:
    line1 = "366 Broadway"
    line2 = "San Francisco, CA 94105"
    text = f"{line1}\n{line2}\n"
    span1 = _make_span(text, 0, len(line1), "street")
    span2 = _make_span(text, len(line1) + 1, len(line1) + 1 + len(line2), "city_state_zip")
    merged = merge_address_lines_into_blocks(text, [span1, span2])
    assert len(merged) == 1
    block = merged[0]
    assert block.start == 0
    assert block.end == len(text) - 1  # exclude final newline
    assert block.text == f"{line1}\n{line2}"
    assert cast(int, block.attrs["lines_count"]) == 2
    assert cast(bool, block.attrs["has_city_state_zip"]) is True
    assert cast(list[str], block.attrs["line_kinds"]) == ["street", "city_state_zip"]


def test_three_line_with_unit() -> None:
    line1 = "366 Broadway"
    line2 = "Suite 210"
    line3 = "San Francisco, CA 94105"
    text = f"{line1}\n{line2}\n{line3}"
    span1 = _make_span(text, 0, len(line1), "street")
    span2 = _make_span(text, len(line1) + 1, len(line1) + 1 + len(line2), "unit")
    span3 = _make_span(text, len(line1) + len(line2) + 2, len(text), "city_state_zip")
    merged = merge_address_lines_into_blocks(text, [span1, span2, span3])
    assert len(merged) == 1
    block = merged[0]
    assert block.start == 0
    assert block.end == len(text)
    assert cast(int, block.attrs["lines_count"]) == 3
    assert cast(list[str], block.attrs["line_kinds"]) == [
        "street",
        "unit",
        "city_state_zip",
    ]
    assert cast(bool, block.attrs["has_unit"]) is True


def test_allow_blank_line() -> None:
    line1 = "366 Broadway"
    blank = ""
    line3 = "San Francisco, CA 94105"
    text = f"{line1}\n{blank}\n{line3}"
    span1 = _make_span(text, 0, len(line1), "street")
    span3 = _make_span(text, len(line1) + 2, len(text), "city_state_zip")
    merged = merge_address_lines_into_blocks(text, [span1, span3])
    assert len(merged) == 1
    block = merged[0]
    assert block.text == text
    assert cast(int, block.attrs["lines_count"]) == 2


def test_unit_preceding_street() -> None:
    line1 = "Apt 5B"
    line2 = "123 Main St"
    line3 = "Springfield, IL 62704"
    text = f"{line1}\n{line2}\n{line3}"
    span1 = _make_span(text, 0, len(line1), "unit")
    span2 = _make_span(text, len(line1) + 1, len(line1) + 1 + len(line2), "street")
    span3 = _make_span(text, len(line1) + len(line2) + 2, len(text), "city_state_zip")
    merged = merge_address_lines_into_blocks(text, [span1, span2, span3])
    assert len(merged) == 1
    block = merged[0]
    assert block.start == 0
    assert block.end == len(text)
    assert cast(int, block.attrs["lines_count"]) == 3


def test_single_line_address_returns_block() -> None:
    text = "366 Broadway"
    span = _make_span(text, 0, len(text), "street")
    merged = merge_address_lines_into_blocks(text, [span])
    assert len(merged) == 1
    block = merged[0]
    assert block.start == 0 and block.end == len(text)
    assert cast(int, block.attrs["lines_count"]) == 1


def test_two_addresses_separated_by_non_address_line() -> None:
    a1_line1 = "366 Broadway"
    a1_line2 = "San Francisco, CA 94105"
    middle = "Contact"
    a2_line1 = "123 Main St"
    a2_line2 = "Springfield, IL 62704"
    text = f"{a1_line1}\n{a1_line2}\n{middle}\n{a2_line1}\n{a2_line2}"
    a1_span1 = _make_span(text, 0, len(a1_line1), "street")
    a1_start2 = len(a1_line1) + 1
    a1_end2 = a1_start2 + len(a1_line2)
    a1_span2 = _make_span(text, a1_start2, a1_end2, "city_state_zip")
    a2_start1 = len(a1_line1) + len(a1_line2) + len(middle) + 3
    a2_span1 = _make_span(text, a2_start1, a2_start1 + len(a2_line1), "street")
    a2_span2 = _make_span(text, a2_start1 + len(a2_line1) + 1, len(text), "city_state_zip")
    spans = [a1_span1, a1_span2, a2_span1, a2_span2]
    merged = merge_address_lines_into_blocks(text, spans)
    assert len(merged) == 2
    assert cast(int, merged[0].attrs["lines_count"]) == 2
    assert cast(int, merged[1].attrs["lines_count"]) == 2


def test_pass_through_non_address_span() -> None:
    line1 = "366 Broadway"
    line2 = "San Francisco, CA 94105"
    email = "info@example.com"
    text = f"{line1}\n{line2}\n{email}"
    street = _make_span(text, 0, len(line1), "street")
    city = _make_span(text, len(line1) + 1, len(line1) + 1 + len(line2), "city_state_zip")
    email_span = EntitySpan(
        len(line1) + len(line2) + 2,
        len(text),
        email,
        EntityLabel.EMAIL,
        "email",
        0.8,
    )
    merged = merge_address_lines_into_blocks(text, [street, city, email_span])
    assert len(merged) == 2
    assert merged[1] == email_span
