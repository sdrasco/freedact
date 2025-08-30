import pytest

from redactor.detect.aliases import AliasDetector
from redactor.detect.base import Detector, EntityLabel


@pytest.fixture
def det() -> AliasDetector:
    return AliasDetector()


def test_hereinafter_same_line(det: AliasDetector) -> None:
    text = 'John Doe, hereinafter "Morgan", agrees'
    spans = det.detect(text)
    assert len(spans) == 1
    span = spans[0]
    assert span.text == "Morgan"
    start = text.index('"Morgan"') + 1
    assert (span.start, span.end) == (start, start + len("Morgan"))
    assert span.label is EntityLabel.ALIAS_LABEL
    attrs = span.attrs
    assert attrs["alias"] == "Morgan"
    assert attrs["trigger"] == "hereinafter"
    assert attrs["subject_text"] == "John Doe"
    assert attrs["scope_hint"] == "same_line"
    assert attrs["alias_kind"] == "nickname"
    assert attrs["role_flag"] is False
    assert attrs["subject_span"] == {"start": 0, "end": len("John Doe")}
    assert span.confidence == pytest.approx(0.99)


def test_role_alias(det: AliasDetector) -> None:
    text = 'Acme LLC (hereinafter referred to as "Seller")'
    spans = det.detect(text)
    assert len(spans) == 1
    span = spans[0]
    assert span.text == "Seller"
    attrs = span.attrs
    assert attrs["alias_kind"] == "role"
    assert attrs["role_flag"] is True
    assert attrs["subject_text"] == "Acme LLC"
    assert attrs["trigger"] == "hereinafter"


def test_hereinafter_prev_line_guess(det: AliasDetector) -> None:
    text = 'John Doe\nHereinafter "Morgan" signs'
    spans = det.detect(text)
    assert len(spans) == 1
    span = spans[0]
    attrs = span.attrs
    assert attrs["subject_text"] is None
    assert attrs["subject_guess"] == "John Doe"
    assert attrs["subject_guess_line"] == 0
    assert attrs["scope_hint"] == "prev_lines"
    assert span.confidence == pytest.approx(0.97)


def test_aka(det: AliasDetector) -> None:
    text = 'Jane Smith, a/k/a "Janie"'
    spans = det.detect(text)
    assert len(spans) == 1
    span = spans[0]
    attrs = span.attrs
    assert span.text == "Janie"
    assert attrs["trigger"] == "aka"
    assert attrs["alias_kind"] == "nickname"


def test_fka(det: AliasDetector) -> None:
    text = 'Robert Roe f/k/a "Rob Roe"'
    span = det.detect(text)[0]
    assert span.text == "Rob Roe"
    assert span.attrs["trigger"] == "fka"


def test_dba(det: AliasDetector) -> None:
    text = 'Widgets Inc., d/b/a "Acme Widgets"'
    span = det.detect(text)[0]
    assert span.text == "Acme Widgets"
    assert span.attrs["trigger"] == "dba"


def test_boundary_and_quotes(det: AliasDetector) -> None:
    text = '(hereinafter "Buyer"),'
    span = det.detect(text)[0]
    start = text.index('"Buyer"') + 1
    assert (span.start, span.end) == (start, start + len("Buyer"))
    assert span.attrs["quote_style"] is not None


@pytest.mark.parametrize(
    "text",
    [
        "The bank shall hereinafter be referred to as the institution",
        "aka the party",
        "\u201cjohnny\u201d",
    ],
)
def test_negatives(det: AliasDetector, text: str) -> None:
    assert det.detect(text) == []


def test_offsets_and_dedup(det: AliasDetector) -> None:
    text = 'Jane Smith, a/k/a "Janie" and also a/k/a "Janie"'
    spans = det.detect(text)
    assert len(spans) == 2
    assert spans[0].text == spans[1].text == "Janie"
    assert spans[0].start != spans[1].start
    assert all(span.label is EntityLabel.ALIAS_LABEL for span in spans)


def test_detector_protocol() -> None:
    det = AliasDetector()
    assert isinstance(det, Detector)
