"""Account and identifier detector using ``python-stdnum`` validators.

This module exposes :class:`AccountIdDetector` which finds common financial and
personal account numbers with high precision.  Detection proceeds in multiple
passes using subtype specific regular expressions followed by validator calls
from ``python-stdnum`` or the Luhn checksum.  The supported subtypes, in order
of precedence, are:

``iban`` -> ``swift_bic`` -> ``routing_aba`` -> ``cc`` -> ``ssn`` -> ``ein`` -> ``generic``

For each candidate the detector trims trailing punctuation such as ``.,)`` and
emits an :class:`~redactor.detect.base.EntitySpan` with label
:class:`~redactor.detect.base.EntityLabel.ACCOUNT_ID`.  Spans carry attributes
including ``subtype``, normalised and display representations and where
applicable issuer or scheme information.  Overlapping spans are resolved by the
above precedence order to avoid duplicate reporting.  Heuristics are applied to
avoid false positives; for instance ABA routing numbers require nearby context
keywords and generic account numbers only match when anchored by explicit
keywords.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, List, cast

from stdnum import bic, iban, luhn
from stdnum.us import ein as us_ein
from stdnum.us import ssn as us_ssn

try:
    from stdnum.us import routing_number  # type: ignore[attr-defined]
except Exception:  # pragma: no cover - missing module
    routing_number = cast(Any, None)

from ..utils.constants import RIGHT_TRIM
from .base import DetectionContext, EntityLabel, EntitySpan

__all__ = ["AccountIdDetector", "get_detector"]

# Regular expressions for each subtype -------------------------------------------------------
IBAN_RX: re.Pattern[str] = re.compile(
    r"\b([A-Z]{2}[0-9]{2}(?:[ ]?[A-Z0-9]{1,4}){2,})\b", re.IGNORECASE
)
SWIFT_BIC_RX: re.Pattern[str] = re.compile(
    r"\b([A-Za-z]{4}[A-Za-z]{2}[A-Za-z0-9]{2}(?:[A-Za-z0-9]{3})?)\b"
)
ABA_RX: re.Pattern[str] = re.compile(r"\b([0-9]{9})\b")
CC_RX: re.Pattern[str] = re.compile(r"\b((?:\d[ -]?){13,19})\b")
SSN_RX: re.Pattern[str] = re.compile(r"\b(\d{3}-\d{2}-\d{4}|\d{9})\b")
EIN_RX: re.Pattern[str] = re.compile(r"\b(\d{2}-\d{7})\b")
GENERIC_HINT_RX: re.Pattern[str] = re.compile(
    (
        r"\b(?:[A-Za-z]?(?:acct|account|a/c|iban|iban:|iban#|acct#|account#|sort\scode|ref|reference)"
        r"[:\s#]+([A-Za-z0-9][A-Za-z0-9 -]{4,}))"
    ),
    re.IGNORECASE,
)

# Keyword context for routing numbers -------------------------------------------------------
_ROUTING_KEYWORDS = ("routing number", "routing", "aba")

# Card scheme prefixes ---------------------------------------------------------------------
_SCHEME_PATTERNS = {
    "visa": re.compile(r"^4"),
    "mastercard": re.compile(r"^(5[1-5]|222[1-9]|22[3-9]\d|2[3-6]\d{2}|27[01]\d|2720)"),
    "amex": re.compile(r"^3[47]"),
    "discover": re.compile(r"^(6011|65|64[4-9])"),
    "jcb": re.compile(r"^35"),
    "diners": re.compile(r"^(36|38)"),
}

# Ranking for overlap resolution -----------------------------------------------------------
_PRIORITY = {
    "iban": 7,
    "swift_bic": 6,
    "routing_aba": 5,
    "cc": 4,
    "ssn": 3,
    "ein": 2,
    "generic": 1,
}


@dataclass(slots=True)
class _Candidate:
    span: EntitySpan
    subtype: str


def _trim(text: str, start: int, end: int) -> tuple[int, str]:
    """Trim trailing punctuation and return new end and substring."""

    if end > start and text[end - 1] in RIGHT_TRIM:
        end -= 1
    return end, text[start:end]


def _is_valid_routing(num: str) -> bool:
    if routing_number is not None:
        try:
            return bool(routing_number.is_valid(num))
        except Exception:  # pragma: no cover - defensive
            return False
    if len(num) != 9 or not num.isdigit():
        return False
    digits = [int(d) for d in num]
    checksum = (
        3 * (digits[0] + digits[3] + digits[6])
        + 7 * (digits[1] + digits[4] + digits[7])
        + (digits[2] + digits[5] + digits[8])
    ) % 10
    return checksum == 0


class AccountIdDetector:
    """Detect various financial or identification numbers within text."""

    _confidence: float = 0.99

    def name(self) -> str:  # pragma: no cover - trivial
        return "account_ids"

    # ------------------------------------------------------------------
    def detect(self, text: str, context: DetectionContext | None = None) -> list[EntitySpan]:
        candidates: List[_Candidate] = []

        enable_generic = True
        if context and context.config is not None:
            try:
                from redactor.config import ConfigModel  # local import to avoid cycle

                cfg = cast(ConfigModel, context.config)
                enable_generic = cfg.detectors.account_ids.generic.enabled
            except Exception:
                pass

        # IBAN -----------------------------------------------------------------
        for match in IBAN_RX.finditer(text):
            start, end = match.span(1)
            end, raw = _trim(text, start, end)
            try:
                normalized = iban.compact(raw)
                if not iban.is_valid(normalized):
                    continue
            except Exception:  # pragma: no cover - defensive
                continue
            attrs = {
                "subtype": "iban",
                "normalized": normalized.upper(),
                "display": iban.format(normalized),
                "issuer_or_country": normalized[:2].upper(),
                "length": len(normalized),
            }
            span = EntitySpan(
                start,
                end,
                raw,
                EntityLabel.ACCOUNT_ID,
                self.name(),
                self._confidence,
                attrs,
            )
            candidates.append(_Candidate(span, "iban"))

        # SWIFT/BIC ------------------------------------------------------------
        for match in SWIFT_BIC_RX.finditer(text):
            start, end = match.span(1)
            if (start > 0 and text[start - 1].isalnum()) or (
                end < len(text) and text[end].isalnum()
            ):
                continue
            end, raw = _trim(text, start, end)
            candidate = raw.upper()
            if not bic.is_valid(candidate):
                continue
            attrs = {
                "subtype": "swift_bic",
                "normalized": candidate,
                "display": candidate,
                "issuer_or_country": candidate[4:6],
                "length": len(candidate),
            }
            span = EntitySpan(
                start,
                end,
                raw,
                EntityLabel.ACCOUNT_ID,
                self.name(),
                self._confidence,
                attrs,
            )
            candidates.append(_Candidate(span, "swift_bic"))

        # ABA routing numbers --------------------------------------------------
        for match in ABA_RX.finditer(text):
            start, end = match.span(1)
            line_start = text.rfind("\n", 0, start) + 1
            context_snippet = text[max(line_start, start - 40) : start].lower()
            if not any(keyword in context_snippet for keyword in _ROUTING_KEYWORDS):
                continue
            end, raw = _trim(text, start, end)
            if not _is_valid_routing(raw):
                continue
            attrs = {
                "subtype": "routing_aba",
                "normalized": raw,
                "display": raw,
                "issuer_or_country": "US",
                "length": len(raw),
            }
            span = EntitySpan(
                start,
                end,
                raw,
                EntityLabel.ACCOUNT_ID,
                self.name(),
                self._confidence,
                attrs,
            )
            candidates.append(_Candidate(span, "routing_aba"))

        # Credit/debit cards ---------------------------------------------------
        for match in CC_RX.finditer(text):
            start, end = match.span(1)
            end, raw = _trim(text, start, end)
            digits = re.sub(r"[ -]", "", raw)
            if not 13 <= len(digits) <= 19:
                continue
            if not luhn.is_valid(digits):
                continue
            scheme: str | None = None
            for name, pat in _SCHEME_PATTERNS.items():
                if pat.match(digits):
                    scheme = name
                    break
            if scheme is None:
                continue
            display = " ".join(re.findall(".{1,4}", digits))
            attrs = {
                "subtype": "cc",
                "normalized": digits,
                "display": display,
                "scheme": scheme,
                "length": len(digits),
            }
            span = EntitySpan(
                start,
                end,
                raw,
                EntityLabel.ACCOUNT_ID,
                self.name(),
                self._confidence,
                attrs,
            )
            candidates.append(_Candidate(span, "cc"))

        # SSN ------------------------------------------------------------------
        for match in SSN_RX.finditer(text):
            start, end = match.span(1)
            if "§" in text[max(0, start - 3) : start]:
                continue
            end, raw = _trim(text, start, end)
            digits = raw.replace("-", "")
            if not us_ssn.is_valid(digits):
                continue
            display = f"{digits[:3]}-{digits[3:5]}-{digits[5:]}"
            attrs = {
                "subtype": "ssn",
                "normalized": digits,
                "display": display,
                "issuer_or_country": "US",
                "length": len(digits),
            }
            span = EntitySpan(
                start,
                end,
                raw,
                EntityLabel.ACCOUNT_ID,
                self.name(),
                self._confidence,
                attrs,
            )
            candidates.append(_Candidate(span, "ssn"))

        # EIN ------------------------------------------------------------------
        for match in EIN_RX.finditer(text):
            start, end = match.span(1)
            end, raw = _trim(text, start, end)
            digits = raw.replace("-", "")
            if not us_ein.is_valid(digits):
                continue
            display = f"{digits[:2]}-{digits[2:]}"
            attrs = {
                "subtype": "ein",
                "normalized": digits,
                "display": display,
                "issuer_or_country": "US",
                "length": len(digits),
            }
            span = EntitySpan(
                start,
                end,
                raw,
                EntityLabel.ACCOUNT_ID,
                self.name(),
                self._confidence,
                attrs,
            )
            candidates.append(_Candidate(span, "ein"))

        # Generic account numbers ----------------------------------------------
        if enable_generic:
            for match in GENERIC_HINT_RX.finditer(text):
                start, end = match.span(1)
                end, raw = _trim(text, start, end)
                compact = re.sub(r"[ -]", "", raw).upper()
                digit_count = sum(1 for c in compact if c.isdigit())
                if digit_count < 6 or len(compact) > 34:
                    continue
                attrs = {
                    "subtype": "generic",
                    "normalized": compact,
                    "display": raw,
                    "length": len(compact),
                }
                span = EntitySpan(
                    start,
                    end,
                    raw,
                    EntityLabel.ACCOUNT_ID,
                    self.name(),
                    0.9,
                    attrs,
                )
                candidates.append(_Candidate(span, "generic"))

        # Overlap resolution ---------------------------------------------------
        sorted_cands = sorted(
            candidates, key=lambda c: (-_PRIORITY.get(c.subtype, 0), c.span.start, c.span.end)
        )
        final: list[EntitySpan] = []
        for cand in sorted_cands:
            if any(not (cand.span.end <= ex.start or cand.span.start >= ex.end) for ex in final):
                continue
            final.append(cand.span)
        return sorted(final, key=lambda s: s.start)


def get_detector() -> AccountIdDetector:
    """Return an :class:`AccountIdDetector` instance."""

    return AccountIdDetector()
