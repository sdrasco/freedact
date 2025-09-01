"""High‑precision phone number detector using ``libphonenumbers``.

This module exposes :class:`PhoneDetector`, a detector that leverages
Google's `libphonenumbers <https://github.com/google/libphonenumber>`_
library to locate telephone numbers.  Candidates are produced via
``PhoneNumberMatcher`` with a strict leniency (``STRICT_GROUPING`` when
available, otherwise ``VALID``) to reduce false positives.  Detected
numbers are validated and enriched with a variety of normalised formats
such as E.164, national, and international representations.

After extraction the detector trims trailing punctuation characters that
are common in prose but not part of the phone number.  It purposely only
trims the right side so that leading parentheses belonging to the phone
remain intact.  Attributes on the resulting :class:`~redactor.detect.base.EntitySpan`
include ``e164``, ``national``, ``international``, ``country_code``,
``region_code``, ``significant`` digits, detected ``type``, ``extension``
if present and a flag indicating whether the original text contained a
leading ``+`` sign.

The detector does not attempt to resolve overlaps with other entity
types; downstream components (e.g. the span merger) are responsible for
that.  In the merge hierarchy phone numbers rank below emails, so an
overlapping email will take precedence.
"""

from __future__ import annotations

import re
from typing import cast

from phonenumbers import (
    SUPPORTED_REGIONS,
    Leniency,
    PhoneNumber,
    PhoneNumberFormat,
    PhoneNumberMatcher,
    PhoneNumberType,
    format_number,
    is_valid_number,
    national_significant_number,
    number_type,
    region_code_for_number,
)

from ..utils.constants import RIGHT_TRIM
from .base import DetectionContext, EntityLabel, EntitySpan

__all__ = ["PhoneDetector", "get_detector"]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NO_PREFIX_RX: re.Pattern[str] = re.compile(r"(?i)No\.\s*$")


def normalize_region(locale: str | None) -> str | None:
    """Return a best‑effort region code derived from ``locale``.

    The function uppercases the locale and validates it against
    ``phonenumbers.SUPPORTED_REGIONS``.  For composite locales such as
    ``en_US`` or ``en-US`` the portion after the separator is used.  Unknown
    locales yield ``None`` so that ``libphonenumbers`` may apply its own
    inference rules.
    """

    if not locale:
        return None
    candidate = locale.split("-")[-1].split("_")[-1].upper()
    return candidate if candidate in SUPPORTED_REGIONS else None


# Determine leniency and associated confidence score at import time.
_STRICT = getattr(Leniency, "STRICT_GROUPING", None)
_LENIENCY: int
if _STRICT is not None:
    _LENIENCY = int(cast(int, _STRICT))
    _CONFIDENCE = 0.99
else:
    _LENIENCY = int(Leniency.VALID)
    _CONFIDENCE = 0.98

_TYPE_MAP = {
    PhoneNumberType.FIXED_LINE: "fixed_line",
    PhoneNumberType.MOBILE: "mobile",
    PhoneNumberType.FIXED_LINE_OR_MOBILE: "fixed_line_or_mobile",
    PhoneNumberType.TOLL_FREE: "toll_free",
    PhoneNumberType.PREMIUM_RATE: "premium_rate",
    PhoneNumberType.SHARED_COST: "shared_cost",
    PhoneNumberType.VOIP: "voip",
    PhoneNumberType.PERSONAL_NUMBER: "personal_number",
    PhoneNumberType.PAGER: "pager",
    PhoneNumberType.UAN: "uan",
    PhoneNumberType.UNKNOWN: "unknown",
}


def _phone_type_name(num: PhoneNumber) -> str:
    """Return the lower‑case name of the phone number type."""

    t = number_type(num)
    return _TYPE_MAP.get(t, "unknown")


# ---------------------------------------------------------------------------
# Detector implementation
# ---------------------------------------------------------------------------


class PhoneDetector:
    """Detect phone numbers within text."""

    _confidence: float = _CONFIDENCE
    _leniency: int = _LENIENCY

    def name(self) -> str:  # pragma: no cover - trivial
        return "phone"

    def detect(self, text: str, context: DetectionContext | None = None) -> list[EntitySpan]:
        """Detect phone numbers in ``text``."""

        region = normalize_region(context.locale if context else "US") or "US"
        matcher = PhoneNumberMatcher(text, region, leniency=self._leniency)

        spans: list[EntitySpan] = []
        for match in matcher:
            start, end = match.start, match.end
            matched_text = text[start:end]

            # Skip obvious overlaps or legal section references.
            if "@" in matched_text:
                continue
            if "§" in matched_text or "§" in text[max(0, start - 2) : start]:
                continue
            if NO_PREFIX_RX.search(text[max(0, start - 5) : start]):
                continue

            num = match.number
            if not is_valid_number(num):
                continue

            if end > start and text[end - 1] in RIGHT_TRIM:
                end -= 1
            matched_text = text[start:end]

            attrs: dict[str, object] = {
                "e164": format_number(num, PhoneNumberFormat.E164),
                "national": format_number(num, PhoneNumberFormat.NATIONAL),
                "international": format_number(num, PhoneNumberFormat.INTERNATIONAL),
                "country_code": num.country_code,
                "region_code": region_code_for_number(num),
                "significant": national_significant_number(num),
                "type": _phone_type_name(num),
                "extension": num.extension or None,
                "had_plus": match.raw_string.strip().startswith("+"),
            }

            spans.append(
                EntitySpan(
                    start,
                    end,
                    matched_text,
                    EntityLabel.PHONE,
                    "phone",
                    self._confidence,
                    attrs,
                )
            )

        # De‑duplicate spans by [start, end).
        unique: dict[tuple[int, int], EntitySpan] = {}
        for span in spans:
            key = (span.start, span.end)
            if key not in unique:
                unique[key] = span
        return sorted(unique.values(), key=lambda s: s.start)


def get_detector() -> PhoneDetector:
    """Return a :class:`PhoneDetector` instance."""

    return PhoneDetector()
