import pytest

from redactor.detect.base import Detector, EntityLabel
from redactor.detect.email import EmailDetector


@pytest.fixture
def det() -> EmailDetector:
    return EmailDetector()


def test_true_positive_basic(det: EmailDetector) -> None:
    text = "Contact john.doe@example.com for details."
    spans = det.detect(text)
    assert len(spans) == 1
    span = spans[0]
    assert span.text == "john.doe@example.com"
    assert span.start == text.index("john.doe@example.com")
    assert span.attrs["local"] == "john.doe"
    assert span.attrs["domain"] == "example.com"
    assert span.attrs["normalized"] == "john.doe@example.com"
    assert span.attrs["tld"] == "com"
    assert span.label is EntityLabel.EMAIL


def test_true_positive_with_tag(det: EmailDetector) -> None:
    text = "Send to user+tag@sub.example.co.uk now."
    spans = det.detect(text)
    assert len(spans) == 1
    span = spans[0]
    assert span.attrs["base_local"] == "user"
    assert span.attrs["tag"] == "tag"
    assert span.attrs["domain"] == "sub.example.co.uk"
    assert span.attrs["tld"] == "uk"


def test_true_positive_quoted(det: EmailDetector) -> None:
    text = '"Quoted" <"odd..name"@Example.ORG>'
    spans = det.detect(text)
    assert len(spans) == 1
    span = spans[0]
    assert span.text == '"odd..name"@Example.ORG'
    assert span.attrs["domain"] == "example.org"
    assert span.attrs["is_quoted_local"] is True
    assert span.attrs["normalized"] == '"odd..name"@example.org'


def test_true_positive_with_underscore_and_hyphen(det: EmailDetector) -> None:
    text = "first_last@acme-inc.com"
    spans = det.detect(text)
    assert len(spans) == 1
    assert spans[0].text == "first_last@acme-inc.com"


def test_boundary_trimming_parenthesis(det: EmailDetector) -> None:
    text = "(john@example.org),"
    spans = det.detect(text)
    assert spans and spans[0].text == "john@example.org"


def test_boundary_trimming_period(det: EmailDetector) -> None:
    text = "Email: john@example.org."
    spans = det.detect(text)
    assert spans and spans[0].text == "john@example.org"


@pytest.mark.parametrize(
    "text",
    [
        "john@example",
        "john..doe@example.com",
        "john.@example.com",
        "foo@-example.com",
        "foo@example-.com",
        "foo@example..com",
        "Reach me at example.com",
        "foo @example.com",
        "foo@bar.c",
    ],
)
def test_negatives(det: EmailDetector, text: str) -> None:
    assert det.detect(text) == []


def test_offsets_and_dedup(det: EmailDetector) -> None:
    text = "Emails: john@example.com and jane@example.org."
    spans = det.detect(text)
    assert [(s.start, s.end) for s in spans] == [
        (text.index("john@example.com"), text.index("john@example.com") + len("john@example.com")),
        (text.index("jane@example.org"), text.index("jane@example.org") + len("jane@example.org")),
    ]
    assert spans[0].text == "john@example.com"
    assert spans[1].text == "jane@example.org"


def test_repeated_substrings(det: EmailDetector) -> None:
    text = "john@example.com john@example.com"
    spans = det.detect(text)
    assert len(spans) == 2
    assert len({(s.start, s.end) for s in spans}) == 2


def test_case_behaviour(det: EmailDetector) -> None:
    text = 'Contact "odd..name"@Example.ORG for info.'
    spans = det.detect(text)
    assert spans[0].text == '"odd..name"@Example.ORG'
    assert spans[0].attrs["domain"] == "example.org"
    assert spans[0].attrs["normalized"] == '"odd..name"@example.org'
    assert spans[0].attrs["local"] == '"odd..name"'


def test_detector_integration() -> None:
    det = EmailDetector()
    assert isinstance(det, Detector)
    text = "Reach us at support@example.com or sales@example.org"
    spans = det.detect(text)
    seen: set[tuple[int, int]] = set()
    for span in spans:
        assert 0 <= span.start < span.end <= len(text)
        key = (span.start, span.end)
        assert key not in seen
        seen.add(key)
