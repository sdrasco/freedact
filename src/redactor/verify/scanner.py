"""Residual sensitive data scanner.

This module reuses the existing detectors to analyse already redacted text for
any leftover personal data.  Unlike the main redaction pipeline the scanner
does not attempt to merge overlapping spans or modify text – it merely reports
what it finds and applies a set of policy and synthetic‑safe ignore rules.  The
resulting :class:`VerificationReport` gives downstream tools a concise summary
of residual PII and a leakage score.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from redactor.config import ConfigModel
from redactor.detect.account_ids import AccountIdDetector
from redactor.detect.address_libpostal import AddressLineDetector
from redactor.detect.aliases import AliasDetector
from redactor.detect.bank_org import BankOrgDetector
from redactor.detect.base import DetectionContext, Detector, EntityLabel, EntitySpan
from redactor.detect.date_dob import DOBDetector
from redactor.detect.date_generic import DateGenericDetector
from redactor.detect.email import EmailDetector
from redactor.detect.ner_spacy import SpacyNERDetector
from redactor.detect.phone import PhoneDetector
from redactor.replace.plan_builder import PlanEntry

from .heuristics import (
    build_replacement_multiset_by_label,
    is_safe_email_domain,
    is_safe_phone_string,
    weight_map,
)

__all__ = [
    "VerificationFinding",
    "VerificationReport",
    "scan_text",
]


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class VerificationFinding:
    """Information about a detected entity during verification."""

    start: int
    end: int
    text: str
    label: EntityLabel
    confidence: float
    attrs: dict[str, object]
    ignored_reason: str | None = None


@dataclass(frozen=True, slots=True)
class VerificationReport:
    """Structured result of a verification scan."""

    total_found: int
    total_ignored: int
    residual_count: int
    score: float
    counts_by_label: dict[str, int]
    ignored_by_label: dict[str, int]
    findings: list[VerificationFinding]
    ignored: list[VerificationFinding]
    details: dict[str, object] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Detector orchestration
# ---------------------------------------------------------------------------


def _build_detectors(cfg: ConfigModel) -> list[Detector]:
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
    if cfg.detectors.ner.enabled:
        detectors.append(SpacyNERDetector(cfg))
    return detectors


def _entityspan_to_finding(span: EntitySpan) -> VerificationFinding:
    return VerificationFinding(
        span.start,
        span.end,
        span.text,
        span.label,
        span.confidence,
        dict(span.attrs),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def scan_text(
    text: str,
    cfg: ConfigModel,
    *,
    applied_plan: list[PlanEntry] | None = None,
) -> VerificationReport:
    """Scan ``text`` for residual sensitive data and return a report."""

    detectors = _build_detectors(cfg)
    context = DetectionContext(locale=cfg.locale, config=cfg)
    min_conf = cfg.verification.min_confidence

    spans: list[VerificationFinding] = []
    for det in detectors:
        for sp in det.detect(text, context):
            if sp.confidence < min_conf:
                continue
            spans.append(_entityspan_to_finding(sp))

    spans.sort(key=lambda f: f.start)
    total_found = len(spans)

    repl_multiset = build_replacement_multiset_by_label(applied_plan)
    block_lines: set[str] = set()
    if applied_plan:
        for pe in applied_plan:
            if pe.label is EntityLabel.ADDRESS_BLOCK:
                for line in pe.replacement.splitlines():
                    stripped = line.rstrip()
                    if stripped:
                        block_lines.add(stripped)
    residual: list[VerificationFinding] = []
    ignored: list[VerificationFinding] = []

    counts_by_label: dict[str, int] = defaultdict(int)
    ignored_by_label: dict[str, int] = defaultdict(int)

    weights = weight_map(cfg)
    score = 0

    for f in spans:
        reason: str | None = None
        label = f.label

        counter = repl_multiset.get(label)
        if counter and counter[f.text] > 0:
            counter[f.text] -= 1
            reason = "replacement_match"
        elif label is EntityLabel.ADDRESS_BLOCK and f.text.rstrip() in block_lines:
            reason = "replacement_match_block_line"
        elif label in {EntityLabel.GPE, EntityLabel.LOC}:
            line_start = text.rfind("\n", 0, f.start) + 1
            line_end = text.find("\n", f.end)
            if line_end == -1:
                line_end = len(text)
            line_text = text[line_start:line_end].rstrip()
            if line_text in block_lines:
                reason = "in_address_block_replacement"
        elif label is EntityLabel.EMAIL:
            domain = f.attrs.get("domain")
            if isinstance(domain, str) and is_safe_email_domain(domain):
                reason = "safe_domain"
        elif label is EntityLabel.PHONE:
            if is_safe_phone_string(f.text):
                reason = "safe_number"
        elif label is EntityLabel.ACCOUNT_ID:
            subtype = str(f.attrs.get("subtype", ""))
            if f.text.startswith("ACCT_"):
                reason = "token_account"
            elif subtype == "iban":
                # rely on replacement_match; nothing special here
                reason = None
        elif label is EntityLabel.ALIAS_LABEL and cfg.redact.alias_labels == "keep_roles":
            reason = "policy_keep_roles"
        elif label is EntityLabel.DATE_GENERIC and not cfg.redact.generic_dates:
            reason = "policy_preserve_date"

        if reason is None:
            residual.append(f)
            counts_by_label[label.name] += 1
            score += weights.get(label, 0)
        else:
            ignored.append(
                VerificationFinding(
                    f.start,
                    f.end,
                    f.text,
                    f.label,
                    f.confidence,
                    f.attrs,
                    reason,
                )
            )
            ignored_by_label[label.name] += 1

    details = {
        "weights": {lbl.name: w for lbl, w in weights.items()},
        "min_confidence": min_conf,
        "generated_at": datetime.utcnow().isoformat(),
    }

    return VerificationReport(
        total_found=total_found,
        total_ignored=len(ignored),
        residual_count=len(residual),
        score=score,
        counts_by_label=dict(counts_by_label),
        ignored_by_label=dict(ignored_by_label),
        findings=residual,
        ignored=ignored,
        details=details,
    )
