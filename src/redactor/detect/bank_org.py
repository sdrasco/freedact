"""High‑precision detector for bank and financial organisation names.

This module implements :class:`BankOrgDetector` which targets explicit
financial institution phrases such as "Credit Union", "Trust Company",
"Bank & Trust", and corporate suffixes like "Bank, N.A.".  The detector
favours high precision:  it relies on conservative regular expressions that
expect capitalised tokens and well known business suffixes.  Generic phrases
such as "food bank" or "bank account" are excluded by rule.  After a raw
match is found the detector trims trailing punctuation on the right but keeps
leading punctuation (e.g. "(Bank of Foo)" → "Bank of Foo").

Overlapping spans are resolved by keeping the longest match; when equal in
length higher confidence wins, and remaining ties are broken by detector
kind (``credit_union`` ≻ ``trust_company`` ≻ ``bank_and_trust`` ≻
``bank_of`` ≻ ``token_bank_suffix`` ≻ ``bank``).  NER based augmentation for
financial institutions without an explicit keyword (e.g. "Morgan Stanley")
may be added in a future iteration.
"""

from __future__ import annotations

import re
from typing import Iterable

from ..utils.constants import RIGHT_TRIM
from .base import DetectionContext, EntityLabel, EntitySpan

__all__ = ["BankOrgDetector", "get_detector"]

# ---------------------------------------------------------------------------
# Patterns and constants
# ---------------------------------------------------------------------------

_EXCLUDED_PRECEDING = {"Food", "Blood", "Sperm", "Milk", "Energy", "Data"}
_AFTER_BANK_KEYWORDS = {"account", "accounts", "holiday"}

_SUFFIX_PART = r"N\.??\s?A\.??|National\s+Association|PLC|plc|N\.??\s?V\.??|LLC|Ltd\.??|Limited|USA"

RX_CREDIT_UNION: re.Pattern[str] = re.compile(
    r"""
    \b([A-Z][\w&.'-]*(?:\s+[A-Z][\w&.'-]*)*)\s+Credit\s+Union\b
    """,
    re.VERBOSE,
)

RX_TRUST_CO: re.Pattern[str] = re.compile(
    r"""
    \b([A-Z][\w&.'-]*(?:\s+[A-Z][\w&.'-]*)*)\s+Trust\s+Company\b
    """,
    re.VERBOSE,
)

RX_BANK_AND_TRUST: re.Pattern[str] = re.compile(
    r"""
    \b([A-Z][\w&.'-]*(?:\s+[A-Z][\w&.'-]*)*)\s+
    (?:Bank\s&\s*Trust|Bank\s+and\s+Trust)(?:\s+Company)?\b
    """,
    re.VERBOSE,
)

# ``Bank of …`` – allows optional tokens before ``Bank`` and an optional
# corporate suffix following the institution name.
RX_BANK_OF: re.Pattern[str] = re.compile(
    rf"""
    \b(?:[A-Z][\w&.'-]*(?:\s+[A-Z][\w&.'-]*)*\s+)?
    Bank\s+of\s+[A-Z][\w&.'-]*(?:\s+[A-Z][\w&.'-]*)*
    (?:\s*(?:,\s*|\s+)(?P<suffix>{_SUFFIX_PART}))?(?=[^\w]|$)
    """,
    re.VERBOSE,
)

# Plain "… Bank" with optional corporate suffix.
RX_PLAIN_BANK: re.Pattern[str] = re.compile(
    rf"""
    \b([A-Z][\w&.'-]*(?:\s+[A-Z][\w&.'-]*)*)\s+Bank
    (?: (?:,\s*|\s+)(?P<suffix>{_SUFFIX_PART}))?(?=[^\w]|$)
    """,
    re.VERBOSE,
)

# Single token ending with "bank" followed by NA/National Association.
RX_BANK_SUFFIX: re.Pattern[str] = re.compile(
    r"""
    \b([A-Z][A-Za-z0-9&.'-]*bank)\b(?:,\s)?(?P<suffix>N\.??\s?A\.??|National\s+Association)(?=[^\w]|$)
    """,
    re.VERBOSE,
)

_KIND_ORDER = {
    "credit_union": 0,
    "trust_company": 1,
    "bank_and_trust": 2,
    "bank_of": 3,
    "token_bank_suffix": 4,
    "bank": 5,
}

_HIGH_CONF_SUFFIXES = {"na", "national_association", "plc", "nv"}

_SUFFIX_KEEP_PERIOD = {"N.A.", "N.V.", "Inc.", "Corp.", "Co.", "Ltd.", "S.A."}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalize_suffix(raw: str | None) -> tuple[str | None, bool]:
    """Return normalised suffix and ``has_na`` flag."""

    if not raw:
        return None, False
    cleaned = raw.lower().replace(".", "").replace(" ", "")
    if cleaned == "na":
        return "na", True
    if cleaned == "nationalassociation":
        return "national_association", True
    if cleaned == "plc":
        return "plc", False
    if cleaned == "nv":
        return "nv", False
    if cleaned == "llc":
        return "llc", False
    if cleaned == "ltd":
        return "ltd", False
    if cleaned == "limited":
        return "limited", False
    if cleaned == "usa":
        return "usa", False
    return None, False


def _is_mostly_lower(text: str) -> bool:
    """Return ``True`` if ``text`` is entirely or mostly lowercase."""

    if not text:
        return True
    if text == text.lower():
        return True
    tokens = re.findall(r"[A-Za-z][\w&.'-]*", text)
    if not tokens:
        return True
    title_count = sum(token[0].isupper() for token in tokens)
    return bool(title_count < len(tokens) / 2)


