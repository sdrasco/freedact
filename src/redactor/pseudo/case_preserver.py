"""Utilities for preserving case and formatting of pseudonym replacements.

This module adapts generated replacement strings so that they resemble the
original spans.  It is intentionally lightweight and relies only on the
standard library.  The helpers are pure and deterministic; any required
randomness must be supplied by the caller via :class:`random.Random`.

Responsibilities
----------------
* Mirror the casing of the source text on the replacement.
* Preserve surrounding punctuation such as quotes or brackets.
* Re‑insert interior punctuation (apostrophes, hyphens, periods, spaces)
  according to the positions found in the source.
* Handle initials‑only patterns (e.g. ``"J.D."`` or ``"J. D."``).
* Carry over possessive suffixes (``'s`` or ``’s``) when present.

The module does **not** decide which tokens to use for a pseudonym – that is
the responsibility of the caller.  It only adjusts the supplied replacement so
that it matches the *shape* of the original span.

If the source contains no alphabetic characters the formatting utilities
return the replacement unchanged (aside from outer punctuation preservation).
When calculating punctuation positions only alphabetic characters advance the
letter offset; digits are ignored for this purpose.
"""

from __future__ import annotations

import random
import re
import string
from typing import List, Optional, Sequence, Tuple

from redactor.utils.textspan import detect_text_case


def match_case(source: str, replacement: str) -> str:
    """Return ``replacement`` with casing adapted from ``source``.

    If ``source`` is uniformly ``UPPER``/``LOWER``/``TITLE`` (as detected by
    :func:`redactor.utils.textspan.detect_text_case`), apply that casing to the
    entire ``replacement``.  Otherwise a character‑wise mapping is performed
    where each alphabetic character in ``replacement`` copies the case of the
    corresponding alphabetic character in ``source``.  When the strings have
    different numbers of letters the source pattern is cycled.
    Non‑alphabetic characters in ``replacement`` are left untouched.
    """

    case = detect_text_case(source)
    if case == "UPPER":
        return replacement.upper()
    if case == "LOWER":
        return replacement.lower()
    if case == "TITLE":
        return replacement.title()

    # Mixed case: map letter by letter.
    source_letters = [ch for ch in source if ch.isalpha()]
    if not source_letters:
        return replacement

    result: List[str] = []
    idx = 0
    for ch in replacement:
        if ch.isalpha():
            src_ch = source_letters[idx % len(source_letters)]
            idx += 1
            result.append(ch.upper() if src_ch.isupper() else ch.lower())
        else:
            result.append(ch)
    return "".join(result)


_INITIALS_RE = re.compile(r"^(?:[A-Za-z][.\- ]+)+[A-Za-z][.]?\Z")


def format_like(source: str, replacement: str, *, rng: Optional[random.Random] = None) -> str:
    """Format ``replacement`` so it mirrors ``source``.

    The function preserves outer punctuation, interior punctuation placement,
    possessive suffixes and casing.  If ``source`` is an initials‑only pattern
    (e.g. ``"J.D."`` or ``"J. D."``) initials are generated from
    ``replacement`` using :func:`preserve_initials`.

    For strings without alphabetic characters the ``replacement`` is returned
    unchanged apart from outer punctuation retention.
    """

    if _INITIALS_RE.fullmatch(source):
        return preserve_initials(source, replacement, rng=rng)

    prefix, core, suffix = extract_outer_punct(source)

    if not any(ch.isalpha() for ch in core):
        return prefix + replacement + suffix

    poss_suffix = ""
    core_work = core
    for suff in ("'s", "'S", "’s", "’S"):
        if core_work.endswith(suff):
            poss_suffix = suff
            core_work = core_work[: -len(suff)]
            break

    # Handle patterns with leading initials followed by additional tokens,
    # e.g. ``"J. D. Salinger"``.  The initials portion is preserved separately
    # before standard punctuation mirroring is applied to the remainder.
    m = re.match(r"^((?:[A-Za-z]\.[\s]*)+)(.+)$", core_work)
    if m:
        init_part = m.group(1).rstrip()
        rest_part = m.group(2).lstrip()
        tokens = re.findall(r"[^\W\d_]+", replacement)
        need = max(1, init_part.count("."))
        init_full = " ".join(tokens[:need]) if tokens else ""
        initials = preserve_initials(init_part, init_full, rng=rng)
        rest_full = " ".join(tokens[need:]) if len(tokens) > need else ""
        rest_fmt = match_case(rest_part, rest_full) if rest_full else rest_part
        out = initials + (" " + rest_fmt if rest_fmt else "")
        if poss_suffix:
            out += poss_suffix
        return prefix + out + suffix

    profile = letter_punct_profile(core_work)

    # When the replacement contains token boundaries (spaces), try to align
    # punctuation with those boundaries so hyphenated sources map to hyphenated
    # replacements rather than splitting tokens mid-letter.
    tokens = [t for t in replacement.split() if t]
    boundaries: list[int] = []
    count = 0
    for tok in tokens[:-1]:
        count += sum(1 for ch in tok if ch.isalpha())
        boundaries.append(count)
    adjusted: list[tuple[int, str]] = []
    for offset, punct in profile:
        new_offset = offset
        for boundary in boundaries:
            if offset < boundary:
                new_offset = boundary
                break
        adjusted.append((new_offset, punct))

    base = "".join(ch for ch in replacement if ch.isalnum())
    with_punct = apply_letter_punct_profile(base, adjusted)
    cased = match_case(core_work, with_punct)
    if poss_suffix:
        cased += poss_suffix
    return prefix + cased + suffix


