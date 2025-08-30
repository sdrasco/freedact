"""Safe, deterministic text normalization.

The :func:`normalize` function performs a sequence of conservative fixes that
are safe for legal text.  The goal is to standardize common Unicode quirks
while preserving layout and meaning.  An offset ``char_map`` is returned so
that downstream components can reconcile indices with the original text.

Rules
-----
The following transforms are applied in order:

1. **Unicode NFC** – canonical composition without changing compatibility
   forms.  This eliminates decomposed accents while avoiding width changes.
2. **Whitespace rationalization** – convert no‑break spaces to a regular space
   and drop zero‑width characters.  Tabs and runs of spaces are left intact.
3. **Quote normalization** – curly quotes and apostrophes become straight
   ASCII quotes.
4. **Soft hyphen removal** – ``\u00ad`` is deleted.
5. **De‑hyphenation of line wraps** – a trailing ``-`` followed by a newline
   and another ASCII letter is considered a line‑wrap artifact and replaced
   with just the two letters.  All other hyphens are preserved.

All other characters, including existing newlines and multiple spaces, are kept
verbatim.  The function is pure and performs no I/O.

``char_map`` contract
---------------------
``char_map`` is a tuple where ``char_map[i]`` gives the index of the source
character that produced ``text[i]``.  Indices are strictly increasing.  The
mapping allows later stages to translate spans from normalized text back to the
original input.

Example
-------

>>> normalize("A\u00a0B")
NormalizationResult(text='A B', char_map=(0, 2, 3), changed=True)

Here the no‑break space at index 1 becomes a normal space at index 1 in the
output.  The character ``'B'`` in the normalized text originated from index ``2``
of the input.
"""

from __future__ import annotations

import string
import unicodedata
from dataclasses import dataclass
from typing import List, Tuple

_NBSP_EQUIVALENTS = {
    "\u00a0",  # NO-BREAK SPACE
    "\u202f",  # NARROW NO-BREAK SPACE
    "\u2007",  # FIGURE SPACE
}

# Zero-width characters which should be removed entirely.  We treat the common
# zero-width space (\u200B) the same way; this avoids accidental joins while
# keeping the contract simple.
_ZERO_WIDTHS = {
    "\u200b",  # ZERO WIDTH SPACE
    "\u200c",  # ZERO WIDTH NON-JOINER
    "\u200d",  # ZERO WIDTH JOINER
    "\ufeff",  # ZERO WIDTH NO-BREAK SPACE
}

_QUOTE_MAP = {
    "\u201c": '"',
    "\u201d": '"',
    "\u2018": "'",
    "\u2019": "'",
}


@dataclass(slots=True, frozen=True)
class NormalizationResult:
    """Result of :func:`normalize`.

    Attributes
    ----------
    text:
        The normalized text.
    char_map:
        ``char_map[i]`` gives the index in the original input that produced
        ``text[i]``.  The mapping is strictly increasing.
    changed:
        ``True`` if the normalized text differs from the input.
    """

    text: str
    char_map: Tuple[int, ...]
    changed: bool


def _nfc_with_map(text: str) -> tuple[List[str], List[int]]:
    """Normalize ``text`` to NFC while building an offset map.

    The algorithm groups a base character together with any following combining
    marks, normalizes the group with :func:`unicodedata.normalize`, and assigns
    the starting index of the group to all produced characters.  This mirrors
    user-perceived characters and keeps the mapping strictly increasing.
    """

    out_chars: List[str] = []
    out_map: List[int] = []
    i = 0
    while i < len(text):
        start = i
        cluster = [text[i]]
        i += 1
        while i < len(text) and unicodedata.combining(text[i]):
            cluster.append(text[i])
            i += 1
        normalized = unicodedata.normalize("NFC", "".join(cluster))
        for ch in normalized:
            out_chars.append(ch)
            out_map.append(start)
    return out_chars, out_map


def normalize(text: str) -> NormalizationResult:
    """Normalize ``text`` and return a :class:`NormalizationResult`.

    The function is deterministic and applies the rules documented at the
    module level.  Line breaks are preserved except when consumed by
    de‑hyphenation.
    """

    chars, mapping = _nfc_with_map(text)

    # Pass 2: whitespace and quote normalization, soft hyphen removal.
    tmp_chars: List[str] = []
    tmp_map: List[int] = []
    for ch, idx in zip(chars, mapping, strict=False):
        if ch in _ZERO_WIDTHS:
            # Drop zero-width characters entirely.
            continue
        if ch in _NBSP_EQUIVALENTS:
            tmp_chars.append(" ")
            tmp_map.append(idx)
            continue
        if ch in _QUOTE_MAP:
            tmp_chars.append(_QUOTE_MAP[ch])
            tmp_map.append(idx)
            continue
        if ch == "\u00ad":  # soft hyphen
            continue
        tmp_chars.append(ch)
        tmp_map.append(idx)

    # Pass 3: de-hyphenate wrapped lines.
    final_chars: List[str] = []
    final_map: List[int] = []
    i = 0
    while i < len(tmp_chars):
        ch = tmp_chars[i]
        if ch in string.ascii_letters and i + 3 <= len(tmp_chars) and tmp_chars[i + 1] == "-":
            # Determine newline sequence length (\n or \r\n).
            newline_len = 0
            next_letter_idx = i + 3
            if i + 3 < len(tmp_chars) and tmp_chars[i + 2] == "\r" and tmp_chars[i + 3] == "\n":
                newline_len = 2
                next_letter_idx = i + 4
            elif tmp_chars[i + 2] == "\n":
                newline_len = 1
                next_letter_idx = i + 3

            if (
                newline_len
                and next_letter_idx < len(tmp_chars)
                and tmp_chars[next_letter_idx] in string.ascii_letters
            ):
                # Copy the surrounding letters and skip hyphen + newline.
                final_chars.append(ch)
                final_map.append(tmp_map[i])
                final_chars.append(tmp_chars[next_letter_idx])
                final_map.append(tmp_map[next_letter_idx])
                i = next_letter_idx + 1
                continue

        final_chars.append(ch)
        final_map.append(tmp_map[i])
        i += 1

    normalized_text = "".join(final_chars)
    changed = normalized_text != text
    return NormalizationResult(normalized_text, tuple(final_map), changed)


__all__ = ["NormalizationResult", "normalize"]
