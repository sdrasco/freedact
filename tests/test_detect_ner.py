import pytest

from redactor.config.schema import load_config
from redactor.detect.base import EntityLabel
from redactor.detect.ner_spacy import SpacyNERDetector


@pytest.fixture
def det() -> SpacyNERDetector:
    cfg = load_config()
    return SpacyNERDetector(cfg)


def test_person_org_basic(det: SpacyNERDetector) -> None:
    text = "John Doe executed the agreement with Acme LLC."
    spans = det.detect(text)
    person = next(s for s in spans if s.label is EntityLabel.PERSON and s.text == "John Doe")
    org = next(s for s in spans if s.label is EntityLabel.ORG and s.text == "Acme LLC")
    assert person.start == text.index("John Doe")
    assert person.end == person.start + len("John Doe")
    assert org.start == text.index("Acme LLC")
    assert org.end == org.start + len("Acme LLC")


def test_boundary_trimming(det: SpacyNERDetector) -> None:
    text = "(John Doe),"
    spans = det.detect(text)
    person = next(s for s in spans if s.label is EntityLabel.PERSON)
    assert person.text == "John Doe"
    start = text.index("John Doe")
    assert person.start == start
    assert person.end == start + len("John Doe")


def test_role_suppression(det: SpacyNERDetector) -> None:
    text = 'hereinafter "Buyer"'
    spans = det.detect(text)
    assert all(s.text != "Buyer" for s in spans)


def test_gpe_optional(det: SpacyNERDetector) -> None:
    text = "Meeting in San Francisco, CA today."
    spans = det.detect(text)
    gpe_spans = [s for s in spans if s.label is EntityLabel.GPE]
    if gpe_spans:
        assert gpe_spans[0].text == "San Francisco, CA"


def test_spacy_specific() -> None:
    pytest.importorskip("spacy")
    cfg = load_config()
    cfg.detectors.ner.enabled = True
    cfg.detectors.ner.require = False
    det = SpacyNERDetector(cfg)
    text = "Jane Smith met at Example Ltd."
    spans = det.detect(text)
    person = next(s for s in spans if s.label is EntityLabel.PERSON and s.text == "Jane Smith")
    org = next(s for s in spans if s.label is EntityLabel.ORG and s.text == "Example Ltd.")
    assert person.attrs["mode"] in {"spacy", "ruler_fallback"}
    assert org.attrs["mode"] in {"spacy", "ruler_fallback"}


def test_duplicate_offsets(det: SpacyNERDetector) -> None:
    text = "Acme LLC met with Acme LLC"
    spans = det.detect(text)
    org_spans = [s for s in spans if s.label is EntityLabel.ORG]
    assert len(org_spans) == 2
    assert org_spans[0].start != org_spans[1].start
