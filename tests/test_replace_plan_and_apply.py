from __future__ import annotations

import re

from redactor.config import load_config
from redactor.detect.base import EntityLabel, EntitySpan
from redactor.pseudo import case_preserver
from redactor.replace import applier, plan_builder


def _span(
    start: int,
    end: int,
    text: str,
    label: EntityLabel,
    *,
    attrs: dict[str, object] | None = None,
    entity_id: str | None = None,
) -> EntitySpan:
    return EntitySpan(start, end, text, label, "test", 0.9, attrs or {}, entity_id=entity_id)


def test_person_and_alias_nickname_consistency() -> None:
    cfg = load_config()
    text = 'John Doe, hereinafter "Morgan". Later, Morgan executed the deed.'
    spans = [
        _span(0, 8, "John Doe", EntityLabel.PERSON, entity_id="p1"),
        _span(
            23,
            29,
            "Morgan",
            EntityLabel.ALIAS_LABEL,
            attrs={"alias_kind": "nickname", "cluster_id": "p1"},
            entity_id="p1",
        ),
        _span(
            39,
            45,
            "Morgan",
            EntityLabel.ALIAS_LABEL,
            attrs={"alias_kind": "nickname", "cluster_id": "p1"},
            entity_id="p1",
        ),
    ]
    plan = plan_builder.build_replacement_plan(text, spans, cfg)
    new_text, _ = applier.apply_plan(text, plan)
    person_repl = next(e.replacement for e in plan if e.label is EntityLabel.PERSON)
    alias_repls = [e.replacement for e in plan if e.label is EntityLabel.ALIAS_LABEL]
    assert len(alias_repls) == 2
    assert len(set(alias_repls)) == 1
    expected_alias = case_preserver.format_like("Morgan", person_repl.split()[0])
    assert alias_repls[0] == expected_alias
    assert "John Doe" not in new_text
    assert "Morgan" not in new_text


def test_role_alias_kept_when_policy_keep_roles() -> None:
    cfg = load_config()
    cfg.redact.alias_labels = "keep_roles"
    text = 'John Doe (the "Buyer") signed. Buyer then paid.'
    spans = [
        _span(0, 8, "John Doe", EntityLabel.PERSON, entity_id="p1"),
        _span(
            15,
            20,
            "Buyer",
            EntityLabel.ALIAS_LABEL,
            attrs={"alias_kind": "role", "cluster_id": "p1"},
            entity_id="p1",
        ),
        _span(
            31,
            36,
            "Buyer",
            EntityLabel.ALIAS_LABEL,
            attrs={"alias_kind": "role", "cluster_id": "p1"},
            entity_id="p1",
        ),
    ]
    plan = plan_builder.build_replacement_plan(text, spans, cfg)
    assert all(e.label is not EntityLabel.ALIAS_LABEL for e in plan)
    new_text, _ = applier.apply_plan(text, plan)
    assert "Buyer" in new_text
    assert "John Doe" not in new_text


def test_address_block_replacement() -> None:
    cfg = load_config()
    text = "Address:\n123 Main St\nSpringfield, IL 12345\nEnd."
    start = text.index("123 Main St")
    end = text.index("\nEnd.")
    block = text[start:end]
    spans = [
        _span(
            start,
            end,
            block,
            EntityLabel.ADDRESS_BLOCK,
            attrs={"line_kinds": ["street", "city_state_zip"]},
        ),
    ]
    plan = plan_builder.build_replacement_plan(text, spans, cfg)
    repl = plan[0].replacement
    assert repl.count("\n") == block.count("\n")
    assert "Main" not in repl and "Springfield" not in repl
    new_text, _ = applier.apply_plan(text, plan)
    assert "Main" not in new_text and "Springfield" not in new_text


def test_email_and_phone_replacement() -> None:
    cfg = load_config()
    text = "Contact: john@example.com, (415) 555-1212."
    spans = [
        _span(9, 25, "john@example.com", EntityLabel.EMAIL, attrs={"base_local": "john"}),
        _span(27, 41, "(415) 555-1212", EntityLabel.PHONE),
    ]
    plan = plan_builder.build_replacement_plan(text, spans, cfg)
    new_text, _ = applier.apply_plan(text, plan)
    assert "john@example.com" not in new_text
    assert "@example.org" in new_text
    assert "(415) 555-1212" not in new_text
    assert re.search(r"\(\d{3}\) \d{3}-\d{4}", new_text)


