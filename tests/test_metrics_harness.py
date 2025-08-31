import os
from typing import cast

import pytest

from evaluation.metrics import (
    SpanRef,
    compute_prf,
    evaluate_fixture,
    evaluate_text_vs_gold,
    greedy_match,
    run_detectors_for_metrics,
    span_iou,
    spans_to_spanrefs,
)
from redactor.config import ConfigModel, load_config


@pytest.fixture(scope="module")
def cfg() -> ConfigModel:
    os.environ["REDACTOR_SEED_SECRET"] = "metrics-secret"
    cfg = load_config()
    cfg.detectors.ner.enabled = False
    return cfg


def test_iou_and_greedy_match() -> None:
    gold = [
        SpanRef(0, 10, "EMAIL"),
        SpanRef(20, 30, "PHONE"),
    ]
    pred = [
        SpanRef(0, 12, "EMAIL"),
        SpanRef(18, 28, "PHONE"),
    ]
    iou0 = span_iou((0, 10), (0, 12))
    iou1 = span_iou((20, 30), (18, 28))
    assert pytest.approx(iou0, rel=1e-6) == 10 / 12
    assert pytest.approx(iou1, rel=1e-6) == 8 / 12

    matches = greedy_match(gold, pred, 0.1, "coarse")
    assert {(m.gold_idx, m.pred_idx) for m in matches} == {(0, 0), (1, 1)}


def test_simple_doc_evaluation(cfg: ConfigModel) -> None:
    text = "Email a@b.com. Phone 415-555-2671."
    email_start = text.index("a@b.com")
    phone_start = text.index("415-555-2671")
    gold = [
        SpanRef(email_start, email_start + 7, "EMAIL"),
        SpanRef(phone_start, phone_start + 12, "PHONE"),
    ]
    metrics = evaluate_text_vs_gold(text, gold, cfg, use_ner=False)
    email_prf = metrics.per_label["EMAIL"]
    phone_prf = metrics.per_label["PHONE"]
    assert email_prf.precision == pytest.approx(1.0)
    assert email_prf.recall == pytest.approx(1.0)
    assert phone_prf.precision == pytest.approx(1.0)
    assert phone_prf.recall == pytest.approx(1.0)


def test_fine_vs_coarse_labels(cfg: ConfigModel) -> None:
    text = "Card 4111 1111 1111 1111"
    spans = run_detectors_for_metrics(text, cfg, use_ner=False)
    coarse_refs = spans_to_spanrefs(spans, granularity="coarse")
    fine_refs = spans_to_spanrefs(spans, granularity="fine")
    coarse_labels = {r.label for r in coarse_refs}
    fine_labels = {r.label for r in fine_refs}
    assert "ACCOUNT_ID" in coarse_labels
    assert any(lbl.startswith("ACCOUNT_ID:cc") for lbl in fine_labels)


def test_fixture_smoke(cfg: ConfigModel) -> None:
    for name in ("emails_phones", "banks_ids"):
        metrics, e2e = evaluate_fixture(name, cfg, use_ner=False)
        assert metrics.per_label
        assert e2e["residual_count"] == 0
        assert cast(int, e2e["plan_size"]) >= 0
        assert isinstance(e2e["changed"], bool)


def test_confusion_matrix() -> None:
    gold = [SpanRef(0, 10, "DOB")]
    pred = [SpanRef(0, 10, "DATE_GENERIC")]
    matches = greedy_match(gold, pred, 0.5, "coarse")
    metrics = compute_prf(
        gold,
        pred,
        matches,
        labels={"DOB", "DATE_GENERIC"},
        iou_threshold=0.5,
    )
    assert metrics.confusion[("DOB", "DATE_GENERIC")] == 1
    dob = metrics.per_label["DOB"]
    date = metrics.per_label["DATE_GENERIC"]
    assert dob.fn == 1 and dob.tp == 0
    assert date.fp == 1 and date.tp == 0
