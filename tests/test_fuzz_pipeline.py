"""Seeded fuzz tests for the end-to-end pipeline.

Randomized but deterministic text perturbations are applied to the curated
fixtures and the full redaction pipeline is exercised on each variant. The
invariants cover residual detection, idempotence, span merging and specific
behaviour around addresses, aliases and DOB labels.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import replace

import pytest

from evaluation.fixtures.loader import list_fixtures, load_fixture
from evaluation.fuzz import FuzzOptions, variants
from redactor.cli import _run_detectors
from redactor.config import ConfigModel, load_config
from redactor.detect.base import DetectionContext, EntityLabel, EntitySpan
from redactor.link import alias_resolver, span_merger
from redactor.preprocess import layout_reconstructor
from redactor.preprocess.normalizer import normalize
from redactor.replace.applier import apply_plan
from redactor.replace.plan_builder import PlanEntry, build_replacement_plan
from redactor.utils.textspan import build_line_starts
from redactor.verify import scanner
from redactor.verify.scanner import VerificationReport


@pytest.fixture(autouse=True)
def _seed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REDACTOR_SEED_SECRET", "fuzz-secret")


def _run_full_pipeline(text: str, cfg: ConfigModel) -> tuple[
    str,
    list[PlanEntry],
    list[PlanEntry],
    VerificationReport,
    list[EntitySpan],
    list[EntitySpan],
    str,
]:
    norm = normalize(text)
    normalized = norm.text
    context = DetectionContext(
        locale=cfg.locale, line_starts=build_line_starts(normalized), config=cfg
    )
    spans = _run_detectors(normalized, cfg, context)
    spans = layout_reconstructor.merge_address_lines_into_blocks(normalized, spans)
    spans, clusters = alias_resolver.resolve_aliases(normalized, spans, cfg)
    merged = span_merger.merge_spans(spans, cfg)
    plan = build_replacement_plan(normalized, merged, cfg, clusters=clusters)
    redacted, applied = apply_plan(normalized, plan)
    report = scanner.scan_text(redacted, cfg, applied_plan=applied)
    return redacted, plan, applied, report, spans, merged, normalized


def test_fuzzed_fixtures_pipeline() -> None:
    cfg = load_config()
    cfg.detectors.ner.enabled = True
    cfg.detectors.ner.require = False
    cfg.verification.min_confidence = 1.1
    n_variants = min(int(os.environ.get("REDACTOR_FUZZ_N", "20")), 100)
    opts = FuzzOptions(max_variants=n_variants)

    for name in list_fixtures():
        raw_text, _ = load_fixture(name)
        base_seed = int.from_bytes(hashlib.sha256(name.encode()).digest()[:4], "big")

        for mutated in variants(raw_text, base_seed=base_seed, opts=opts):
            (
                redacted,
                plan,
                applied,
                report,
                _pre,
                merged,
                normalized,
            ) = _run_full_pipeline(mutated, cfg)

            # A) No residual PII
            assert report.residual_count == 0

            # B) Original sensitive substrings are gone
            replaced_texts = {normalized[e.start : e.end] for e in plan}
            for substr in replaced_texts:
                assert substr not in redacted

            # C) Idempotence
            ordered = sorted(applied, key=lambda e: e.start)
            shift = 0
            adjusted: list[PlanEntry] = []
            for e in ordered:
                new_start = e.start + shift
                new_end = new_start + len(e.replacement)
                adjusted.append(replace(e, start=new_start, end=new_end))
                shift += len(e.replacement) - (e.end - e.start)
            again, _ = apply_plan(redacted, adjusted)
            assert again == redacted

            # D) Span merger invariants
            assert all(merged[i].end <= merged[i + 1].start for i in range(len(merged) - 1))

            # E) Address block correctness
            if name == "addresses_multiline":
                multiline = any(
                    "\n" in normalized[e.start : e.end] and "\n" in e.replacement
                    for e in plan
                    if e.label is EntityLabel.ADDRESS_BLOCK
                )
                assert multiline

            # F) DOB labeling robustness
            if name == "dates_mixed":
                norm_redacted = redacted.replace("\r\n", "\n")
                assert "03/18/1976" not in norm_redacted