def preserve_initials(
    source: str, replacement_full: str, *, rng: Optional[random.Random] = None
) -> str:
    """Return initials shaped like ``source`` derived from ``replacement_full``.

    ``source`` must be a sequence of single letters optionally separated by
    dots, spaces or hyphens.  The exact separator pattern – including spacing –
    is preserved.  If ``replacement_full`` provides fewer tokens than required
    initials, additional letters are generated.  A ``rng`` may be supplied for
    deterministic synthesis; if omitted the last available initial is reused.
    """

    letters: List[str] = []
    seps: List[str] = []
    buf = ""
    for ch in source:
        if ch.isalpha():
            letters.append(ch)
            if buf:
                seps.append(buf)
                buf = ""
        elif ch in ".- ":
            buf += ch
        else:
            # Not an initials pattern
            return match_case(source, replacement_full)
    seps.append(buf)

    if not letters:
        return replacement_full

    tokens = re.findall(r"[^\W\d_]+", replacement_full, flags=re.UNICODE)
    initials = [t[0] for t in tokens]
    if not initials:
        initials = ["A"]

    if len(initials) < len(letters):
        deficit = len(letters) - len(initials)
        if rng is not None:
            initials.extend(rng.choice(string.ascii_uppercase) for _ in range(deficit))
        else:
            initials.extend(initials[-1] for _ in range(deficit))
    else:
        initials = initials[: len(letters)]

    built = "".join(ch + sep for ch, sep in zip(initials, seps, strict=False))
    return match_case(source, built)


def extract_outer_punct(source: str) -> Tuple[str, str, str]:
    """Return ``(prefix, core, suffix)`` separating outer punctuation.

    ``prefix`` and ``suffix`` are contiguous runs of non‑alphanumeric characters
    from the start and end of ``source`` respectively.  ``core`` is the middle
    portion.
    """

    start = 0
    end = len(source)
    while start < end and not source[start].isalnum():
        start += 1
    while end > start and not source[end - 1].isalnum():
        end -= 1
    return source[:start], source[start:end], source[end:]


def letter_punct_profile(source: str) -> List[Tuple[int, str]]:
    """Return interior punctuation positions for ``source``.

    The result is a list of ``(letter_offset, punct)`` tuples where
    ``letter_offset`` counts only alphabetic characters.  Punctuation sequences
    (including spaces) between letters are recorded.  If ``source`` ends with
    punctuation after the final letter it is also included.
    """

    profile: List[Tuple[int, str]] = []
    letter_offset = 0
    buf = ""
    for ch in source:
        if ch.isalpha():
            if buf:
                profile.append((letter_offset, buf))
                buf = ""
            letter_offset += 1
        else:
            buf += ch
    if buf:
        profile.append((letter_offset, buf))
    return profile


def apply_letter_punct_profile(replacement_core: str, profile: Sequence[Tuple[int, str]]) -> str:
    """Insert punctuation defined by ``profile`` into ``replacement_core``.

    ``profile`` is typically produced by :func:`letter_punct_profile` and
    contains pairs of ``(letter_offset, punct)``.  ``letter_offset`` counts only
    alphabetic characters.  If an offset exceeds the number of available
    letters the punctuation is appended at the end.
    """

    if not profile:
        return replacement_core

    result: List[str] = []
    letters_seen = 0
    prof_iter = iter(sorted(profile, key=lambda x: x[0]))
    current = next(prof_iter, None)

    for ch in replacement_core:
        while current and letters_seen == current[0]:
            result.append(current[1])
            current = next(prof_iter, None)
        result.append(ch)
        if ch.isalpha():
            letters_seen += 1

    while current:
        result.append(current[1])
        current = next(prof_iter, None)
    return "".join(result)


__all__ = [
    "match_case",
    "format_like",
    "preserve_initials",
    "extract_outer_punct",
    "letter_punct_profile",
    "apply_letter_punct_profile",
]
