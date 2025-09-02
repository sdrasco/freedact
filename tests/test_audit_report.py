"""Tests for audit report and diff generation."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from redactor.config import load_config
from redactor.detect.base import EntityLabel
from redactor.replace.applier import apply_plan
from redactor.replace.plan_builder import PlanEntry
from redactor.verify.report import (
    build_audit_entries,
    generate_diff_html,
    summarize_audit,
    write_report_bundle,
)


def _build_plan() -> tuple[str, str, list[PlanEntry]]:
    before = 'John Doe, hereinafter "Morgan". Email: john@acme.com\n'
    plan = [
        PlanEntry(
            start=0,
            end=8,
            replacement="Alex Carter",
            label=EntityLabel.PERSON,
            entity_id="p1",
            span_id=None,
            meta={"source": "manual"},
        ),
        PlanEntry(
            start=23,
            end=29,
            replacement="Alex",
            label=EntityLabel.ALIAS_LABEL,
            entity_id=None,
            span_id=None,
            meta={"source": "manual"},
        ),
        PlanEntry(
            start=39,
            end=52,
            replacement="uabc123@example.org",
            label=EntityLabel.EMAIL,
            entity_id=None,
            span_id=None,
            meta={"source": "manual"},
        ),
    ]
    after, _ = apply_plan(before, plan)
    return before, after, plan


def test_audit_workflow(tmp_path: Path) -> None:
    before, after, plan = _build_plan()

    entries = build_audit_entries(before, after, plan)
    assert len(entries) == 3
    assert [e.id for e in entries] == ["r0001", "r0002", "r0003"]
    assert entries[0].original_text == before[0:8]
    assert entries[1].original_text == before[23:29]
    assert entries[2].original_text == before[39:52]
    assert entries[0].label is EntityLabel.PERSON
    assert entries[1].label is EntityLabel.ALIAS_LABEL
    assert entries[2].label is EntityLabel.EMAIL

    cfg = load_config(env={"REDACTOR_SEED_SECRET": "s3cret"})
    summary, verification_dict = summarize_audit(
        before, entries, cfg=cfg, plan=plan, verification_report=None
    )
    assert summary.total_replacements == 3
    assert summary.counts_by_label == {"PERSON": 1, "ALIAS_LABEL": 1, "EMAIL": 1}
    assert summary.deltas_total == sum(e.length_delta for e in entries)
    assert summary.doc_hash_b32
    assert summary.seed_present is True
    assert verification_dict is None

    cfg_no = load_config(env={})
    summary_no, _ = summarize_audit(
        before, entries, cfg=cfg_no, plan=plan, verification_report=None
    )
    assert summary_no.seed_present is False
    summary_json = json.dumps(asdict(summary))
    assert "s3cret" not in summary_json

    html = generate_diff_html(before, after, entries)
    assert '<span id="r0001"' in html
    assert "Alex Carter" in html
    assert "&quot;" in html
    assert html == generate_diff_html(before, after, entries)

    paths = write_report_bundle(
        tmp_path,
        text_before=before,
        text_after=after,
        plan=plan,
        cfg=cfg,
        verification_report=None,
    )

    assert (tmp_path / "audit.json").exists()
    assert (tmp_path / "diff.html").exists()
    assert (tmp_path / "plan.json").exists()

    with open(paths["audit.json"], "r", encoding="utf-8") as f:
        audit_data = json.load(f)
    assert audit_data["summary"]["deltas_total"] == sum(
        e["length_delta"] for e in audit_data["entries"]
    )
    assert "s3cret" not in json.dumps(audit_data)


def test_seed_presence_signal() -> None:
    before = "John Doe\n"
    plan = [
        PlanEntry(
            start=0,
            end=8,
            replacement="Jane Roe",
            label=EntityLabel.PERSON,
            entity_id=None,
            span_id=None,
            meta={"source": "manual"},
        )
    ]
    after, _ = apply_plan(before, plan)
    entries = build_audit_entries(before, after, plan)

    cfg = load_config(env={"REDACTOR_SEED_SECRET": "unit-test-secret"})
    summary, _ = summarize_audit(before, entries, cfg=cfg, plan=plan, verification_report=None)
    assert summary.seed_present is True
    summary_json = json.dumps(asdict(summary))
    assert "unit-test-secret" not in summary_json

    cfg_no = load_config(env={})
    summary_no, _ = summarize_audit(
        before, entries, cfg=cfg_no, plan=plan, verification_report=None
    )
    assert summary_no.seed_present is False


def test_secret_leakage_prevention(tmp_path: Path) -> None:
    before = "John Doe\n"
    plan = [
        PlanEntry(
            start=0,
            end=8,
            replacement="Jane Roe",
            label=EntityLabel.PERSON,
            entity_id=None,
            span_id=None,
            meta={"source": "unit-test-secret"},
        )
    ]
    after, _ = apply_plan(before, plan)
    cfg = load_config(env={"REDACTOR_SEED_SECRET": "unit-test-secret"})

    with pytest.raises(ValueError, match="Refusing to write audit artifacts"):
        write_report_bundle(
            tmp_path,
            text_before=before,
            text_after=after,
            plan=plan,
            cfg=cfg,
            verification_report=None,
        )

    plan[0].meta["source"] = "manual"
    paths = write_report_bundle(
        tmp_path,
        text_before=before,
        text_after=after,
        plan=plan,
        cfg=cfg,
        verification_report=None,
    )
    audit_text = Path(paths["audit.json"]).read_text(encoding="utf-8")
    plan_text = Path(paths["plan.json"]).read_text(encoding="utf-8")
    assert "unit-test-secret" not in audit_text
    assert "unit-test-secret" not in plan_text
