"""Tests for the conservative sentence segmenter."""

from __future__ import annotations

from redactor.preprocess.segmenter import SentenceSpan, segment_sentences


def texts(spans: list[SentenceSpan]) -> list[str]:
    return [s.text for s in spans]


def test_simple_split() -> None:
    s = segment_sentences("Alpha. Beta?")
    assert texts(s) == ["Alpha.", "Beta?"]


def test_abbreviation_guard() -> None:
    text = 'Mr. Smith signed on Jan. 5, 2020. Hereinafter "Buyer".'
    s = segment_sentences(text)
    assert len(s) == 2
    assert s[0].text.endswith("2020.")
    assert s[1].text == 'Hereinafter "Buyer".'


def test_quoted_terminator() -> None:
    text = 'He said, "Done." And left.'
    s = segment_sentences(text)
    assert texts(s) == ['He said, "Done."', "And left."]


def test_no_split_us() -> None:
    text = "In the U.S. District Court, the matter proceeded."
    s = segment_sentences(text)
    assert len(s) == 1
    assert s[0].text == text
