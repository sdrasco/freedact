from __future__ import annotations

from pathlib import Path

import pytest

from redactor.cli import _run_detectors
from redactor.config import ConfigModel, load_config
from redactor.detect.base import DetectionContext, EntityLabel, EntitySpan
from redactor.filters import filter_spans_for_safety, find_heading_ranges
from redactor.link import alias_resolver, span_merger
from redactor.preprocess import layout_reconstructor
from redactor.preprocess.normalizer import normalize
from redactor.replace.applier import apply_plan
from redactor.replace.plan_builder import PlanEntry, build_replacement_plan
from redactor.utils.textspan import build_line_starts


def _run_pipeline(
    text: str, cfg: ConfigModel
) -> tuple[str, str, list[PlanEntry], list[EntitySpan]]:
    norm = normalize(text)
    normalized = norm.text
    context = DetectionContext(
        locale=cfg.locale, line_starts=build_line_starts(normalized), config=cfg
    )
    spans = _run_detectors(normalized, cfg, context)
    spans = layout_reconstructor.merge_address_lines_into_blocks(normalized, spans)
    address_blocks = [sp for sp in spans if sp.label is EntityLabel.ADDRESS_BLOCK]
    heading_ranges = find_heading_ranges(normalized)
    spans = filter_spans_for_safety(
        spans,
        heading_ranges=heading_ranges,
        address_blocks=address_blocks,
        protect_headings=cfg.filters.protect_headings,
        gpe_outside_addresses=cfg.filters.gpe_outside_addresses,
    )
    filtered_spans = list(spans)
    spans, clusters = alias_resolver.resolve_aliases(normalized, spans, cfg)
    merged = span_merger.merge_spans(spans, cfg)
    plan = build_replacement_plan(normalized, merged, cfg, clusters=clusters)
    redacted, _applied = apply_plan(normalized, plan)
    return normalized, redacted, plan, filtered_spans


def test_safe_profile_standalone_gpe(tmp_path: Path) -> None:
    cfg = load_config("examples/safe-overrides.yml")
    text = "Cambridge is a city in Massachusetts."
    normalized, redacted, plan, spans = _run_pipeline(text, cfg)
    assert normalized == redacted
    assert plan == []
    assert all(sp.label not in {EntityLabel.GPE, EntityLabel.LOC} for sp in spans)


def test_safe_profile_address_block(tmp_path: Path) -> None:
    pytest.importorskip("usaddress")
    cfg = load_config("examples/safe-overrides.yml")
    text = "366 Broadway\nCambridge, MA 02139"
    normalized, redacted, plan, _spans = _run_pipeline(text, cfg)
    assert len(plan) == 1
    entry = plan[0]
    assert entry.label is EntityLabel.ADDRESS_BLOCK
    assert "\n" in entry.replacement
    assert "Acct_" not in entry.replacement
