from __future__ import annotations

import pytest

from redactor.config import ConfigModel, load_config
from redactor.detect.base import EntityLabel
from redactor.replace.plan_builder import PlanEntry
from redactor.verify.scanner import scan_text


def _base_cfg() -> ConfigModel:
    cfg = load_config()
    cfg.detectors.ner.enabled = False
    return cfg


def test_baseline_detection() -> None:
    cfg = _base_cfg()
    text = "Email john@acme.com, Phone +12125550000, SSN 123-45-6789."
    report = scan_text(text, cfg)
    assert report.counts_by_label["EMAIL"] == 1
    assert report.counts_by_label["PHONE"] == 1
    assert report.counts_by_label["ACCOUNT_ID"] == 1
    assert report.residual_count == 3


def test_replacement_matches_ignored() -> None:
    cfg = _base_cfg()
    text = "foo@bar.com\n+12025550100\n123 Main St"
    plan = [
        PlanEntry(0, 0, "foo@bar.com", EntityLabel.EMAIL, None, None, {}),
        PlanEntry(0, 0, "+12025550100", EntityLabel.PHONE, None, None, {}),
        PlanEntry(0, 0, "123 Main St", EntityLabel.ADDRESS_BLOCK, None, None, {}),
    ]
    report = scan_text(text, cfg, applied_plan=plan)
    assert report.residual_count == 0
    assert {f.ignored_reason for f in report.ignored} == {"replacement_match"}
    assert report.ignored_by_label == {"EMAIL": 1, "PHONE": 1, "ADDRESS_BLOCK": 1}


def test_policy_keep_roles() -> None:
    cfg = _base_cfg()
    cfg.redact.alias_labels = "keep_roles"
    text = 'Acme LLC (hereinafter "Buyer"). Buyer shall pay.'
    report = scan_text(text, cfg)
    assert report.ignored_by_label["ALIAS_LABEL"] >= 1
    assert all(f.ignored_reason == "policy_keep_roles" for f in report.ignored)


def test_policy_generic_dates() -> None:
    cfg = _base_cfg()
    text = "Executed on July 4, 1982."
    report = scan_text(text, cfg)
    assert report.ignored_by_label["DATE_GENERIC"] == 1
    cfg.redact.generic_dates = True
    report2 = scan_text(text, cfg)
    assert report2.counts_by_label["DATE_GENERIC"] == 1


def test_weights_and_scoring() -> None:
    cfg = load_config()  # keep NER enabled for PERSON detection
    text = "John Doe john@acme.com 4111-1111-1111-1111 +12125551234"
    report = scan_text(text, cfg)
    assert report.counts_by_label == {
        "PERSON": 1,
        "EMAIL": 1,
        "ACCOUNT_ID": 1,
        "PHONE": 1,
    }
    assert report.score == 3 + 3 + 3 + 2


def test_confidence_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _base_cfg()

    from redactor.detect.base import EntitySpan
    from redactor.detect.email import EmailDetector

    def fake_detect(
        self: EmailDetector, text: str, context: object | None = None
    ) -> list[EntitySpan]:
        return [EntitySpan(0, len(text), text, EntityLabel.EMAIL, "fake", 0.1, {})]

    monkeypatch.setattr(EmailDetector, "detect", fake_detect)
    report = scan_text("john@acme.com", cfg)
    assert report.total_found == 0


def test_sorting_and_details() -> None:
    cfg = _base_cfg()
    text = "123-45-6789 and john@acme.com"
    report = scan_text(text, cfg)
    starts = [f.start for f in report.findings]
    assert starts == sorted(starts)
    assert "weights" in report.details and "min_confidence" in report.details
