"""Heuristics for detecting whether text resembles a personal name.

This module exposes a small, dependency‑free API used by other detectors to
validate PERSON candidates and to perform light‑weight parsing.  The heuristics
are intentionally high precision and avoid cultural over‑reach – the goal is not
a full name parser and no gender inference is performed.

Scoring rules are deterministic and documented so callers can tune thresholds:

* **+0.45** – at least two core tokens (e.g. given + surname) or initials with a
  surname.
* **+0.15** – for each additional core token up to two more (max +0.30).
* **+0.15** – exactly one or two initials with at least one core surname token.
* **+0.10** – recognised particle between given and surname (``de``, ``van``,
  ``of`` ...).
* **+0.05** – common suffix present (``Jr.``, ``III``, ``Esq.``, ``Ph.D.`` ...).
* **−0.25** – any token contains digits.
* **−0.20** – all tokens uppercase and any token is a legal role/stopword.
* **−0.30** – a single token that matches a role lexicon (``Buyer``,
  ``Defendant`` ...).

The final score is clamped to ``[0.0, 1.0]`` and ``is_probable_person_name``
uses a default threshold of ``0.60``.  Unicode letters are accepted and curly
apostrophes/quotes are normalised to their ASCII forms for token tests.  Tokens
may contain interior apostrophes or hyphens; ``normalized_tokens`` title‑case
segments after these punctuation marks.
"""

from __future__ import annotations

import re
from typing import Dict, List

__all__ = [
    "tokenize_name",
    "is_titlecase_word",
    "is_initial",
    "is_particle",
    "is_suffix",
    "is_honorific",
    "is_core_name_token",
    "is_roman_numeral",
    "score_person_name",
    "is_probable_person_name",
    "parse_person_name",
]

# ---------------------------------------------------------------------------
# Lexicons
# ---------------------------------------------------------------------------

PARTICLES: frozenset[str] = frozenset(
    {
        "de",
        "del",
        "della",
        "di",
        "da",
        "van",
        "von",
        "der",
        "den",
        "dos",
        "das",
        "du",
        "la",
        "le",
        "of",
        "bin",
        "bint",
        "ibn",
    }
)

SUFFIXES_NORMALIZED: frozenset[str] = frozenset(
    {
        "JR",
        "SR",
        "II",
        "III",
        "IV",
        "ESQ",
        "ESQUIRE",
        "PHD",
        "MD",
        "JD",
        "LLM",
        "CPA",
    }
)

HONORIFICS: frozenset[str] = frozenset(
    {
        "mr",
        "ms",
        "mrs",
        "mx",
        "dr",
        "prof",
        "hon",
        "sir",
        "dame",
        "lord",
        "lady",
        "rev",
        "fr",
        "judge",
        "justice",
    }
)

ROLE_LEXICON: frozenset[str] = frozenset(
    {
        "buyer",
        "seller",
        "plaintiff",
        "defendant",
        "appellant",
        "appellee",
        "petitioner",
        "respondent",
    }
)

# Stopwords used for uppercase penalty (includes role terms)
UPPER_STOPWORDS: frozenset[str] = frozenset(
    {
        *{w.upper() for w in ROLE_LEXICON},
        "UNITED",
        "STATES",
        "BANK",
        "SECTION",
        "OF",
        "AMERICA",
    }
)

# Tokens that should not count as core name tokens – common organisation words
ORG_STOPWORDS: frozenset[str] = frozenset(
    {
        "bank",
        "company",
        "co",
        "corp",
        "corporation",
        "inc",
        "llc",
        "llp",
        "ltd",
        "plc",
        "university",
        "college",
        "hospital",
        "association",
        "agency",
        "department",
        "section",
    }
)

ROMAN_NUMERALS: frozenset[str] = frozenset(
    {"I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"}
)

# ---------------------------------------------------------------------------
# Token utilities
# ---------------------------------------------------------------------------


