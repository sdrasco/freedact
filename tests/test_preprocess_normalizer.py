"""Tests for text normalization."""

from __future__ import annotations

from redactor.preprocess.normalizer import normalize


def test_noop() -> None:
    text = "Simple text"
    result = normalize(text)
    assert result.text == text
    assert result.changed is False
    assert result.char_map == tuple(range(len(text)))


def test_quotes() -> None:
    text = "\u201cJohn\u2019s\u201d"
    result = normalize(text)
    assert result.text == '"John\'s"'
    assert result.changed is True


def test_zero_width_and_nbsp() -> None:
    text = "A\u200bB\u00a0C"
    result = normalize(text)
    assert result.text == "AB C"


def test_soft_hyphen() -> None:
    text = "co\u00adoperate"
    result = normalize(text)
    assert result.text == "cooperate"


def test_dehyphenation_map() -> None:
    text = "foo-\nbar"
    result = normalize(text)
    assert result.text == "foobar"
    assert result.char_map == (0, 1, 2, 5, 6, 7)


def test_nonletter_hyphen_preserved() -> None:
    text = "Apt -\n5B"
    result = normalize(text)
    assert result.text == text


def test_preserves_mixed_eols() -> None:
    text = "A\nB\r\nC"
    result = normalize(text)
    assert result.text == text