def test_account_id_replacements() -> None:
    cfg = load_config()
    text = (
        "CC 4111-1111-1111-1111, routing 123456789, IBAN GB82WEST12345698765432, SSN 123-45-6789."
    )
    spans = [
        _span(3, 22, "4111-1111-1111-1111", EntityLabel.ACCOUNT_ID, attrs={"subtype": "cc"}),
        _span(32, 41, "123456789", EntityLabel.ACCOUNT_ID, attrs={"subtype": "routing_aba"}),
        _span(48, 70, "GB82WEST12345698765432", EntityLabel.ACCOUNT_ID, attrs={"subtype": "iban"}),
        _span(76, 87, "123-45-6789", EntityLabel.ACCOUNT_ID, attrs={"subtype": "ssn"}),
    ]
    plan = plan_builder.build_replacement_plan(text, spans, cfg)
    by_sub = {e.meta.get("subtype"): e for e in plan}
    assert by_sub["cc"].replacement != "4111-1111-1111-1111"
    assert re.sub(r"\d", "0", by_sub["cc"].replacement) == re.sub(r"\d", "0", "4111-1111-1111-1111")
    assert by_sub["routing_aba"].replacement.isdigit()
    assert by_sub["routing_aba"].replacement != "123456789"
    assert len(by_sub["iban"].replacement) == len("GB82WEST12345698765432")
    assert by_sub["iban"].replacement[:2] == "GB"
    assert re.sub(r"\d", "0", by_sub["ssn"].replacement) == "000-00-0000"
    assert by_sub["ssn"].replacement != "123-45-6789"
    new_text, _ = applier.apply_plan(text, plan)
    assert "4111-1111-1111-1111" not in new_text
    assert "123456789" not in new_text
    assert "GB82WEST12345698765432" not in new_text
    assert "123-45-6789" not in new_text


def test_dob_vs_generic_date_policy() -> None:
    cfg = load_config()
    text = "Date of Birth: May 9, 1960. Executed on May 10, 1960."
    spans = [
        _span(
            15,
            26,
            "May 9, 1960",
            EntityLabel.DOB,
            attrs={"format": "month_name_mdY", "normalized": "1960-05-09"},
        ),
        _span(
            40,
            52,
            "May 10, 1960",
            EntityLabel.DATE_GENERIC,
            attrs={"format": "month_name_mdY", "normalized": "1960-05-10"},
        ),
    ]
    plan = plan_builder.build_replacement_plan(text, spans, cfg)
    assert any(e.label is EntityLabel.DOB for e in plan)
    assert all(e.label is not EntityLabel.DATE_GENERIC for e in plan)
    new_text, _ = applier.apply_plan(text, plan)
    assert "May 9, 1960" not in new_text
    assert "May 10, 1960" in new_text
    cfg.redact.generic_dates = True
    plan2 = plan_builder.build_replacement_plan(text, spans, cfg)
    new_text2, _ = applier.apply_plan(text, plan2)
    assert "May 9, 1960" not in new_text2
    assert "May 10, 1960" not in new_text2


def test_adjacent_spans_apply_independently() -> None:
    cfg = load_config()
    text = "AliceBob"
    spans = [
        _span(0, 5, "Alice", EntityLabel.PERSON, entity_id="p1"),
        _span(5, 8, "Bob", EntityLabel.PERSON, entity_id="p2"),
    ]
    plan = plan_builder.build_replacement_plan(text, spans, cfg)
    new_text, _ = applier.apply_plan(text, plan)
    assert "Alice" not in new_text and "Bob" not in new_text
    assert len(plan) == 2


def test_idempotent_application() -> None:
    cfg = load_config()
    text = "John Doe"
    spans = [_span(0, 8, "John Doe", EntityLabel.PERSON, entity_id="p1")]
    plan = plan_builder.build_replacement_plan(text, spans, cfg)
    new_text, _ = applier.apply_plan(text, plan)
    new_text2, _ = applier.apply_plan(new_text, plan)
    assert new_text2 == new_text


def test_deterministic_outputs() -> None:
    cfg = load_config()
    text = "Jane Doe met Jane Doe."
    start = text.index("Jane Doe")
    spans = [_span(start, start + 8, "Jane Doe", EntityLabel.PERSON, entity_id="p1")]
    plan1 = plan_builder.build_replacement_plan(text, spans, cfg)
    red1, _ = applier.apply_plan(text, plan1)
    plan2 = plan_builder.build_replacement_plan(text, spans, cfg)
    red2, _ = applier.apply_plan(text, plan2)
    assert red1 == red2
