import pytest

from redactor.detect.account_ids import AccountIdDetector
from redactor.detect.base import EntityLabel, EntitySpan


@pytest.fixture
def det() -> AccountIdDetector:
    return AccountIdDetector()


def _find_span(spans: list[EntitySpan], subtype: str) -> EntitySpan:
    for s in spans:
        if s.attrs.get("subtype") == subtype:
            return s
    raise AssertionError(f"no span with subtype {subtype}")


def test_true_positive_iban(det: AccountIdDetector) -> None:
    text = "IBAN: GB82 WEST 1234 5698 7654 32."
    spans = det.detect(text)
    assert len(spans) == 1
    span = spans[0]
    assert span.text == "GB82 WEST 1234 5698 7654 32"
    assert span.start == text.index("GB82 WEST 1234 5698 7654 32")
    assert span.attrs["subtype"] == "iban"
    assert span.attrs["normalized"] == "GB82WEST12345698765432"
    assert span.attrs["issuer_or_country"] == "GB"
    assert span.label is EntityLabel.ACCOUNT_ID


def test_true_positive_bic(det: AccountIdDetector) -> None:
    text = "SWIFT: DEUTDEFF;"
    spans = det.detect(text)
    assert len(spans) == 1
    span = spans[0]
    assert span.text == "DEUTDEFF"
    assert span.attrs["subtype"] == "swift_bic"
    assert span.attrs["issuer_or_country"] == "DE"


def test_true_positive_aba_with_context(det: AccountIdDetector) -> None:
    text = "Routing number (ABA): 021000021, Account: 000123456789."
    spans = det.detect(text)
    span = _find_span(spans, "routing_aba")
    assert span.text == "021000021"
    assert span.attrs["subtype"] == "routing_aba"
    assert span.attrs["normalized"] == "021000021"
    assert span.attrs["issuer_or_country"] == "US"


def test_true_positive_card(det: AccountIdDetector) -> None:
    text = "Card: 4111 1111 1111 1111."
    spans = det.detect(text)
    assert len(spans) == 1
    span = spans[0]
    assert span.attrs["subtype"] == "cc"
    assert span.attrs["scheme"] == "visa"
    assert span.attrs["normalized"] == "4111111111111111"


def test_true_positive_ssn(det: AccountIdDetector) -> None:
    text = "SSN 123-45-6789"
    spans = det.detect(text)
    assert len(spans) == 1
    span = spans[0]
    assert span.attrs["subtype"] == "ssn"
    assert span.attrs["display"] == "123-45-6789"
    assert span.attrs["normalized"] == "123456789"


def test_true_positive_ein(det: AccountIdDetector) -> None:
    text = "Employer EIN: 12-3456789"
    spans = det.detect(text)
    span = _find_span(spans, "ein")
    assert span.attrs["display"] == "12-3456789"
    assert span.attrs["normalized"] == "123456789"


def test_negatives_bare_aba(det: AccountIdDetector) -> None:
    assert det.detect("021000021") == []


def test_ein_requires_hyphen(det: AccountIdDetector) -> None:
    spans = det.detect("12-3456789")
    assert _find_span(spans, "ein").attrs["normalized"] == "123456789"
    spans = det.detect("123456789")
    assert all(s.attrs.get("subtype") != "ein" for s in spans)


def test_generic_floor(det: AccountIdDetector) -> None:
    assert det.detect("acct abcdefghij") == []
    assert det.detect("Ref: 12-34") == []
    spans = det.detect("Ref: 123-456")
    span = _find_span(spans, "generic")
    assert span.text == "123-456"


def test_true_positive_generic(det: AccountIdDetector) -> None:
    text = "Acct # 0034-567-89012"
    spans = det.detect(text)
    span = _find_span(spans, "generic")
    assert span.text == "0034-567-89012"
    assert span.attrs["normalized"] == "003456789012"


def test_boundary_trimming_iban(det: AccountIdDetector) -> None:
    text = "(GB82WEST12345698765432),"
    spans = det.detect(text)
    assert spans and spans[0].text == "GB82WEST12345698765432"


def test_boundary_trimming_card(det: AccountIdDetector) -> None:
    text = "Card: 4111111111111111)."
    spans = det.detect(text)
    assert spans and spans[0].text == "4111111111111111"


@pytest.mark.parametrize(
    "text",
    [
        "2021-03-04",
        "1,234.56",
        "03/04/2021",
        "§ 123.45(a)(2)",
        "user@example.com",
    ],
)
def test_negatives(det: AccountIdDetector, text: str) -> None:
    assert det.detect(text) == []


def test_overlap_keeps_iban(det: AccountIdDetector) -> None:
    text = "IBAN: GB82 WEST 1234 5698 7654 32"
    spans = det.detect(text)
    assert len(spans) == 1
    assert spans[0].attrs["subtype"] == "iban"


def test_duplicate_card_numbers(det: AccountIdDetector) -> None:
    text = "4111111111111111 4111111111111111"
    spans = det.detect(text)
    assert len(spans) == 2
    assert spans[0].start != spans[1].start
