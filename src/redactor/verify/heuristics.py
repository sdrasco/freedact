"""Lightweight helpers for verification scanning.

This module provides pure functions used by the verification scanner to
apply policy and synthetic‑safe ignore rules.  They avoid heavy imports so
that the verification step remains fast and dependency free.

The helpers cover:
    * identifying e‑mail domains and phone numbers that are considered
      inherently safe (e.g. ``example.org`` or ``+1555`` test numbers);
    * building multisets of replacement strings from an applied plan so
      detected spans matching our own replacements can be ignored; and
    * providing the label weight mapping used for leakage scoring.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Iterable

from redactor.config import ConfigModel
from redactor.detect.base import EntityLabel
from redactor.replace.plan_builder import PlanEntry

__all__ = [
    "is_safe_email_domain",
    "is_safe_phone_string",
    "build_replacement_multiset_by_label",
    "weight_map",
]


_SAFE_EMAIL_DOMAINS = {"example.org", "example.com", "example.net"}


def is_safe_email_domain(domain: str) -> bool:
    """Return ``True`` if ``domain`` is on the allow list.

    The redaction pipeline generates synthetic email addresses using the
    ``example.*`` domains.  Any match within these domains is treated as safe
    and ignored by the verification scanner.
    """

    return domain.lower() in _SAFE_EMAIL_DOMAINS


_SAFE_PHONE_RE = re.compile(r"^\+1555\d{7}$")


def is_safe_phone_string(s: str) -> bool:
    """Return ``True`` if ``s`` is a known safe test phone number."""

    return bool(_SAFE_PHONE_RE.match(s))


def build_replacement_multiset_by_label(
    applied_plan: Iterable[PlanEntry] | None,
) -> dict[EntityLabel, Counter[str]]:
    """Return mapping of labels to Counters of replacement strings.

    ``applied_plan`` may contain multiple identical replacement strings for
    the same label.  Using :class:`collections.Counter` allows the scanner to
    ignore only as many detected matches as were actually produced during
    replacement, avoiding accidental over‑suppression of genuine residual
    data.
    """

    multiset: dict[EntityLabel, Counter[str]] = defaultdict(Counter)
    if applied_plan is None:
        return multiset
    for entry in applied_plan:
        multiset[entry.label][entry.replacement] += 1
    return multiset


_DEFAULT_WEIGHTS = {
    EntityLabel.PERSON: 3,
    EntityLabel.ADDRESS_BLOCK: 3,
    EntityLabel.DOB: 3,
    EntityLabel.EMAIL: 3,
    EntityLabel.ACCOUNT_ID: 3,
    EntityLabel.PHONE: 2,
    EntityLabel.BANK_ORG: 1,
    EntityLabel.ORG: 1,
    EntityLabel.ALIAS_LABEL: 1,
    EntityLabel.GPE: 1,
    EntityLabel.LOC: 1,
    EntityLabel.DATE_GENERIC: 1,  # adjusted below depending on policy
}


def weight_map(cfg: ConfigModel) -> dict[EntityLabel, int]:
    """Return entity weights adjusted for policy settings."""

    weights = dict(_DEFAULT_WEIGHTS)
    if not cfg.redact.generic_dates:
        weights[EntityLabel.DATE_GENERIC] = 0
    return weights
