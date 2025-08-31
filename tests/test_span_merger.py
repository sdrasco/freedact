from __future__ import annotations

from redactor.config.schema import ConfigModel, load_config
from redactor.detect.base import EntityLabel, EntitySpan
from redactor.link.span_merger import merge_spans


def _span(
    start: int,
    end: int,
    label: EntityLabel,
    *,
    text: str | None = None,
    source: str = "det",
    confidence: float = 0.9,
) -> EntitySpan:
    if text is None:
        text = "x" * (end - start)
    return EntitySpan(start, end, text, label, source, confidence)


def _cfg() -> ConfigModel:
    return load_config()


def test_dedupe_identical_ranges_confidence_and_source() -> None:
    cfg = _cfg()
    s1 = _span(0, 4, EntityLabel.PERSON, source="ner_spacy", confidence=0.95)
    s2 = _span(0, 4, EntityLabel.PERSON, source="heuristic", confidence=0.90)
    assert merge_spans([s1, s2], cfg) == [s1]

    # Same confidence – lexicographic source order decides
    s3 = _span(0, 4, EntityLabel.PERSON, source="ner_spacy", confidence=0.9)
    s4 = _span(0, 4, EntityLabel.PERSON, source="heuristic", confidence=0.9)
    assert merge_spans([s3, s4], cfg) == [s4]


def test_longer_wins_within_same_precedence() -> None:
    cfg = _cfg()
    short = _span(0, 4, EntityLabel.PERSON, text="John", confidence=0.90)
    long = _span(0, 8, EntityLabel.PERSON, text="John Doe", confidence=0.85)
    assert merge_spans([short, long], cfg) == [long]


def test_precedence_across_labels() -> None:
    cfg = _cfg()
    text = "foo@example.com"
    email = _span(0, len(text), EntityLabel.EMAIL, text=text, source="email")
    phone = _span(0, len(text), EntityLabel.PHONE, text=text, source="phone")
    assert merge_spans([phone, email], cfg) == [email]


def test_dob_beats_generic_date() -> None:
    cfg = _cfg()
    text = "01/02/2000"
    generic = _span(
        0,
        len(text),
        EntityLabel.DATE_GENERIC,
        text=text,
        source="date",
        confidence=0.97,
    )
    dob = _span(
        0,
        len(text),
        EntityLabel.DOB,
        text=text,
        source="dob",
        confidence=0.99,
    )
    assert merge_spans([generic, dob], cfg) == [dob]


def test_address_block_supersedes_line() -> None:
    cfg = _cfg()
    line_text = "123 Main St"
    block_text = f"{line_text}\nCity, ST"
    line = _span(
        0,
        len(line_text),
        EntityLabel.ADDRESS_BLOCK,
        text=line_text,
        source="address_line",
        confidence=0.9,
    )
    block = _span(
        0,
        len(block_text),
        EntityLabel.ADDRESS_BLOCK,
        text=block_text,
        source="address_block_merge",
        confidence=0.8,
    )
    assert merge_spans([line, block], cfg) == [block]


def test_non_overlapping_spans_pass_through_sorted() -> None:
    cfg = _cfg()
    person = _span(10, 15, EntityLabel.PERSON, text="Alice", source="ner")
    account = _span(20, 30, EntityLabel.ACCOUNT_ID, text="1234567890", source="acct")
    email = _span(0, 9, EntityLabel.EMAIL, text="a@b.co", source="email")
    result = merge_spans([person, account, email], cfg)
    assert result == [email, person, account]


def test_precedence_override_with_custom_config() -> None:
    cfg = _cfg()
    org = _span(0, 3, EntityLabel.ORG, text="Org", source="det1")
    bank = _span(0, 3, EntityLabel.BANK_ORG, text="Org", source="det2")
    assert merge_spans([org, bank], cfg)[0].label is EntityLabel.ORG

    # Swap precedence of ORG and BANK_ORG
    cfg2 = cfg.model_copy(deep=True)
    prec = cfg2.precedence[:]
    i_org = prec.index("ORG")
    i_bank = prec.index("BANK_ORG")
    prec[i_org], prec[i_bank] = prec[i_bank], prec[i_org]
    cfg2.precedence = prec
    assert merge_spans([org, bank], cfg2)[0].label is EntityLabel.BANK_ORG


def test_boundary_touching_allowed() -> None:
    cfg = _cfg()
    first = _span(0, 4, EntityLabel.PERSON, text="John", source="a")
    second = _span(4, 8, EntityLabel.PERSON, text="Doe", source="b")
    assert merge_spans([second, first], cfg) == [first, second]


def test_idempotence() -> None:
    cfg = _cfg()
    short = _span(0, 4, EntityLabel.PERSON, text="John", confidence=0.9)
    long = _span(0, 8, EntityLabel.PERSON, text="John Doe", confidence=0.85)
    phone = _span(10, 20, EntityLabel.PHONE, text="123", source="phone")
    email = _span(10, 20, EntityLabel.EMAIL, text="123", source="email")
    merged = merge_spans([short, long, phone, email], cfg)
    assert merge_spans(merged, cfg) == merged