def _preceding_word(full_text: str, start: int, match_text: str) -> str | None:
    """Return the word immediately preceding ``Bank`` within the match."""

    rel = match_text.find("Bank")
    if rel == -1:
        return None
    prefix = match_text[:rel].rstrip()
    tokens = prefix.split()
    return tokens[-1] if tokens else None


def _after_bank_contains(full_text: str, bank_end: int) -> bool:
    """Return ``True`` if keywords appear within two words after ``bank_end``."""

    after = full_text[bank_end:]
    # Trim leading whitespace and punctuation
    i = 0
    while i < len(after) and not after[i].isalnum():
        i += 1
    after = after[i:]
    tokens = re.split(r"\W+", after)
    tokens = [t for t in tokens if t]
    for tok in tokens[:2]:
        if tok.lower() in _AFTER_BANK_KEYWORDS:
            return True
    return False


# ---------------------------------------------------------------------------
# Detector implementation
# ---------------------------------------------------------------------------


class BankOrgDetector:
    """Detect bank or financial organisation names."""

    def name(self) -> str:  # pragma: no cover - trivial
        return "bank_org"

    def detect(self, text: str, context: DetectionContext | None = None) -> list[EntitySpan]:
        """Detect bank organisations in ``text``."""

        candidates: list[EntitySpan] = []

        def handle_matches(matches: Iterable[re.Match[str]], kind: str, hint: str) -> None:
            for m in matches:
                start, end = m.span()
                suffix_raw = m.groupdict().get("suffix")
                if suffix_raw and end < len(text) and text[end] == ".":
                    end += 1
                span_text = text[start:end]

                if span_text.startswith("("):
                    start += 1
                    span_text = text[start:end]
                if span_text.endswith(")"):
                    end -= 1
                    span_text = text[start:end]

                keep_suffix_dot = any(span_text.endswith(sfx) for sfx in _SUFFIX_KEEP_PERIOD)
                if (
                    span_text
                    and span_text[-1] in RIGHT_TRIM
                    and not (keep_suffix_dot and span_text[-1] == ".")
                ):
                    end -= 1
                    span_text = text[start:end]

                # Exclusion heuristics for patterns containing the word "Bank".
                if "Bank" in span_text:
                    prev = _preceding_word(text, start, span_text)
                    if prev in _EXCLUDED_PRECEDING:
                        continue
                    bank_idx = span_text.index("Bank")
                    bank_end = start + bank_idx + len("Bank")
                    if _after_bank_contains(text, bank_end):
                        continue

                if _is_mostly_lower(span_text):
                    continue

                suffix, has_na = _normalize_suffix(suffix_raw)
                normalized = " ".join(span_text.split()).lower()

                if kind in {"credit_union", "trust_company", "bank_and_trust"}:
                    conf = 0.96
                elif suffix in _HIGH_CONF_SUFFIXES:
                    conf = 0.98
                else:
                    conf = 0.93

                attrs: dict[str, object] = {
                    "normalized": normalized,
                    "kind": kind,
                    "suffix": suffix,
                    "has_na": has_na,
                    "source_hint": hint,
                }

                candidates.append(
                    EntitySpan(
                        start,
                        end,
                        span_text,
                        EntityLabel.BANK_ORG,
                        "bank_org",
                        conf,
                        attrs,
                    )
                )

        handle_matches(RX_CREDIT_UNION.finditer(text), "credit_union", "rx_credit_union")
        handle_matches(RX_TRUST_CO.finditer(text), "trust_company", "rx_trust_company")
        handle_matches(RX_BANK_AND_TRUST.finditer(text), "bank_and_trust", "rx_bank_and_trust")
        handle_matches(RX_BANK_OF.finditer(text), "bank_of", "rx_bank_of")
        handle_matches(RX_PLAIN_BANK.finditer(text), "bank", "rx_bank")
        handle_matches(RX_BANK_SUFFIX.finditer(text), "token_bank_suffix", "rx_token_bank_suffix")

        # Resolve overlaps and duplicates
        candidates.sort(key=lambda s: (s.start, s.end))
        resolved: list[EntitySpan] = []
        for span in candidates:
            if resolved and not (span.start >= resolved[-1].end or span.end <= resolved[-1].start):
                existing = resolved[-1]
                replace = False
                if span.length > existing.length:
                    replace = True
                elif span.length == existing.length:
                    if span.confidence > existing.confidence:
                        replace = True
                    elif span.confidence == existing.confidence:
                        if (
                            _KIND_ORDER[str(span.attrs["kind"])]
                            < _KIND_ORDER[str(existing.attrs["kind"])]
                        ):
                            replace = True
                if replace:
                    resolved[-1] = span
            elif resolved and span.start == resolved[-1].start and span.end == resolved[-1].end:
                # Exact duplicate range, prefer higher confidence then kind order
                existing = resolved[-1]
                replace = False
                if span.confidence > existing.confidence:
                    replace = True
                elif (
                    span.confidence == existing.confidence
                    and _KIND_ORDER[str(span.attrs["kind"])]
                    < _KIND_ORDER[str(existing.attrs["kind"])]
                ):
                    replace = True
                if replace:
                    resolved[-1] = span
            else:
                resolved.append(span)

        return resolved


def get_detector() -> BankOrgDetector:
    """Return a :class:`BankOrgDetector` instance."""

    return BankOrgDetector()
