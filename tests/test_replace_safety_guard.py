from __future__ import annotations

import re

from redactor.config import load_config
from redactor.detect.base import EntityLabel, EntitySpan
from redactor.replace import plan_builder


def _span(
    start: int,
    end: int,
    text: str,
    label: EntityLabel,
    *,
    attrs: dict[str, object] | None = None,
) -> EntitySpan:
    return EntitySpan(start, end, text, label, "test", 0.9, attrs or {})


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


def test_email_replacement_safe_domain() -> None:
    cfg = load_config()
    src = "john@acme.com"
    text = f"Contact {src}"
    s = text.index(src)
    span = _span(s, s + len(src), src, EntityLabel.EMAIL, attrs={"base_local": "john"})
    plan = plan_builder.build_replacement_plan(text, [span], cfg)
    repl = plan[0].replacement
    assert repl.endswith("@example.org")
    local = repl.split("@", 1)[0].split("+", 1)[0]
    assert local.lower() != "john"


def test_phone_replacement_uses_safe_pattern() -> None:
    cfg = load_config()
    src = "(415) 867-5309"
    text = f"Call {src} now"
    s = text.index(src)
    span = _span(s, s + len(src), src, EntityLabel.PHONE)
    plan = plan_builder.build_replacement_plan(text, [span], cfg)
    repl = plan[0].replacement
    for sc, rc in zip(src, repl, strict=True):
        if not sc.isdigit():
            assert sc == rc
    digits = re.sub(r"\D", "", repl)
    if repl.startswith("+"):
        assert digits.startswith("1555")
    else:
        assert digits[3:6] == "555"


def test_account_routing_safe() -> None:
    cfg = load_config()
    src = "021000021"
    text = f"routing {src}"
    s = text.index(src)
    span = _span(s, s + len(src), src, EntityLabel.ACCOUNT_ID, attrs={"subtype": "routing_aba"})
    plan = plan_builder.build_replacement_plan(text, [span], cfg)
    repl = plan[0].replacement
    digits = re.sub(r"\D", "", repl)
    assert digits != src
    assert len(digits) == 9
    assert _aba_check_digit(digits[:8]) == digits[8]
    assert digits != "021000021"


def test_account_ein_safe() -> None:
    cfg = load_config()
    src = "12-3456789"
    text = f"ein {src}"
    s = text.index(src)
    span = _span(s, s + len(src), src, EntityLabel.ACCOUNT_ID, attrs={"subtype": "ein"})
    plan = plan_builder.build_replacement_plan(text, [span], cfg)
    repl = plan[0].replacement
    assert re.fullmatch(r"\d{2}-\d{7}", repl)
    assert repl != src


def test_account_cc_safe() -> None:
    cfg = load_config()
    src = "4111 1111 1111 1111"
    text = f"cc {src}"
    s = text.index(src)
    span = _span(s, s + len(src), src, EntityLabel.ACCOUNT_ID, attrs={"subtype": "cc"})
    plan = plan_builder.build_replacement_plan(text, [span], cfg)
    repl = plan[0].replacement
    digits = re.sub(r"\D", "", repl)
    assert repl != src
    assert _luhn_valid(digits)


def test_account_generic_safe() -> None:
    cfg = load_config()
    src = "000123-456-789"
    text = f"num {src}"
    s = text.index(src)
    span = _span(s, s + len(src), src, EntityLabel.ACCOUNT_ID, attrs={"subtype": "generic"})
    plan = plan_builder.build_replacement_plan(text, [span], cfg)
    repl = plan[0].replacement
    assert repl != src
    hy_src = [i for i, ch in enumerate(src) if ch == "-"]
    hy_repl = [i for i, ch in enumerate(repl) if ch == "-"]
    assert hy_src == hy_repl


def test_dob_safe_and_shaped() -> None:
    cfg = load_config()
    src = "July 4, 1982"
    text = f"DOB {src}"
    s = text.index(src)
    span = _span(
        s,
        s + len(src),
        src,
        EntityLabel.DOB,
        attrs={"format": "month_name_mdY", "normalized": "1982-07-04"},
    )
    plan = plan_builder.build_replacement_plan(text, [span], cfg)
    repl = plan[0].replacement
    assert repl != src
    assert re.fullmatch(r"[A-Za-z]+ \d{1,2}, \d{4}", repl)
