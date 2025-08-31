"""Deterministic text fuzzing utilities.

The helpers in this module introduce small, reversible perturbations into
fixtures used for pipeline tests.  They focus on whitespace, quote styles and
lexical triggers to stress brittle logic without changing the substantive
content of the document.

Examples of applied mutations:

* insertion of zero‑width characters between letters
* replacement of regular spaces with non‑breaking variants
* ad hoc hyphenation of long tokens (``foo-\nbar``)
* extra line breaks within long lines
* straight⇄curly quote swapping
* variant forms of alias and date‑of‑birth labels
* optional mixing of line ending styles

All edits are driven by a :class:`random.Random` seeded via
:func:`rng_from_seed`.  Given the same seed and options the output is fully
deterministic and contains only valid UTF‑8 characters.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass
from typing import Iterable, Literal

_ZW_CHARS = ["\u200b", "\u200c", "\u200d"]
_NBSP_CHARS = ["\u00a0", "\u202f"]


@dataclass(slots=True, frozen=True)
class FuzzOptions:
    """Configuration for :func:`mutate_text`.

    Attributes mirror the probabilities for each mutation.  ``max_variants``
    controls how many mutated versions :func:`variants` yields.
    """

    max_variants: int = 50
    insert_zero_width_prob: float = 0.2
    replace_nbsp_prob: float = 0.2
    break_words_prob: float = 0.2
    insert_linebreak_prob: float = 0.15
    quote_variant_prob: float = 0.3
    alias_trigger_variant_prob: float = 0.25
    dob_label_variant_prob: float = 0.25
    eol_style: Literal["mixed", "lf", "crlf"] = "mixed"


def rng_from_seed(seed: int) -> random.Random:
    """Return a deterministic :class:`~random.Random` seeded with ``seed``."""

    return random.Random(seed)


def _replace_nbsp(text: str, rng: random.Random, prob: float) -> str:
    out: list[str] = []
    for ch in text:
        if ch == " " and rng.random() < prob:
            out.append(rng.choice(_NBSP_CHARS))
        else:
            out.append(ch)
    return "".join(out)


def _insert_zero_width(text: str, rng: random.Random, prob: float) -> str:
    out: list[str] = []
    for i, ch in enumerate(text):
        out.append(ch)
        if i + 1 < len(text) and ch.isalpha() and text[i + 1].isalpha() and rng.random() < prob:
            out.append(rng.choice(_ZW_CHARS))
    return "".join(out)


_WORD_RE = re.compile(r"[A-Za-z]{8,}")


def break_token_with_hyphen(token: str, rng: random.Random) -> str:
    """Insert ``-\n`` at a deterministic position inside ``token``."""

    idx = rng.randint(2, len(token) - 2)
    return f"{token[:idx]}-\n{token[idx:]}"


def _break_words(text: str, rng: random.Random, prob: float) -> str:
    def repl(match: re.Match[str]) -> str:
        word = match.group(0)
        if rng.random() >= prob:
            return word
        return break_token_with_hyphen(word, rng)

    return _WORD_RE.sub(repl, text)


def _insert_linebreaks(text: str, rng: random.Random, prob: float) -> str:
    out_lines: list[str] = []
    for line in text.splitlines(keepends=True):
        if len(line) > 40 and rng.random() < prob:
            spaces = [m.start() for m in re.finditer(" ", line[:-1])]
            if spaces:
                idx = rng.choice(spaces)
                line = line[: idx + 1] + "\n" + line[idx + 1 :]
        out_lines.append(line)
    return "".join(out_lines)


_QUOTE_RE = re.compile(r'("[^"\n]*"|\u201c[^\u201d\n]*\u201d)')


def swap_quotes(text: str, rng: random.Random, prob: float) -> str:
    """Swap straight and curly quotes around quoted substrings."""

    def repl(match: re.Match[str]) -> str:
        grp = match.group(0)
        if rng.random() >= prob:
            return grp
        if grp.startswith("\u201c"):
            return f'"{grp[1:-1]}"'
        return f"\u201c{grp[1:-1]}\u201d"

    return _QUOTE_RE.sub(repl, text)


_ALIAS_RE = re.compile(r"\bhereinafter\b", re.IGNORECASE)


def vary_alias_labeling(text: str, rng: random.Random, prob: float) -> str:
    variants = ["Hereinafter", "hereinafter", "HEREINAFTER", "hereafter"]

    def repl(match: re.Match[str]) -> str:
        word = match.group(0)
        if rng.random() >= prob:
            return word
        return rng.choice(variants)

    return _ALIAS_RE.sub(repl, text)


_DOB_RE = re.compile(
    r"\b(?:DOB|D\.O\.B\.|Date of Birth)\b(?:\s*[:\-\u2014]\s*)?",
    re.IGNORECASE,
)


def vary_dob_labeling(text: str, rng: random.Random, prob: float) -> str:
    labels = ["DOB", "D.O.B.", "Date of Birth"]
    seps = [":", "-", "\u2014"]

    def repl(match: re.Match[str]) -> str:
        original = match.group(0)
        if rng.random() >= prob:
            return original
        return f"{rng.choice(labels)}{rng.choice(seps)} "

    return _DOB_RE.sub(repl, text)


def random_eol_mix(text: str, rng: random.Random, style: Literal["mixed", "lf", "crlf"]) -> str:
    """Apply the requested line-ending style to ``text``."""

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if style == "lf":
        return text
    if style == "crlf":
        return text.replace("\n", "\r\n")
    parts = text.split("\n")
    out: list[str] = []
    for i, part in enumerate(parts):
        out.append(part)
        if i < len(parts) - 1:
            out.append("\r\n" if rng.random() < 0.5 else "\n")
    return "".join(out)


def mutate_text(text: str, *, seed: int, opts: FuzzOptions) -> str:
    """Return a fuzzed variant of ``text`` using ``seed`` and ``opts``."""

    rng = rng_from_seed(seed)
    mutated = text
    mutated = vary_alias_labeling(mutated, rng, opts.alias_trigger_variant_prob)
    mutated = vary_dob_labeling(mutated, rng, opts.dob_label_variant_prob)
    mutated = swap_quotes(mutated, rng, opts.quote_variant_prob)
    mutated = _replace_nbsp(mutated, rng, opts.replace_nbsp_prob)
    mutated = _insert_zero_width(mutated, rng, opts.insert_zero_width_prob)
    mutated = _break_words(mutated, rng, opts.break_words_prob)
    mutated = _insert_linebreaks(mutated, rng, opts.insert_linebreak_prob)
    mutated = random_eol_mix(mutated, rng, opts.eol_style)
    return mutated


def variants(text: str, *, base_seed: int, opts: FuzzOptions) -> Iterable[str]:
    """Yield deterministic fuzzed variants of ``text``."""

    for i in range(opts.max_variants):
        yield mutate_text(text, seed=base_seed + i, opts=opts)


__all__ = [
    "FuzzOptions",
    "rng_from_seed",
    "mutate_text",
    "variants",
    "swap_quotes",
    "vary_alias_labeling",
    "vary_dob_labeling",
    "break_token_with_hyphen",
    "random_eol_mix",
]

# End of module.
