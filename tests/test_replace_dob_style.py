import re

from redactor.config import load_config
from redactor.detect.date_dob import DOBDetector
from redactor.replace import applier, plan_builder


def _redact(text: str) -> str:
    cfg = load_config()
    det = DOBDetector()
    spans = det.detect(text)
    plan = plan_builder.build_replacement_plan(text, spans, cfg)
    new_text, _ = applier.apply_plan(text, plan)
    return new_text


def test_numeric_retains_numeric() -> None:
    text = "DOB: 12/21/1975"
    new_text = _redact(text)
    assert re.search(r"\b\d{1,2}/\d{1,2}/\d{4}\b", new_text)
    assert "12/21/1975" not in new_text


def test_month_name_retains_month_name() -> None:
    text = "Date of Birth: July 4, 1982"
    new_text = _redact(text)
    assert re.search(r"[A-Z][a-z]+ \d{1,2}, \d{4}", new_text)
    assert "July 4, 1982" not in new_text
