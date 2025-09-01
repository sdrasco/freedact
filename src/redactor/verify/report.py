"""Audit report and HTML diff generation for redaction runs.

This module assembles detailed audit information for each redaction run and can
render a side‑by‑side HTML diff highlighting replacements.  The produced
``audit.json`` file intentionally contains the *original* text segments alongside
their replacements, so it must only be stored locally and handled with care.  A
compact ``diff.html`` offers a human friendly overview where replaced segments
are emphasised in both the original and redacted views.  ``doc_hash_b32``
records a deterministic hash of the input document for correlation purposes; it
is derived purely from the input text and does not reveal any secret material.
If verification results are available they can optionally be summarized in the
audit bundle.
"""

from __future__ import annotations

import base64
import html
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

# No external dependencies; typing helpers are minimal.
from redactor.config import ConfigModel
from redactor.detect.base import EntityLabel
from redactor.pseudo.seed import doc_hash, ensure_secret_present
from redactor.replace.plan_builder import PlanEntry

from .scanner import VerificationReport

__all__ = [
    "AuditEntry",
    "AuditSummary",
    "AuditBundle",
    "build_audit_entries",
    "summarize_audit",
    "generate_diff_html",
    "write_report_bundle",
]


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AuditEntry:
    """Description of a single applied replacement."""

    id: str
    start: int
    end: int
    label: EntityLabel
    source: str
    entity_id: str | None
    subtype: str | None
    original_text: str
    replacement_text: str
    confidence: float | None
    cluster_id: str | None
    policy_flags: dict[str, bool]
    length_delta: int


@dataclass(frozen=True, slots=True)
class AuditSummary:
    """Summary statistics for a redaction run."""

    total_replacements: int
    counts_by_label: dict[str, int]
    deltas_total: int
    generated_at: str
    doc_hash_b32: str
    seed_present: bool


@dataclass(frozen=True, slots=True)
class AuditBundle:
    """Top level structure persisted to ``audit.json``."""

    entries: list[AuditEntry]
    summary: AuditSummary
    verification: dict[str, object] | None = None


# ---------------------------------------------------------------------------
# Assembly helpers
# ---------------------------------------------------------------------------


def build_audit_entries(
    text_before: str,
    text_after: str,
    plan: list[PlanEntry],
) -> list[AuditEntry]:
    """Return audit entries for ``plan``.

    Parameters
    ----------
    text_before:
        The original document text.
    text_after:
        The redacted document text.  Currently unused but reserved for future
        cross‑checks.
    plan:
        Replacement plan applied to ``text_before``.
    """

    _ = text_after  # reserved for future validation

    entries: list[AuditEntry] = []
    for idx, p in enumerate(plan, start=1):
        original_text = text_before[p.start : p.end]
        replacement_text = p.replacement
        meta = p.meta

        source = str(meta.get("source", ""))
        subtype_val = meta.get("subtype")
        subtype = subtype_val if isinstance(subtype_val, str) else None

        confidence_val = meta.get("confidence")
        confidence = float(confidence_val) if isinstance(confidence_val, (int, float)) else None

        cluster_val = meta.get("cluster_id")
        cluster_id = cluster_val if isinstance(cluster_val, str) else None

        policy_flags: dict[str, bool] = {k: bool(v) for k, v in meta.items() if isinstance(v, bool)}

        length_delta = len(replacement_text) - len(original_text)

        entries.append(
            AuditEntry(
                id=f"r{idx:04d}",
                start=p.start,
                end=p.end,
                label=p.label,
                source=source,
                entity_id=p.entity_id,
                subtype=subtype,
                original_text=original_text,
                replacement_text=replacement_text,
                confidence=confidence,
                cluster_id=cluster_id,
                policy_flags=policy_flags,
                length_delta=length_delta,
            )
        )
    return entries


def summarize_audit(
    text_before: str,
    entries: list[AuditEntry],
    *,
    cfg: ConfigModel,
    verification_report: VerificationReport | None = None,
) -> tuple[AuditSummary, dict[str, object] | None]:
    """Return summary information for ``entries``.

    Parameters
    ----------
    text_before:
        Document text prior to redaction.
    entries:
        Audit entries previously built.
    cfg:
        Configuration model, used only to check whether a seed secret is
        present.
    verification_report:
        Optional :class:`VerificationReport` to embed in the result.
    """

    total_replacements = len(entries)
    counts_by_label: dict[str, int] = {}
    deltas_total = 0
    for e in entries:
        counts_by_label[e.label.name] = counts_by_label.get(e.label.name, 0) + 1
        deltas_total += e.length_delta

    generated_at = datetime.utcnow().isoformat()
    digest = doc_hash(text_before)
    doc_hash_b32 = base64.b32encode(digest).decode("ascii").lower().rstrip("=")
    seed_present = ensure_secret_present(cfg, strict=False)

    verification_dict: dict[str, object] | None = None
    if verification_report is not None:
        verification_dict = {
            "residual_count": verification_report.residual_count,
            "score": verification_report.score,
            "counts_by_label": verification_report.counts_by_label,
            "ignored_by_label": verification_report.ignored_by_label,
        }

    summary = AuditSummary(
        total_replacements=total_replacements,
        counts_by_label=counts_by_label,
        deltas_total=deltas_total,
        generated_at=generated_at,
        doc_hash_b32=doc_hash_b32,
        seed_present=seed_present,
    )
    return summary, verification_dict


# ---------------------------------------------------------------------------
# HTML diff generator
# ---------------------------------------------------------------------------


