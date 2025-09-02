from __future__ import annotations

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


def test_no_generic_account_ids() -> None:
    cfg = load_config("examples/safe-overrides.yml")
    text = "Please review account Acct # 0034-567-89012 before closing."
    _normalized, redacted, plan, spans = _run_pipeline(text, cfg)
    assert all(sp.label is not EntityLabel.ACCOUNT_ID for sp in spans)
    assert all(p.label is not EntityLabel.ACCOUNT_ID for p in plan)
    assert "Acct_" not in redacted
