import re
from typing import Dict

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


def test_name_case_and_initials() -> None:
    cfg = load_config()
    text = "JOHN DOE met J. D. Salinger."
    spans = [
        _span(0, 8, "JOHN DOE", EntityLabel.PERSON),
        _span(13, 27, "J. D. Salinger", EntityLabel.PERSON),
    ]
    plan = plan_builder.build_replacement_plan(text, spans, cfg)
    repls = [p.replacement for p in plan]
    assert repls[0].isupper()
    assert re.fullmatch(r"[A-Z]\. [A-Z]\. [A-Za-z]+", repls[1])


def test_date_and_phone_format() -> None:
    cfg = load_config()
    month_name = "May 9, 1960"
    numeric = "03/18/1976"
    text = f"DOB1: {month_name}; DOB2: {numeric}; Phone: (415) 867-5309"
    spans = [
        _span(6, 17, month_name, EntityLabel.DOB, attrs={"normalized": "1960-05-09"}),
        _span(25, 35, numeric, EntityLabel.DOB, attrs={"normalized": "1976-03-18"}),
        _span(44, 58, "(415) 867-5309", EntityLabel.PHONE),
    ]
    plan = plan_builder.build_replacement_plan(text, spans, cfg)
    dob_repls = [p.replacement for p in plan if p.label is EntityLabel.DOB]
    phone_repl = next(p.replacement for p in plan if p.label is EntityLabel.PHONE)
    assert re.fullmatch(r"[A-Za-z]+ \d{1,2}, \d{4}", dob_repls[0])
    assert re.fullmatch(r"\d{2}/\d{2}/\d{4}", dob_repls[1])
    assert re.sub(r"\d", "0", phone_repl) == "(000) 000-0000"