def _highlight_before(text: str, entries: list[AuditEntry]) -> str:
    pieces: list[str] = []
    last = 0
    for e in entries:
        pieces.append(html.escape(text[last : e.start]))
        original = html.escape(text[e.start : e.end])
        pieces.append(f'<span id="{e.id}" class="repl">{original}</span>')
        last = e.end
    pieces.append(html.escape(text[last:]))
    return "".join(pieces)


def _highlight_after(text: str, entries: list[AuditEntry]) -> str:
    pieces: list[str] = []
    last = 0
    offset = 0
    for e in entries:
        start = e.start + offset
        end = start + len(e.replacement_text)
        pieces.append(html.escape(text[last:start]))
        repl = html.escape(text[start:end])
        pieces.append(f'<span id="{e.id}-after" class="repl">{repl}</span>')
        last = end
        offset += e.length_delta
    pieces.append(html.escape(text[last:]))
    return "".join(pieces)


def generate_diff_html(
    before: str,
    after: str,
    entries: list[AuditEntry],
) -> str:
    """Return a static HTML diff showing original and redacted text."""

    before_html = _highlight_before(before, entries)
    after_html = _highlight_after(after, entries)

    rows = []
    for e in entries:
        rows.append(
            "<tr>"
            f'<td><a href="#{e.id}">{e.id}</a></td>'
            f"<td>{html.escape(e.label.name)}</td>"
            f"<td>{html.escape(e.original_text)}</td>"
            f"<td>{html.escape(e.replacement_text)}</td>"
            f"<td>{e.start}..{e.end}</td>"
            "</tr>"
        )

    rows_html = "".join(rows)

    html_output = (
        "<!DOCTYPE html>\n"
        "<html><head><meta charset='utf-8'><title>Redaction diff</title>"
        "<style>"
        "body{font-family:sans-serif;}"
        "table{border-collapse:collapse;margin-bottom:1em;}"
        "th,td{border:1px solid #ccc;padding:4px;}"
        "div.container{display:flex;gap:2%;}"
        "div.before,div.after{width:50%;white-space:pre-wrap;font-family:monospace;}"
        "span.repl{background:#fffd38;}"
        "</style></head><body>"
        "<p><em>Indices refer to the pre-redaction text.</em></p>"
        "<table class='index'><thead><tr><th>ID</th><th>Label</th><th>Original"
        "</th><th>Replacement</th><th>Start..End</th></tr></thead>"
        f"<tbody>{rows_html}</tbody></table>"
        "<div class='container'>"
        f"<div class='before'>{before_html}</div>"
        f"<div class='after'>{after_html}</div>"
        "</div></body></html>"
    )
    return html_output


# ---------------------------------------------------------------------------
# Report bundle writer
# ---------------------------------------------------------------------------


def write_report_bundle(
    report_dir: str | Path,
    *,
    text_before: str,
    text_after: str,
    plan: list[PlanEntry],
    cfg: ConfigModel,
    verification_report: VerificationReport | None = None,
) -> dict[str, str]:
    """Write audit artifacts to ``report_dir`` and return written paths.

    ``audit.json`` includes original text segments and must remain local.
    Secrets from ``cfg`` are never written to any of the output files.
    """

    entries = build_audit_entries(text_before, text_after, plan)
    summary, verification_dict = summarize_audit(
        text_before, entries, cfg=cfg, verification_report=verification_report
    )

    bundle = AuditBundle(entries=entries, summary=summary, verification=verification_dict)

    report_path = Path(report_dir)
    report_path.mkdir(parents=True, exist_ok=True)

    written: dict[str, str] = {}

    audit_path = report_path / "audit.json"
    audit_data = {
        "entries": [
            {
                **asdict(e),
                "label": e.label.name,
            }
            for e in bundle.entries
        ],
        "summary": asdict(bundle.summary),
    }
    if bundle.verification is not None:
        audit_data["verification"] = bundle.verification
    with audit_path.open("w", encoding="utf-8") as f:
        json.dump(audit_data, f, ensure_ascii=False, indent=2)
    written["audit.json"] = str(audit_path)

    diff_html = generate_diff_html(text_before, text_after, entries)
    diff_path = report_path / "diff.html"
    diff_path.write_text(diff_html, encoding="utf-8")
    written["diff.html"] = str(diff_path)

    plan_min: list[dict[str, object | None]] = []
    for p in plan:
        subtype_val = p.meta.get("subtype")
        subtype = subtype_val if isinstance(subtype_val, str) else None
        plan_min.append(
            {
                "start": p.start,
                "end": p.end,
                "label": p.label.name,
                "replacement": p.replacement,
                "subtype": subtype,
                "entity_id": p.entity_id,
            }
        )
    plan_path = report_path / "plan.json"
    with plan_path.open("w", encoding="utf-8") as f:
        json.dump(plan_min, f, ensure_ascii=False, indent=2)
    written["plan.json"] = str(plan_path)

    if verification_report is not None:
        verification_path = report_path / "verification.json"
        ver_dict = asdict(verification_report)
        for key in ("findings", "ignored"):
            items = ver_dict.get(key)
            if isinstance(items, list):
                for item in items:
                    label = item.get("label")
                    if isinstance(label, EntityLabel):
                        item["label"] = label.name
        with verification_path.open("w", encoding="utf-8") as f:
            json.dump(ver_dict, f, ensure_ascii=False, indent=2)
        written["verification.json"] = str(verification_path)

    return written
