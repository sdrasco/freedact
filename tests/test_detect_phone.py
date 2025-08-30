import pytest

from redactor.detect.base import DetectionContext, EntityLabel
from redactor.detect.phone import PhoneDetector


@pytest.fixture
def det() -> PhoneDetector:
    return PhoneDetector()


def test_true_positive_basic(det: PhoneDetector) -> None:
    text = "Call 415-555-2671 today."
    spans = det.detect(text)
    assert len(spans) == 1
    span = spans[0]
    assert span.text == "415-555-2671"
    assert span.start == text.index("415-555-2671")
    assert span.end == span.start + len("415-555-2671")
    assert isinstance(span.attrs["e164"], str)
    assert span.attrs["e164"].startswith("+1")
    assert span.attrs["type"] in {"fixed_line", "mobile", "fixed_line_or_mobile"}


def test_true_positive_with_extension(det: PhoneDetector) -> None:
    text = "Office: +1 (212) 555-0000 ext. 23"
    spans = det.detect(text)
    assert len(spans) == 1
    span = spans[0]
    assert "ext. 23" in span.text
    assert span.attrs["extension"] == "23"
    assert isinstance(span.attrs["e164"], str)
    assert span.attrs["e164"].startswith("+1")


def test_true_positive_with_region(det: PhoneDetector) -> None:
    text = "EU: +44 20 7946 0958"
    spans = det.detect(text, DetectionContext(locale="GB"))
    assert len(spans) == 1
    span = spans[0]
    assert span.attrs["region_code"] == "GB"
    assert isinstance(span.attrs["international"], str)
    assert span.attrs["international"].startswith("+44")


def test_multiple_numbers_offsets(det: PhoneDetector) -> None:
    text = "(650) 253-0000, (650) 253-0001"
    spans = det.detect(text)
    assert len(spans) == 2
    assert spans[0].text == "(650) 253-0000"
    assert spans[1].text == "(650) 253-0001"
    first_start = text.index("(650) 253-0000")
    second_start = text.index("(650) 253-0001")
    assert spans[0].start == first_start
    assert spans[0].end == first_start + len("(650) 253-0000")
    assert spans[1].start == second_start
    assert spans[1].end == second_start + len("(650) 253-0001")


def test_trimming_parenthesis(det: PhoneDetector) -> None:
    text = "(415) 555-0123)."
    spans = det.detect(text)
    assert spans
    span = spans[0]
    assert span.text == "(415) 555-0123"
    assert span.end == span.start + len("(415) 555-0123")


def test_trimming_semicolon(det: PhoneDetector) -> None:
    text = "Tel: +49 89 636-48018;"
    spans = det.detect(text)
    assert spans and spans[0].text == "+49 89 636-48018"


@pytest.mark.parametrize(
    "text",
    [
        "2020-12-31",
        "03/04/2021",
        "SSN 123-45-6789",
        "§ 123.45(a)(2)",
        "4111 1111 1111 1111",
        "No. 1234",
        "Ref: 123-456-789",
    ],
)
def test_negatives(det: PhoneDetector, text: str) -> None:
    assert det.detect(text) == []


def test_offsets_and_dedup(det: PhoneDetector) -> None:
    text = "Call 415-555-0000 or 415-555-0000."
    spans = det.detect(text)
    assert len(spans) == 2
    starts = {s.start for s in spans}
    assert len(starts) == 2


def test_region_behavior(det: PhoneDetector) -> None:
    text = "Call 020 7946 0958"
    us_spans = det.detect(text, DetectionContext(locale="US"))
    gb_spans = det.detect(text, DetectionContext(locale="GB"))
    assert us_spans == []
    assert len(gb_spans) == 1
    assert isinstance(gb_spans[0].attrs["e164"], str)
    assert gb_spans[0].attrs["e164"].startswith("+44")


def test_detector_protocol(det: PhoneDetector) -> None:
    text = "Numbers: 415-555-2671 and +1 (212) 555-0000"
    spans = det.detect(text)
    seen: set[tuple[int, int]] = set()
    for span in spans:
        assert span.label is EntityLabel.PHONE
        assert 0 <= span.start < span.end <= len(text)
        key = (span.start, span.end)
        assert key not in seen
        seen.add(key)
