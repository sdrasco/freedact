import re
from typing import Dict

import pytest

from redactor.config import load_config
from redactor.detect.base import EntityLabel, EntitySpan
from redactor.replace import plan_builder


def _span(
    start: int,
    end: int,
    text: str,
    label: EntityLabel,
    *,
    attrs: Dict[str, object] | None = None,
) -> EntitySpan:
    return EntitySpan(start, end, text, label, "t", 0.9, attrs or {})


def _luhn_valid(num: str) -> bool:
    total = 0
    for idx, ch in enumerate(reversed(num)):
        digit = int(ch)
        if idx % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def _aba_check_digit(eight: str) -> str:
    weights = [3, 7, 1] * 3
    total = sum(int(d) * w for d, w in zip(eight, weights, strict=False))
    return str((10 - total % 10) % 10)


def test_email_guard() -> None:
    cfg = load_config()
    text = "john@acme.com"
    spans = [_span(0, len(text), text, EntityLabel.EMAIL, attrs={"base_local": "john"})]
    plan = plan_builder.build_replacement_plan(text, spans, cfg)
    repl = plan[0].replacement
    assert repl.endswith("@example.org")
    assert repl != text
    local, _, domain = repl.partition("@")
    assert domain == "example.org"
    assert len(local.split("+")[0]) == len("john")


def test_phone_guard() -> None:
    cfg = load_config()
    text = "(415) 867-5309"
    spans = [_span(0, len(text), text, EntityLabel.PHONE)]
    plan = plan_builder.build_replacement_plan(text, spans, cfg)
    repl = plan[0].replacement
    digits = re.sub(r"\D", "", repl)
    assert digits[3:6] == "555"
    assert re.sub(r"\d", "0", repl) == re.sub(r"\d", "0", text)
    assert repl != text


def test_cc_guard() -> None:
    cfg = load_config()
    text = "4111-1111-1111-1111"
    spans = [_span(0, len(text), text, EntityLabel.ACCOUNT_ID, attrs={"subtype": "cc"})]
    plan = plan_builder.build_replacement_plan(text, spans, cfg)
    repl = plan[0].replacement
    digits = re.sub(r"\D", "", repl)
    assert _luhn_valid(digits)
    assert repl != text
    assert re.sub(r"\d", "0", repl) == re.sub(r"\d", "0", text)


def test_routing_guard() -> None:
    cfg = load_config()
    text = "123456789"
    spans = [_span(0, len(text), text, EntityLabel.ACCOUNT_ID, attrs={"subtype": "routing_aba"})]
    plan = plan_builder.build_replacement_plan(text, spans, cfg)
    repl = plan[0].replacement
    digits = re.sub(r"\D", "", repl)
    assert len(digits) == 9
    assert digits != "021000021"
    assert _aba_check_digit(digits[:8]) == digits[8]


def test_ein_guard() -> None:
    cfg = load_config()
    text = "12-3456789"
    spans = [_span(0, len(text), text, EntityLabel.ACCOUNT_ID, attrs={"subtype": "ein"})]
    plan = plan_builder.build_replacement_plan(text, spans, cfg)
    repl = plan[0].replacement
    assert re.fullmatch(r"\d{2}-\d{7}", repl)
    assert repl != text


def test_generic_account_guard() -> None:
    cfg = load_config()
    text = "123-456-7890"
    spans = [_span(0, len(text), text, EntityLabel.ACCOUNT_ID)]
    plan = plan_builder.build_replacement_plan(text, spans, cfg)
    repl = plan[0].replacement
    assert re.sub(r"\d", "0", repl) == re.sub(r"\d", "0", text)
    assert repl != text


def test_dob_guard() -> None:
    cfg = load_config()
    text = "May 9, 1960"
    spans = [_span(0, len(text), text, EntityLabel.DOB, attrs={"normalized": "1960-05-09"})]
    plan = plan_builder.build_replacement_plan(text, spans, cfg)
    repl = plan[0].replacement
    assert repl != text
    assert re.fullmatch(r"[A-Za-z]+ \d{1,2}, \d{4}", repl)


def test_ban_acct_prefix_non_account(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = load_config()
    text = "John"
    spans = [_span(0, len(text), text, EntityLabel.PERSON)]

    from redactor.pseudo import name_rules
    from redactor.pseudo.generator import PseudonymGenerator

    def fake_generate_person_like(source: str, *, key: str, gen: PseudonymGenerator) -> str:
        if key.endswith(":1"):
            return "Alan Smith"
        return "Acct_12345"

    monkeypatch.setattr(name_rules, "generate_person_like", fake_generate_person_like)
    plan = plan_builder.build_replacement_plan(text, spans, cfg)
    repl = plan[0].replacement
    assert not repl.lower().startswith("acct_")