def _normalize_quotes(text: str) -> str:
    return (
        text.replace("\u2019", "'")
        .replace("\u2018", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
    )


def tokenize_name(text: str) -> List[str]:
    """Split ``text`` into tokens suitable for name analysis."""

    text = _normalize_quotes(text).strip("\"'[]{}()<>")
    if not text:
        return []
    tokens: List[str] = []
    for raw in text.split():
        tok = raw.strip("[]{}()\"'")
        if tok:
            tokens.append(tok)
    return tokens


def is_titlecase_word(tok: str) -> bool:
    return bool(tok) and tok == tok.title() and tok.isalpha()


def is_initial(tok: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z]\.?", tok))


def is_particle(tok: str) -> bool:
    return tok in PARTICLES


def _normalize_suffix(tok: str) -> str:
    return re.sub(r"[\.\-]", "", tok).upper()


def is_suffix(tok: str) -> bool:
    return _normalize_suffix(tok) in SUFFIXES_NORMALIZED


def is_honorific(tok: str) -> bool:
    return tok.rstrip(".").lower() in HONORIFICS


def is_roman_numeral(tok: str) -> bool:
    return tok.upper().rstrip(".") in ROMAN_NUMERALS


def is_core_name_token(tok: str) -> bool:
    tok_norm = _normalize_quotes(tok)
    if any(ch.isdigit() for ch in tok_norm):
        return False
    if tok_norm.lower() in ORG_STOPWORDS:
        return False
    letters = tok_norm.replace("-", "").replace("'", "")
    if not letters.isalpha():
        return False
    return tok_norm[0].isalpha() and tok_norm[0].isupper()


def _normalize_token(tok: str) -> str:
    tok = _normalize_quotes(tok)
    parts = re.split(r"(['-])", tok)
    normalised = ""
    for part in parts:
        if part in {"'", "-"}:
            normalised += part
        else:
            normalised += part.capitalize()
    return normalised


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def score_person_name(text: str) -> float:
    """Return a confidence score in ``[0.0, 1.0]`` for ``text``.

    The scoring scheme is documented in the module docstring.  It favours
    typical Western-style names but allows for initials, particles and common
    suffixes.  Scores ``≥ 0.60`` are considered high confidence.
    """

    tokens = tokenize_name(text)
    if not tokens:
        return 0.0

    core_tokens = [t for t in tokens if is_core_name_token(t)]
    initials = [t for t in tokens if is_initial(t)]
    particles = [t for t in tokens if is_particle(t)]
    suffixes = [t for t in tokens if is_suffix(t)]

    score = 0.0

    if (len(core_tokens) >= 2) or (core_tokens and initials):
        score += 0.45
        if len(core_tokens) >= 2:
            score += 0.15
            additional_core = max(0, len(core_tokens) - 2)
            score += min(additional_core, 2) * 0.15

    if 1 <= len(initials) <= 2 and core_tokens:
        score += 0.15

    if particles:
        score += 0.10

    if suffixes:
        score += 0.05

    if any(any(ch.isdigit() for ch in t) for t in tokens):
        score -= 0.25

    if (
        all(t.isupper() for t in tokens)
        and len(tokens) > 1
        and any(t in UPPER_STOPWORDS for t in tokens)
    ):
        score -= 0.20

    if len(tokens) == 1 and tokens[0].lower() in ROLE_LEXICON:
        score -= 0.30

    return max(0.0, min(1.0, score))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def is_probable_person_name(text: str) -> bool:
    """Return ``True`` if ``text`` plausibly represents a personal name."""

    return score_person_name(text) >= 0.60


def parse_person_name(text: str) -> Dict[str, object]:
    """Parse ``text`` into name components and return structured info."""

    tokens = tokenize_name(text)
    honorifics: List[str] = []
    suffixes: List[str] = []

    i = 0
    while i < len(tokens) and is_honorific(tokens[i]):
        honorifics.append(tokens[i])
        i += 1
    tokens = tokens[i:]

    j = len(tokens) - 1
    while j >= 0 and (is_suffix(tokens[j]) or is_roman_numeral(tokens[j])):
        suffixes.insert(0, tokens[j])
        j -= 1
    tokens_main = tokens[: j + 1]

    particles: List[str] = []
    given: List[str] = []
    surname: List[str] = []

    if tokens_main:
        first_particle = next((idx for idx, t in enumerate(tokens_main) if is_particle(t)), None)
        if first_particle is not None:
            last_particle = first_particle
            while last_particle + 1 < len(tokens_main) and is_particle(
                tokens_main[last_particle + 1]
            ):
                last_particle += 1
            given = tokens_main[:first_particle]
            particles = tokens_main[first_particle : last_particle + 1]
            surname = tokens_main[last_particle + 1 :]
        else:
            if (
                len(tokens_main) >= 3
                and is_core_name_token(tokens_main[-1])
                and is_core_name_token(tokens_main[-2])
                and not is_initial(tokens_main[-2])
            ):
                given = tokens_main[:-2]
                surname = tokens_main[-2:]
            else:
                given = tokens_main[:-1]
                surname = tokens_main[-1:]

    initials = [t for t in given if is_initial(t)]

    normalized_tokens = [_normalize_token(t) for t in tokenize_name(text)]
    score = score_person_name(text)
    result: Dict[str, object] = {
        "honorifics": honorifics,
        "given": given,
        "particles": particles,
        "surname": surname,
        "suffixes": suffixes,
        "initials": initials,
        "raw_tokens": tokenize_name(text),
        "normalized_tokens": normalized_tokens,
        "score": score,
        "is_probable": score >= 0.60,
    }
    return result
