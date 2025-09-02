from __future__ import annotations

from typing import cast

import pytest

from redactor.detect.address_libpostal import AddressLineDetector
from redactor.detect.base import EntityLabel, EntitySpan
from redactor.link.address_merge import merge_address_lines_into_blocks


def _detect_lines(text: str) -> list[EntitySpan]:
    det = AddressLineDetector()
    try:
        spans = det.detect(text)
    except RuntimeError:
        pytest.skip("usaddress library not available")
    return [sp for sp in spans if sp.label is EntityLabel.ADDRESS_BLOCK]


def test_merge_two_lines() -> None:
    text = "366 Broadway\nCambridge, MA 02139\n"
    lines = _detect_lines(text)
    merged = merge_address_lines_into_blocks(text, lines)
    blocks = [sp for sp in merged if sp.source == "address_block_merge"]
    assert len(blocks) == 1
    block = blocks[0]
    assert block.text.count("\n") == 1
    lines_attr = cast(list[dict[str, object]], block.attrs["lines"])
    kinds = [line["kind"] for line in lines_attr]
    assert kinds == ["street", "city_state_zip"]


def test_merge_po_box() -> None:
    text = "PO Box 123\nCambridge, MA 02139"
    lines = _detect_lines(text)
    merged = merge_address_lines_into_blocks(text, lines)
    block = [sp for sp in merged if sp.source == "address_block_merge"][0]
    lines_attr = cast(list[dict[str, object]], block.attrs["lines"])
    kinds = [line["kind"] for line in lines_attr]
    assert kinds[0] == "po_box"


def test_merge_with_unit() -> None:
    text = "366 Broadway Apt 5B\nCambridge, MA 02139"
    lines = _detect_lines(text)
    merged = merge_address_lines_into_blocks(text, lines)
    block = [sp for sp in merged if sp.source == "address_block_merge"][0]
    lines_attr = cast(list[dict[str, object]], block.attrs["lines"])
    kinds = [line["kind"] for line in lines_attr]
    assert kinds[-1] == "city_state_zip"
    assert kinds[0] in {"street", "unit"}


def test_no_merge_far_apart() -> None:
    text = "366 Broadway\n\nSee you soon\nCambridge, MA 02139"
    lines = _detect_lines(text)
    merged = merge_address_lines_into_blocks(text, lines)
    blocks = [sp for sp in merged if sp.source == "address_block_merge"]
    assert not blocks
    assert len(merged) == len(lines)
