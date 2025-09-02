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
    text = "DOB: 03/18/1976"
    new_text = _redact(text)
    assert re.search(r"\b\d{1,2}/\d{1,2}/\d{4}\b", new_text)
    assert "03/18/1976" not in new_text


def test_month_name_retains_month_name() -> None:
    text = "Date of Birth: May 9, 1960"
    new_text = _redact(text)
    assert re.search(r"[A-Z][a-z]+ \d{1,2}, \d{4}", new_text)
    assert "May 9, 1960" not in new_text
