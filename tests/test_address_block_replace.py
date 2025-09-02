from __future__ import annotations

import re
from typing import Tuple

import pytest

from redactor.config import load_config
from redactor.detect.address_libpostal import AddressLineDetector
from redactor.detect.base import EntityLabel
from redactor.link import span_merger
from redactor.link.address_merge import merge_address_lines_into_blocks
from redactor.replace.applier import apply_plan
from redactor.replace.plan_builder import PlanEntry, build_replacement_plan
from redactor.verify import scanner


def _pipeline(text: str) -> Tuple[str, list[PlanEntry]]:
    cfg = load_config()
    det = AddressLineDetector()
    try:
        lines = det.detect(text)
    except RuntimeError:
        pytest.skip("usaddress library not available")
    addr_lines = [sp for sp in lines if sp.label is EntityLabel.ADDRESS_BLOCK]
    merged = merge_address_lines_into_blocks(text, addr_lines)
    merged_spans = span_merger.merge_spans(merged, cfg)
    plan = build_replacement_plan(text, merged_spans, cfg)
    return apply_plan(text, plan)


def test_replacement_shape_two_lines() -> None:
    text = "366 Broadway\nCambridge, MA 02139\n"
    redacted, plan = _pipeline(text)
    pe = plan[0]
    assert pe.replacement.count("\n") == 1
    assert "Broadway" not in pe.replacement
    assert "Cambridge, MA 02139" not in pe.replacement
    assert re.search(r"\b\d{5}(?:-\d{4})?\b", pe.replacement)


def test_preserve_unit_keyword() -> None:
    text = "366 Broadway Apt 5B\nCambridge, MA 02139"
    redacted, plan = _pipeline(text)
    first_line = plan[0].replacement.splitlines()[0]
    assert re.search(r"\b(Apt|Ste|Suite|Unit|#)\b", first_line)


def test_verifier_ignores_replacement_lines() -> None:
    text = "366 Broadway\nCambridge, MA 02139"
    redacted, plan = _pipeline(text)
    report = scanner.scan_text(redacted, load_config(), applied_plan=plan)
    assert report.residual_count == 0
    reasons = {f.ignored_reason for f in report.ignored}
    assert "replacement_match_block_line" in reasons
    assert "in_address_block_replacement" in reasons


def test_mixed_eols() -> None:
    text = "366 Broadway\r\nCambridge, MA 02139"
    redacted, plan = _pipeline(text)
    assert "\r\n" in plan[0].replacement
