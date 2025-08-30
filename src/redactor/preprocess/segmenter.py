"""Lightweight sentence segmentation.

The :func:`segment_sentences` helper performs conservative sentence splitting
that works reasonably well for legal documents.  It relies solely on regular
expressions and a short list of abbreviations to avoid false breaks.

The function expects already normalized text and returns ``SentenceSpan``
objects whose ``start`` and ``end`` indices refer to the original string using
half‑open ``[start, end)`` conventions.  The span text is returned for
convenience.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

_ABBREVIATIONS = {
    "Mr.",
    "Ms.",
    "Mrs.",
    "Dr.",
    "St.",
    "No.",
    "Art.",
    "Sec.",
    "Ex.",
    "Fig.",
    "Inc.",
    "Co.",
    "Ltd.",
    "Jr.",
    "Sr.",
    "U.S.",
    "Jan.",
    "Feb.",
    "Mar.",
    "Apr.",
    "Jun.",
    "Jul.",
    "Aug.",
    "Sep.",
    "Sept.",
    "Oct.",
    "Nov.",
    "Dec.",
}


_TERMINATOR_RE = re.compile(r"[.!?][\"')\]]*")
_STRIP_CHARS = "\"')]"


@dataclass(slots=True, frozen=True)
class SentenceSpan:
    """A single sentence span using half‑open offsets."""

    start: int
    end: int
    text: str


def _preceding_token(text: str, end: int) -> str:
    """Return the token (word + punctuation) ending at ``end``.

    The token is used for abbreviation checks.  Surrounding quotes or closing
    brackets are stripped.
    """

    start = (
        max(
            text.rfind(" ", 0, end),
            text.rfind("\n", 0, end),
            text.rfind("\t", 0, end),
            text.rfind("\r", 0, end),
        )
        + 1
    )
    token = text[start:end]
    return token.strip(_STRIP_CHARS)


def segment_sentences(text: str) -> List[SentenceSpan]:
    """Split ``text`` into sentences.

    Splits occur on ``[.!?]`` possibly followed by closing quotes or brackets
    when the punctuation is followed by whitespace/newlines and then an
    upper‑case letter starting the next sentence.  Tokens listed in
    ``_ABBREVIATIONS`` are protected from splitting.
    """

    spans: List[SentenceSpan] = []
    start = 0
    for match in _TERMINATOR_RE.finditer(text):
        end = match.end()
        after = text[end:]
        m = re.match(r"\s+([A-Z])", after)
        if not m:
            continue

        token = _preceding_token(text, end)
        if token in _ABBREVIATIONS:
            continue

        spans.append(SentenceSpan(start, end, text[start:end]))
        gap = m.start(1)
        start = end + gap

    if start < len(text):
        spans.append(SentenceSpan(start, len(text), text[start:]))
    return spans


__all__ = ["SentenceSpan", "segment_sentences"]
