"""Strict email address detector.

This module provides :class:`EmailDetector`, a high‑precision detector for
email addresses inspired by RFC5322.  It focuses on accuracy and avoids false
positives by using a conservative regular expression and additional
post‑validation.  After a raw regex match, the detector trims trailing
punctuation that is commonly adjacent to emails in prose and validates domain
and local parts.  Attributes such as the local part, domain, tag, and top‑level
 domain are exposed for downstream components.

Notably, IP‑literal domains (e.g. ``user@[1.2.3.4]``) are intentionally
excluded in favour of precision.
"""

from __future__ import annotations

import re

from ..utils.constants import rtrim_index
from .base import DetectionContext, EntityLabel, EntitySpan

__all__ = ["EmailDetector", "get_detector"]

# ---------------------------------------------------------------------------
# Regular expression
# ---------------------------------------------------------------------------
# The pattern is intentionally conservative and only matches dot‑atom or quoted
# locals with domain names composed of labels and a terminal alphabetic TLD.
LOCAL_ATOM = r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+"
LOCAL_DOT_ATOM = rf"{LOCAL_ATOM}(?:\.{LOCAL_ATOM})*"
LOCAL_QUOTED = r'"(?:[^"\\\r\n]|\\.)+"'
LOCAL_PART = rf"(?:{LOCAL_DOT_ATOM}|{LOCAL_QUOTED})"

DOMAIN_LABEL = r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
TLD = r"[A-Za-z]{2,63}"
DOMAIN = rf"(?:{DOMAIN_LABEL}\.)+{TLD}"

EMAIL_RX: re.Pattern[str] = re.compile(
    rf"""
    (?<![A-Za-z0-9!#$%&'*+/=?^_`{{|}}~.-])   # ensure preceding boundary
    ({LOCAL_PART}@{DOMAIN})
    (?=[^A-Za-z0-9-]|$)                     # ensure following boundary
    """,
    re.VERBOSE | re.IGNORECASE,
)


def _has_consecutive_dots(value: str) -> bool:
    return ".." in value


def _validate_local(local: str) -> bool:
    if local.startswith('"') and local.endswith('"'):
        return True
    if local.startswith(".") or local.endswith("."):
        return False
    if _has_consecutive_dots(local):
        return False
    return True


def _validate_domain(domain: str) -> bool:
    if _has_consecutive_dots(domain):
        return False
    labels = domain.split(".")
    if len(labels) < 2:
        return False
    tld = labels[-1]
    if not tld.isalpha() or not (2 <= len(tld) <= 63):
        return False
    for label in labels:
        if not label or label.startswith("-") or label.endswith("-"):
            return False
    return True


class EmailDetector:
    """Detect email addresses within text."""

    _confidence: float = 0.99

    def name(self) -> str:  # pragma: no cover - trivial
        return "email"

    def detect(self, text: str, context: DetectionContext | None = None) -> list[EntitySpan]:
        """Detect email addresses in ``text``."""

        _ = context
        spans: list[EntitySpan] = []
        for match in EMAIL_RX.finditer(text):
            start, end = match.span(1)
            end = rtrim_index(text, end)
            email_text = text[start:end]

            local, domain = email_text.rsplit("@", 1)
            if not (_validate_local(local) and _validate_domain(domain)):
                continue

            domain_lower = domain.lower()
            is_quoted = local.startswith('"') and local.endswith('"')
            if not is_quoted and "+" in local:
                base_local, tag = local.split("+", 1)
            else:
                base_local, tag = local, None

            tld = domain_lower.rsplit(".", 1)[1]
            attrs: dict[str, object] = {
                "local": local,
                "domain": domain_lower,
                "normalized": f"{local}@{domain_lower}",
                "base_local": base_local,
                "tag": tag,
                "is_quoted_local": is_quoted,
                "tld": tld,
            }
            spans.append(
                EntitySpan(
                    start,
                    end,
                    email_text,
                    EntityLabel.EMAIL,
                    "email",
                    self._confidence,
                    attrs,
                )
            )

        # De‑duplicate spans by [start, end)
        unique: dict[tuple[int, int], EntitySpan] = {}
        for span in spans:
            key = (span.start, span.end)
            if key not in unique:
                unique[key] = span
        return sorted(unique.values(), key=lambda s: s.start)


def get_detector() -> EmailDetector:
    """Return an :class:`EmailDetector` instance."""

    return EmailDetector()
