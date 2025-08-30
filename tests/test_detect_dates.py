import pytest

from redactor.detect.base import Detector, EntityLabel
from redactor.detect.date_dob import DOBDetector
from redactor.detect.date_generic import DateGenericDetector


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
    text = "Date of Birth: July 4, 1982"
    g_spans = det_generic.detect(text)
    assert g_spans and g_spans[0].attrs["normalized"] == "1982-07-04"
    spans = det_dob.detect(text)
    assert len(spans) == 1
    span = spans[0]
    assert span.text == "July 4, 1982"
    expected_start = text.index("July 4, 1982")
    assert span.start == expected_start
    assert span.end == expected_start + len("July 4, 1982")
    assert span.attrs["normalized"] == "1982-07-04"
    assert span.attrs["trigger"] == "date_of_birth"
    assert span.attrs["line_scope"] == "same_line"
    assert span.label is EntityLabel.DOB


def test_dob_short_label_numeric(det_dob: DOBDetector) -> None:
    text = "DOB 12/21/1975"
    spans = det_dob.detect(text)
    assert len(spans) == 1
    span = spans[0]
    expected_start = text.index("12/21/1975")
    assert span.start == expected_start
    assert span.end == expected_start + len("12/21/1975")
    assert span.attrs["normalized"] == "1975-12-21"
    assert span.attrs["trigger"] == "dob"


def test_dob_born_trigger(det_dob: DOBDetector) -> None:
    text = "Born on 4 July 1975"
    spans = det_dob.detect(text)
    assert len(spans) == 1
    span = spans[0]
    assert span.attrs["normalized"] == "1975-07-04"
    assert span.attrs["trigger"] == "born"


# ---------------------------------------------------------------------------
# Generic date detections without DOB
# ---------------------------------------------------------------------------


def test_generic_not_dob(det_generic: DateGenericDetector, det_dob: DOBDetector) -> None:
    text1 = "Executed on July 4, 1982"
    assert det_generic.detect(text1)
    assert det_dob.detect(text1) == []

    text2 = "As of 2020-01-31, the agreement…"
    assert det_generic.detect(text2)
    assert det_dob.detect(text2) == []


# ---------------------------------------------------------------------------
# Punctuation trimming
# ---------------------------------------------------------------------------


def test_punctuation_trimming(det_generic: DateGenericDetector, det_dob: DOBDetector) -> None:
    text = "(Date of Birth: July 4, 1982)."
    g_spans = det_generic.detect(text)
    assert g_spans and g_spans[0].text == "July 4, 1982"
    spans = det_dob.detect(text)
    assert spans and spans[0].text == "July 4, 1982"


# ---------------------------------------------------------------------------
# Multiple dates
# ---------------------------------------------------------------------------


def test_multiple_dates(det_generic: DateGenericDetector, det_dob: DOBDetector) -> None:
    text = "DOB: 07/04/1982. Executed on 07/05/1982."
    g_spans = det_generic.detect(text)
    assert [s.text for s in g_spans] == ["07/04/1982", "07/05/1982"]
    spans = det_dob.detect(text)
    assert [s.text for s in spans] == ["07/04/1982"]


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
    text = "John Doe\nDate of Birth: December 21, 1975\nAddress: ..."
    spans = det_dob.detect(text)
    assert spans and spans[0].attrs["line_scope"] == "same_line"
    assert spans[0].attrs["trigger"] == "date_of_birth"

    text2 = "Date of Birth\nJuly 4, 1982"
    spans2 = det_dob.detect(text2)
    assert spans2 and spans2[0].attrs["line_scope"] == "prev_line"


# ---------------------------------------------------------------------------
# Detector protocol integration
# ---------------------------------------------------------------------------


def test_detector_protocol(det_generic: DateGenericDetector, det_dob: DOBDetector) -> None:
    assert isinstance(det_generic, Detector)
    assert isinstance(det_dob, Detector)
    text = "Date of Birth: July 4, 1982"
    spans = det_dob.detect(text)
    for span in spans:
        assert 0 <= span.start < span.end <= len(text)
