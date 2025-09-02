import pytest

from redactor.detect.base import Detector, EntityLabel
from redactor.detect.date_dob import DOBDetector
from redactor.detect.date_generic import DateGenericDetector

MONTH_NAME = "May 9, 1960"
NUMERIC = "03/18/1976"
ALT_NUMERIC = "08/05/1992"
ALT_NUMERIC_NEXT = "08/06/1992"


@pytest.fixture
def det_generic() -> DateGenericDetector:
    return DateGenericDetector()


@pytest.fixture
def det_dob() -> DOBDetector:
    return DOBDetector()


# ---------------------------------------------------------------------------
# Positive DOB detections
# ---------------------------------------------------------------------------


def test_dob_date_of_birth(det_generic: DateGenericDetector, det_dob: DOBDetector) -> None:
    text = f"Date of Birth: {MONTH_NAME}"
    g_spans = det_generic.detect(text)
    assert g_spans and g_spans[0].attrs["normalized"] == "1960-05-09"
    spans = det_dob.detect(text)
    assert len(spans) == 1
    span = spans[0]
    assert span.text == MONTH_NAME
    expected_start = text.index(MONTH_NAME)
    assert span.start == expected_start
    assert span.end == expected_start + len(MONTH_NAME)
    assert span.attrs["normalized"] == "1960-05-09"
    assert span.attrs["trigger"] == "date_of_birth"
    assert span.attrs["line_scope"] == "same_line"
    assert span.label is EntityLabel.DOB


def test_dob_short_label_numeric(det_dob: DOBDetector) -> None:
    text = f"DOB: {NUMERIC}"
    spans = det_dob.detect(text)
    assert len(spans) == 1
    span = spans[0]
    expected_start = text.index(NUMERIC)
    assert span.start == expected_start
    assert span.end == expected_start + len(NUMERIC)
    assert span.attrs["normalized"] == "1976-03-18"
    assert span.attrs["trigger"] == "dob"


def test_dob_born_trigger(det_dob: DOBDetector) -> None:
    text = f"Born on {MONTH_NAME}"
    spans = det_dob.detect(text)
    assert len(spans) == 1
    span = spans[0]
    assert span.attrs["normalized"] == "1960-05-09"
    assert span.attrs["trigger"] == "born"


# ---------------------------------------------------------------------------
# Generic date detections without DOB
# ---------------------------------------------------------------------------


def test_generic_not_dob(det_generic: DateGenericDetector, det_dob: DOBDetector) -> None:
    text1 = f"Executed on {MONTH_NAME}"
    assert det_generic.detect(text1)
    assert det_dob.detect(text1) == []

    text2 = "As of 2020-01-31, the agreement…"
    assert det_generic.detect(text2)
    assert det_dob.detect(text2) == []


# ---------------------------------------------------------------------------
# Punctuation trimming
# ---------------------------------------------------------------------------


def test_punctuation_trimming(det_generic: DateGenericDetector, det_dob: DOBDetector) -> None:
    text = f"(Date of Birth: {MONTH_NAME})."
    g_spans = det_generic.detect(text)
    assert g_spans and g_spans[0].text == MONTH_NAME
    spans = det_dob.detect(text)
    assert spans and spans[0].text == MONTH_NAME


# ---------------------------------------------------------------------------
# Multiple dates
# ---------------------------------------------------------------------------


def test_multiple_dates(det_generic: DateGenericDetector, det_dob: DOBDetector) -> None:
    text = f"DOB: {ALT_NUMERIC}. Executed on {ALT_NUMERIC_NEXT}."
    g_spans = det_generic.detect(text)
    assert [s.text for s in g_spans] == [ALT_NUMERIC, ALT_NUMERIC_NEXT]
    spans = det_dob.detect(text)
    assert [s.text for s in spans] == [ALT_NUMERIC]


# ---------------------------------------------------------------------------
# Edge validation
# ---------------------------------------------------------------------------


def test_invalid_date_not_dob(det_generic: DateGenericDetector, det_dob: DOBDetector) -> None:
    text = "DOB: February 29, 2021"
    g_spans = det_generic.detect(text)
    assert g_spans and g_spans[0].attrs["normalized"] is None
    assert det_dob.detect(text) == []


# ---------------------------------------------------------------------------
# Line context
# ---------------------------------------------------------------------------


def test_line_context_same_and_prev(det_dob: DOBDetector) -> None:
    text = f"John Doe\nDate of Birth: {NUMERIC}\nAddress: ..."
    spans = det_dob.detect(text)
    assert spans and spans[0].attrs["line_scope"] == "same_line"
    assert spans[0].attrs["trigger"] == "date_of_birth"

    text2 = f"Date of Birth:\n{MONTH_NAME}"
    spans2 = det_dob.detect(text2)
    assert spans2 and spans2[0].attrs["line_scope"] == "prev_line"


# ---------------------------------------------------------------------------
# Detector protocol integration
# ---------------------------------------------------------------------------


def test_detector_protocol(det_generic: DateGenericDetector, det_dob: DOBDetector) -> None:
    assert isinstance(det_generic, Detector)
    assert isinstance(det_dob, Detector)
    text = f"Date of Birth: {MONTH_NAME}"
    spans = det_dob.detect(text)
    for span in spans:
        assert 0 <= span.start < span.end <= len(text)
