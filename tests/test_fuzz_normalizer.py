"""Fuzz normalizer-specific invariants.

These tests ensure that the :func:`normalize` function reverses the edits
introduced by :mod:`evaluation.fuzz` helpers.  They exercise zero-width
insertion, NBSP replacement, ad-hoc hyphenation and quote/EOL handling.
"""

from __future__ import annotations

from redactor.preprocess.normalizer import normalize


def _is_monotonic(map_: tuple[int, ...]) -> bool:
    return all(map_[i] < map_[i + 1] for i in range(len(map_) - 1))


def test_zero_width_and_nbsp() -> None:
    res = normalize("A\u200b\u00a0B")
    assert res.text == "A B"
    assert _is_monotonic(res.char_map)


def test_hyphenated_word() -> None:
    res = normalize("co-\noperate")
    assert res.text == "cooperate"
    assert res.char_map == (0, 1, 4, 5, 6, 7, 8, 9, 10)


def test_mixed_eols_preserved() -> None:
    res = normalize("a\r\nb\nc")
    assert res.text == "a\r\nb\nc"
    assert res.char_map == (0, 1, 2, 3, 4, 5)


def test_quote_normalization() -> None:
    res = normalize("\u201cQuote\u201d")
    assert res.text == '"Quote"'
