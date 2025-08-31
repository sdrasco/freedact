"""Evaluation harness for detection precision/recall and end-to-end coverage.

This module provides small, dependency-free helpers to measure detection quality
against curated fixtures.  Matching between gold and predicted spans follows a
half-open interval convention and uses intersection over union (IoU) with a
threshold.  Account identifiers can be evaluated in coarse or fine granularity
modes: ``coarse`` collapses all subtypes to ``ACCOUNT_ID`` while ``fine`` keeps
subtype specific labels such as ``ACCOUNT_ID:cc``.  Micro metrics aggregate
counts across all labels whereas macro metrics average scores per label.

The end-to-end coverage helper runs the full redaction pipeline and verifies
that annotated substrings are removed, complementing the more fine grained
precision/recall metrics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence, cast

from evaluation.fixtures import loader as fixtures_loader
from redactor.config import ConfigModel
from redactor.detect.base import DetectionContext, Detector, EntityLabel, EntitySpan
from redactor.link import alias_resolver, span_merger
from redactor.preprocess import layout_reconstructor
from redactor.preprocess.normalizer import normalize
from redactor.replace.applier import apply_plan
from redactor.replace.plan_builder import build_replacement_plan
from redactor.utils.textspan import build_line_starts
from redactor.verify import scanner

__all__ = [
    "SpanRef",
    "Match",
    "PRF",
    "MetricsBundle",
    "span_iou",
    "normalize_label",
    "greedy_match",
    "compute_prf",
    "run_detectors_for_metrics",
    "spans_to_spanrefs",
    "evaluate_text_vs_gold",
    "evaluate_fixture",
    "evaluate_all_fixtures",
    "end_to_end_coverage",
]


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class SpanRef:
    """Reference span used for metrics computations."""

    start: int
    end: int
    label: str
    subtype: str | None = None


@dataclass(slots=True)
class Match:
    """Greedy matching result between a gold and predicted span."""

    gold_idx: int
    pred_idx: int
    iou: float
    gold_label: str
    pred_label: str
    gold_subtype: str | None
    pred_subtype: str | None


@dataclass(slots=True)
class PRF:
    """Precision/recall/F1 counts and scores."""

    tp: int
    fp: int
    fn: int
    precision: float
    recall: float
    f1: float


@dataclass(slots=True)
class MetricsBundle:
    """Bundle of metrics for a document or collection."""

    per_label: dict[str, PRF]
    micro: PRF
    macro: PRF
    confusion: dict[tuple[str, str], int]
    iou_threshold: float


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def span_iou(a: tuple[int, int], b: tuple[int, int]) -> float:
    """Return IoU for two half-open character spans ``a`` and ``b``."""

    start = max(a[0], b[0])
    end = min(a[1], b[1])
    if end <= start:
        return 0.0
    inter = end - start
    union = (a[1] - a[0]) + (b[1] - b[0]) - inter
    if union <= 0:
        return 0.0
    return inter / union


def normalize_label(label: str, *, granularity: Literal["coarse", "fine"] = "coarse") -> str:
    """Return normalized label according to ``granularity``."""

    if granularity == "coarse" and label.startswith("ACCOUNT_ID"):
        return "ACCOUNT_ID"
    return label


def greedy_match(
    gold: Sequence[SpanRef],
    pred: Sequence[SpanRef],
    iou_threshold: float,
    granularity: Literal["coarse", "fine"],
) -> list[Match]:
    """Greedy bipartite matching by descending IoU."""

    candidates: list[tuple[float, int, int, str, str, str | None, str | None]] = []
    for gi, g in enumerate(gold):
        for pi, p in enumerate(pred):
            iou = span_iou((g.start, g.end), (p.start, p.end))
            if iou < iou_threshold:
                continue
            g_label = normalize_label(
                f"{g.label}:{g.subtype}" if g.subtype else g.label,
                granularity=granularity,
            )
            p_label = normalize_label(
                f"{p.label}:{p.subtype}" if p.subtype else p.label,
                granularity=granularity,
            )
            candidates.append((iou, gi, pi, g_label, p_label, g.subtype, p.subtype))

    candidates.sort(reverse=True)
    used_gold: set[int] = set()
    used_pred: set[int] = set()
    matches: list[Match] = []
    for iou, gi, pi, g_label, p_label, g_sub, p_sub in candidates:
        if gi in used_gold or pi in used_pred:
            continue
        used_gold.add(gi)
        used_pred.add(pi)
        matches.append(Match(gi, pi, iou, g_label, p_label, g_sub, p_sub))
    return matches


def compute_prf(
    gold: Sequence[SpanRef],
    pred: Sequence[SpanRef],
    matches: Sequence[Match],
    labels: set[str],
    *,
    iou_threshold: float,
    granularity: Literal["coarse", "fine"] = "coarse",
) -> MetricsBundle:
    """Compute precision/recall/F1 metrics."""

    counts: dict[str, list[int]] = {lbl: [0, 0, 0] for lbl in labels}
    confusion: dict[tuple[str, str], int] = {}

    matched_gold = {m.gold_idx for m in matches}
    matched_pred = {m.pred_idx for m in matches}

    for m in matches:
        if m.gold_label == m.pred_label:
            c = counts.setdefault(m.gold_label, [0, 0, 0])
            c[0] += 1
        else:
            c_g = counts.setdefault(m.gold_label, [0, 0, 0])
            c_p = counts.setdefault(m.pred_label, [0, 0, 0])
            c_g[2] += 1  # FN
            c_p[1] += 1  # FP
            confusion[(m.gold_label, m.pred_label)] = (
                confusion.get((m.gold_label, m.pred_label), 0) + 1
            )

    for gi, g in enumerate(gold):
        if gi in matched_gold:
            continue
        lbl = normalize_label(
            f"{g.label}:{g.subtype}" if g.subtype else g.label,
            granularity=granularity,
        )
        c = counts.setdefault(lbl, [0, 0, 0])
        c[2] += 1
        confusion[(lbl, "<none>")] = confusion.get((lbl, "<none>"), 0) + 1

    for pi, p in enumerate(pred):
        if pi in matched_pred:
            continue
        lbl = normalize_label(
            f"{p.label}:{p.subtype}" if p.subtype else p.label,
            granularity=granularity,
        )
        c = counts.setdefault(lbl, [0, 0, 0])
        c[1] += 1
        confusion[("<none>", lbl)] = confusion.get(("<none>", lbl), 0) + 1

    per_label: dict[str, PRF] = {}
    tp_total = fp_total = fn_total = 0
    for lbl, (tp, fp, fn) in counts.items():
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        per_label[lbl] = PRF(tp, fp, fn, precision, recall, f1)
        tp_total += tp
        fp_total += fp
        fn_total += fn

    micro_prec = tp_total / (tp_total + fp_total) if (tp_total + fp_total) else 0.0
    micro_rec = tp_total / (tp_total + fn_total) if (tp_total + fn_total) else 0.0
    micro_f1 = (
        2 * micro_prec * micro_rec / (micro_prec + micro_rec) if (micro_prec + micro_rec) else 0.0
    )
    micro = PRF(tp_total, fp_total, fn_total, micro_prec, micro_rec, micro_f1)

    n_lbl = len(per_label)
    macro_prec = sum(p.precision for p in per_label.values()) / n_lbl if n_lbl else 0.0
    macro_rec = sum(p.recall for p in per_label.values()) / n_lbl if n_lbl else 0.0
    macro_f1 = sum(p.f1 for p in per_label.values()) / n_lbl if n_lbl else 0.0
    macro = PRF(tp_total, fp_total, fn_total, macro_prec, macro_rec, macro_f1)

    return MetricsBundle(per_label, micro, macro, confusion, iou_threshold)


# ---------------------------------------------------------------------------
# Detector helpers
# ---------------------------------------------------------------------------


def run_detectors_for_metrics(
    text: str,
    cfg: ConfigModel,
    *,
    use_ner: bool | None = None,
) -> list[EntitySpan]:
    """Instantiate detectors as used by the CLI and return raw spans."""

    from redactor.detect.account_ids import AccountIdDetector
    from redactor.detect.address_libpostal import AddressLineDetector
    from redactor.detect.aliases import AliasDetector
    from redactor.detect.bank_org import BankOrgDetector
    from redactor.detect.date_dob import DOBDetector
    from redactor.detect.date_generic import DateGenericDetector
    from redactor.detect.email import EmailDetector
    from redactor.detect.phone import PhoneDetector

    detectors: list[Detector] = [
        EmailDetector(),
        PhoneDetector(),
        AccountIdDetector(),
        BankOrgDetector(),
        AddressLineDetector(),
        DateGenericDetector(),
        DOBDetector(),
        AliasDetector(),
    ]

    enable_ner = cfg.detectors.ner.enabled if use_ner is None else use_ner
    if enable_ner:
        from redactor.detect.ner_spacy import SpacyNERDetector

        detectors.append(SpacyNERDetector(cfg))

    context = DetectionContext(locale=cfg.locale, line_starts=build_line_starts(text), config=cfg)
    spans: list[EntitySpan] = []
    for det in detectors:
        spans.extend(det.detect(text, context))
    return spans


def spans_to_spanrefs(
    spans: Sequence[EntitySpan],
    *,
    granularity: Literal["coarse", "fine"],
) -> list[SpanRef]:
    """Convert detector spans to :class:`SpanRef` objects."""

    refs: list[SpanRef] = []
    for sp in spans:
        label = sp.label.name
        subtype = cast(str | None, sp.attrs.get("subtype"))
        if sp.label is EntityLabel.ACCOUNT_ID:
            norm_label = normalize_label(
                f"ACCOUNT_ID:{subtype}" if subtype else "ACCOUNT_ID",
                granularity=granularity,
            )
            sub = subtype if granularity == "fine" else subtype
            if granularity == "coarse":
                sub = None
            refs.append(SpanRef(sp.start, sp.end, norm_label, sub))
            continue
        if sp.label is EntityLabel.ADDRESS_BLOCK and sp.source != "address_line":
            continue
        norm_label = normalize_label(label, granularity=granularity)
        refs.append(SpanRef(sp.start, sp.end, norm_label, None))
    return refs


# ---------------------------------------------------------------------------
# Public evaluation entry points
# ---------------------------------------------------------------------------


def evaluate_text_vs_gold(
    text: str,
    gold: Sequence[SpanRef],
    cfg: ConfigModel,
    *,
    iou_threshold: float = 0.5,
    granularity: Literal["coarse", "fine"] = "coarse",
    use_ner: bool | None = None,
) -> MetricsBundle:
    """Run detectors on ``text`` and compare against ``gold`` spans."""

    spans = run_detectors_for_metrics(text, cfg, use_ner=use_ner)
    pred_refs = spans_to_spanrefs(spans, granularity=granularity)

    matches = greedy_match(gold, pred_refs, iou_threshold, granularity)

    label_set: set[str] = set()
    for sp in list(gold) + pred_refs:
        label_set.add(
            normalize_label(
                f"{sp.label}:{sp.subtype}" if sp.subtype else sp.label,
                granularity=granularity,
            )
        )

    metrics = compute_prf(
        list(gold),
        pred_refs,
        matches,
        label_set,
        iou_threshold=iou_threshold,
        granularity=granularity,
    )
    return metrics


def end_to_end_coverage(text: str, cfg: ConfigModel) -> dict[str, object]:
    """Run the full pipeline and return coverage information."""

    norm = normalize(text)
    normalized = norm.text
    spans = run_detectors_for_metrics(normalized, cfg)
    spans = layout_reconstructor.merge_address_lines_into_blocks(normalized, spans)
    spans, clusters = alias_resolver.resolve_aliases(normalized, spans, cfg)
    merged = span_merger.merge_spans(spans, cfg)
    plan = build_replacement_plan(normalized, merged, cfg, clusters=clusters)
    redacted, applied = apply_plan(normalized, plan)
    before = scanner.scan_text(normalized, cfg)
    report = scanner.scan_text(redacted, cfg, applied_plan=applied)
    residual_count = sum(
        1
        for f in report.findings
        if f.label is not EntityLabel.ADDRESS_BLOCK
        and not (f.label is EntityLabel.ACCOUNT_ID and not any(ch.isdigit() for ch in f.text))
    )

    coverage_count = max(0, before.residual_count - report.residual_count)
    return {
        "coverage_count": coverage_count,
        "changed": redacted != normalized,
        "plan_size": len(plan),
        "residual_count": residual_count,
        "score": report.score,
    }


def evaluate_fixture(
    name: str,
    cfg: ConfigModel,
    *,
    iou_threshold: float = 0.5,
    granularity: Literal["coarse", "fine"] = "coarse",
    use_ner: bool | None = None,
) -> tuple[MetricsBundle, dict[str, object]]:
    """Evaluate a fixture by name returning metrics and minimal coverage data."""

    text, ann = fixtures_loader.load_fixture(name)
    spans_data = cast(list[dict[str, object]], ann.get("spans", []))
    gold: list[SpanRef] = []
    for sp in spans_data:
        start = cast(int, sp["start"])
        end = cast(int, sp["end"])
        label = cast(str, sp["label"])
        subtype = cast(str | None, sp.get("subtype"))
        gold.append(SpanRef(start, end, label, subtype))

    metrics = evaluate_text_vs_gold(
        text,
        gold,
        cfg,
        iou_threshold=iou_threshold,
        granularity=granularity,
        use_ner=use_ner,
    )

    coverage = end_to_end_coverage(text, cfg)
    e2e = {
        "residual_count": coverage["residual_count"],
        "plan_size": coverage["plan_size"],
        "changed": coverage["changed"],
    }
    return metrics, e2e


def evaluate_all_fixtures(
    cfg: ConfigModel,
    *,
    iou_threshold: float = 0.5,
    granularity: Literal["coarse", "fine"] = "coarse",
    use_ner: bool | None = None,
) -> dict[str, object]:
    """Evaluate all fixtures returning per-fixture and aggregate metrics."""

    results: dict[str, object] = {}
    aggregate_counts: dict[str, list[int]] = {}
    aggregate_confusion: dict[tuple[str, str], int] = {}
    per_fixture: dict[str, object] = {}

    for name in fixtures_loader.list_fixtures():
        metrics, e2e = evaluate_fixture(
            name,
            cfg,
            iou_threshold=iou_threshold,
            granularity=granularity,
            use_ner=use_ner,
        )
        per_fixture[name] = {"metrics": metrics, "e2e": e2e}
        for lbl, pr in metrics.per_label.items():
            counts = aggregate_counts.setdefault(lbl, [0, 0, 0])
            counts[0] += pr.tp
            counts[1] += pr.fp
            counts[2] += pr.fn
        for key, val in metrics.confusion.items():
            aggregate_confusion[key] = aggregate_confusion.get(key, 0) + val

    per_label: dict[str, PRF] = {}
    tp_total = fp_total = fn_total = 0
    for lbl, (tp, fp, fn) in aggregate_counts.items():
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        per_label[lbl] = PRF(tp, fp, fn, precision, recall, f1)
        tp_total += tp
        fp_total += fp
        fn_total += fn

    micro_prec = tp_total / (tp_total + fp_total) if (tp_total + fp_total) else 0.0
    micro_rec = tp_total / (tp_total + fn_total) if (tp_total + fn_total) else 0.0
    micro_f1 = (
        2 * micro_prec * micro_rec / (micro_prec + micro_rec) if (micro_prec + micro_rec) else 0.0
    )
    micro = PRF(tp_total, fp_total, fn_total, micro_prec, micro_rec, micro_f1)

    n_lbl = len(per_label)
    macro_prec = sum(p.precision for p in per_label.values()) / n_lbl if n_lbl else 0.0
    macro_rec = sum(p.recall for p in per_label.values()) / n_lbl if n_lbl else 0.0
    macro_f1 = sum(p.f1 for p in per_label.values()) / n_lbl if n_lbl else 0.0
    macro = PRF(tp_total, fp_total, fn_total, macro_prec, macro_rec, macro_f1)

    aggregate_bundle = MetricsBundle(per_label, micro, macro, aggregate_confusion, iou_threshold)
    results["fixtures"] = per_fixture
    results["aggregate"] = aggregate_bundle
    return results
