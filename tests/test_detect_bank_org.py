import pytest

from redactor.detect.bank_org import BankOrgDetector
from redactor.detect.base import EntityLabel


@pytest.fixture
def det() -> BankOrgDetector:
    return BankOrgDetector()


def test_true_positive_bank_na(det: BankOrgDetector) -> None:
    text = "Plaintiff shall pay Chase Bank, N.A. within 30 days."
    spans = det.detect(text)
    assert len(spans) == 1
    span = spans[0]
    assert span.text == "Chase Bank, N.A."
    start = text.index("Chase Bank, N.A.")
    assert span.start == start
    assert span.end == start + len("Chase Bank, N.A.")
    assert span.label is EntityLabel.BANK_ORG
    assert span.attrs["kind"] == "bank"
    assert span.attrs["suffix"] in {"na", "national_association"}
    assert span.attrs["has_na"] is True
    assert span.confidence >= 0.98


def test_true_positive_bank_of(det: BankOrgDetector) -> None:
    text = "Deposit is held at Bank of Example, N.A., for escrow."
    spans = det.detect(text)
    assert len(spans) == 1
    span = spans[0]
    assert span.text == "Bank of Example, N.A."
    assert span.attrs["kind"] == "bank_of"
    assert span.attrs["suffix"] == "na"
    assert span.attrs["normalized"] == "bank of example, n.a."


def test_true_positive_credit_union(det: BankOrgDetector) -> None:
    text = "Account at Acme Credit Union will be used."
    spans = det.detect(text)
    assert spans and spans[0].text == "Acme Credit Union"
    assert spans[0].attrs["kind"] == "credit_union"
    assert spans[0].attrs["suffix"] is None


def test_true_positive_trust_company(det: BankOrgDetector) -> None:
    text = "Trustee: Example Trust Company"
    spans = det.detect(text)
    assert spans and spans[0].text == "Example Trust Company"
    assert spans[0].attrs["kind"] == "trust_company"


def test_true_positive_bank_plc(det: BankOrgDetector) -> None:
    text = "Escrow with Standard Chartered Bank PLC shall apply."
    spans = det.detect(text)
    assert spans and spans[0].text == "Standard Chartered Bank PLC"
    assert spans[0].attrs["kind"] == "bank"
    assert spans[0].attrs["suffix"] == "plc"


def test_true_positive_token_suffix(det: BankOrgDetector) -> None:
    text = "Citibank, N.A. agrees to…"
    spans = det.detect(text)
    assert spans and spans[0].text == "Citibank, N.A."
    assert spans[0].attrs["kind"] == "token_bank_suffix"
    assert spans[0].attrs["suffix"] == "na"


def test_true_positive_bank_and_trust(det: BankOrgDetector) -> None:
    text = "State Street Bank & Trust Company will serve as custodian."
    spans = det.detect(text)
    assert spans and spans[0].text == "State Street Bank & Trust Company"
    assert spans[0].attrs["kind"] == "bank_and_trust"


def test_trimming_parentheses(det: BankOrgDetector) -> None:
    text = "(Bank of Anywhere, N.A.),"
    spans = det.detect(text)
    assert spans and spans[0].text == "Bank of Anywhere, N.A."
    span = spans[0]
    start = text.index("Bank of Anywhere, N.A.")
    assert span.start == start
    assert span.end == start + len("Bank of Anywhere, N.A.")


def test_trimming_quotes(det: BankOrgDetector) -> None:
    text = '"Acme Credit Union".'
    spans = det.detect(text)
    assert spans and spans[0].text == "Acme Credit Union"


@pytest.mark.parametrize(
    "text",
    [
        "The food bank distributed meals.",
        "The Food Bank distributed meals.",
        "Please provide your bank account number.",
        "Bank holiday is on Monday.",
        "the bank shall notify…",
    ],
)
def test_negatives(det: BankOrgDetector, text: str) -> None:
    assert det.detect(text) == []


def test_offsets_and_multiples(det: BankOrgDetector) -> None:
    text = "Held at Wells Fargo Bank, N.A.; and at Acme Credit Union."
    spans = det.detect(text)
    assert len(spans) == 2
    first, second = spans
    assert first.text == "Wells Fargo Bank, N.A."
    assert second.text == "Acme Credit Union"
    first_start = text.index("Wells Fargo Bank, N.A.")
    second_start = text.index("Acme Credit Union")
    assert first.start == first_start
    assert first.end == first_start + len("Wells Fargo Bank, N.A.")
    assert second.start == second_start
    assert second.end == second_start + len("Acme Credit Union")
