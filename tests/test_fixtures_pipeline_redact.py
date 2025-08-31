from __future__ import annotations

import re
from typing import Any, cast

import pytest

from evaluation.fixtures.loader import list_fixtures, load_fixture
from redactor.cli import _run_detectors
from redactor.config import ConfigModel, load_config
from redactor.detect.base import DetectionContext, EntityLabel
from redactor.link import alias_resolver, span_merger
from redactor.preprocess import layout_reconstructor
from redactor.preprocess.normalizer import normalize
from redactor.replace.applier import apply_plan
from redactor.replace.plan_builder import PlanEntry, build_replacement_plan
from redactor.utils.textspan import build_line_starts
from redactor.verify import scanner
from redactor.verify.scanner import VerificationReport


@pytest.fixture(autouse=True)
def fixed_seed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REDACTOR_SEED_SECRET", "fixture-secret")


def _run_pipeline(
    text: str, cfg: ConfigModel
) -> tuple[str, str, list[PlanEntry], VerificationReport]:
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
    return normalized, redacted, plan, report


def test_pipeline_redacts_fixtures() -> None:
    cfg = load_config()
    cfg.detectors.ner.enabled = True
    cfg.detectors.ner.require = False
    for name in list_fixtures():
        text, ann = load_fixture(name)
        normalized, redacted, plan, report = _run_pipeline(text, cfg)

        assert report.residual_count == 0
        assert redacted != normalized
        assert plan

        ann_spans = cast(list[dict[str, Any]], ann["spans"])
        ann_labels = {EntityLabel[cast(str, s["label"])] for s in ann_spans}
        expected = {lbl for lbl in ann_labels if lbl is not EntityLabel.DATE_GENERIC}
        plan_labels = {entry.label for entry in plan}
        for lbl in expected:
            assert lbl in plan_labels

        if name == "example_hereinafter":
            person_first: str | None = None
            alias_repls: list[str] = []
            for entry in plan:
                orig = normalized[entry.start : entry.end]
                if entry.label is EntityLabel.PERSON and orig == "John Doe":
                    person_first = entry.replacement.split()[0]
                if entry.label is EntityLabel.ALIAS_LABEL and orig == "Morgan":
                    alias_repls.append(entry.replacement)
            assert person_first and alias_repls
            for repl in alias_repls:
                assert repl.lower() == person_first.lower()
        elif name == "addresses_multiline":
            multiline = False
            for entry in plan:
                if entry.label is EntityLabel.ADDRESS_BLOCK:
                    orig = normalized[entry.start : entry.end]
                    if "\n" in orig and "\n" in entry.replacement:
                        multiline = True
                        break
            assert multiline
        elif name == "banks_ids":
            required = {"cc", "routing_aba", "swift_bic", "iban"}
            found: set[str] = set()
            for entry in plan:
                if entry.label is EntityLabel.ACCOUNT_ID:
                    subtype = cast(str, entry.meta.get("subtype"))
                    orig = normalized[entry.start : entry.end]
                    repl = entry.replacement
                    if subtype in required:
                        found.add(subtype)
                        assert repl != orig
                        if subtype == "cc":
                            assert re.fullmatch(r"(\d{4} \d{4} \d{4} \d{4})", repl)
                        elif subtype == "routing_aba":
                            assert re.fullmatch(r"\d{9}", repl)
                        elif subtype == "swift_bic":
                            assert re.fullmatch(r"[A-Z]{8}", repl)
                        elif subtype == "iban":
                            assert re.fullmatch(
                                r"[A-Z]{2}\d{2} [A-Z]{4} \d{4} \d{4} \d{4} \d{2}", repl
                            )
            assert required <= found
        elif name == "emails_phones":
            for entry in plan:
                orig = normalized[entry.start : entry.end]
                repl = entry.replacement
                if entry.label is EntityLabel.EMAIL:
                    assert repl.endswith("@example.org")
                elif entry.label is EntityLabel.PHONE:
                    digits_orig = re.sub(r"\D", "", orig)
                    digits_repl = re.sub(r"\D", "", repl)
                    seps_orig = re.sub(r"\d", "", orig)
                    seps_repl = re.sub(r"\d", "", repl)
                    assert len(digits_orig) == len(digits_repl)
                    assert seps_orig == seps_repl
