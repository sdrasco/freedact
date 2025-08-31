"""Numeric identifier pseudonymization helpers.

This module provides generators for various number-like identifiers such as
credit card numbers, routing numbers and government IDs.  The generators follow
simple structure-preserving rules and rely on deterministic randomness from
``PseudonymGenerator.rng``.  The goal is not to produce valid identifiers but
to maintain the visible shape so that downstream processing sees a plausible
value.

Most helpers merely replace digits while keeping separators.  Some implement
lightweight checksum logic such as the Luhn algorithm for credit cards or the
ABA checksum for routing numbers.  :func:`redactor.pseudo.case_preserver.format_like`
is used where appropriate to mirror punctuation.
"""

from __future__ import annotations

import random
import re
import string
from typing import TYPE_CHECKING, List

from .case_preserver import format_like

if TYPE_CHECKING:  # pragma: no cover
    from .generator import PseudonymGenerator


def _normalize(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z]", "", text)


# ---------------------------------------------------------------------------
# Credit card numbers


def _luhn_checksum(num: str) -> int:
    total = 0
    reverse = list(map(int, num[::-1]))
    for idx, digit in enumerate(reverse):
        if idx % 2 == 1:
            doubled = digit * 2
            total += doubled - 9 if doubled > 9 else doubled
        else:
            total += digit
    return total % 10


def _luhn_complete(prefix: str) -> str:
    check = (10 - _luhn_checksum(prefix + "0")) % 10
    return prefix + str(check)


def generate_cc_like(source_digits: str, *, key: str, gen: PseudonymGenerator) -> str:
    """Generate a Luhn-valid credit card number shaped like ``source_digits``."""

    digits = _normalize(source_digits)
    seps = [(i, ch) for i, ch in enumerate(source_digits) if not ch.isdigit()]

    length = len(digits)
    rng = gen.rng("ACCOUNT_CC", key)

    def build(r: random.Random) -> str:
        network = "visa"
        if digits.startswith("5"):
            network = "mc"
        elif digits.startswith("34") or digits.startswith("37"):
            network = "amex"
        elif digits.startswith("6"):
            network = "disc"
        if network == "visa":
            prefix = "444000"
        elif network == "mc":
            prefix = "555000"
        elif network == "amex":
            prefix = "343000"
        else:
            prefix = "601100"
        body_len = max(0, length - len(prefix) - 1)
        body = "".join(str(r.randint(0, 9)) for _ in range(body_len))
        return _luhn_complete(prefix[: length - 1 - len(body)] + body)

    candidate = build(rng)
    for salt in range(1, 5):
        if candidate != digits:
            break
        rng = gen.rng("ACCOUNT_CC", f"{key}:{salt}")
        candidate = build(rng)

    out = list(candidate)
    for pos, ch in seps:
        out.insert(pos, ch)
    return "".join(out)


# ---------------------------------------------------------------------------
# Generic digits


def generate_generic_digits_like(
    source: str, *, key: str, gen: PseudonymGenerator, min_len: int = 6
) -> str:
    """Replace digits in ``source`` with deterministic digits preserving separators."""

    rng = gen.rng("GENERIC_DIGITS", key)
    result: List[str] = []
    for ch in source:
        if ch.isdigit():
            result.append(str(rng.randint(0, 9)))
        else:
            result.append(ch)
    candidate = "".join(result)
    if _normalize(candidate) == _normalize(source):
        rng = gen.rng("GENERIC_DIGITS", f"{key}:1")
        result = []
        for ch in source:
            if ch.isdigit():
                result.append(str(rng.randint(0, 9)))
            else:
                result.append(ch)
        candidate = "".join(result)
    return candidate


# ---------------------------------------------------------------------------
# Routing numbers


def _aba_check_digit(eight: str) -> str:
    weights = [3, 7, 1] * 3
    total = sum(int(d) * w for d, w in zip(eight, weights, strict=False))
    return str((10 - total % 10) % 10)


def generate_routing_like(source9: str, *, key: str, gen: PseudonymGenerator) -> str:
    """Generate a 9-digit routing number with a valid ABA checksum."""

    digits = _normalize(source9)
    seps = [(i, ch) for i, ch in enumerate(source9) if not ch.isdigit()]

    rng = gen.rng("ACCOUNT_ROUTING", key)

    def build(r: random.Random) -> str:
        body = "".join(str(r.randint(0, 9)) for _ in range(8))
        return body + _aba_check_digit(body)

    candidate = build(rng)
    for salt in range(1, 5):
        if candidate != digits:
            break
        rng = gen.rng("ACCOUNT_ROUTING", f"{key}:{salt}")
        candidate = build(rng)

    out = list(candidate)
    for pos, ch in seps:
        out.insert(pos, ch)
    return "".join(out)


# ---------------------------------------------------------------------------
# IBAN


def _iban_check_digits(country: str, body: str) -> str:
    # Compute mod-97 check digits
    converted = body + country + "00"
    num = ""
    for ch in converted:
        if ch.isdigit():
            num += ch
        else:
            num += str(ord(ch.upper()) - 55)
    remainder = 0
    for ch in num:
        remainder = (remainder * 10 + int(ch)) % 97
    return f"{98 - remainder:02d}"


def generate_iban_like(source: str, *, key: str, gen: PseudonymGenerator) -> str:
    """Generate an IBAN-like number preserving country code and length."""

    clean = _normalize(source)
    country = clean[:2]
    length = len(clean)
    body_len = length - 4
    rng = gen.rng("ACCOUNT_IBAN", key)
    body = "".join(rng.choice(string.ascii_uppercase + string.digits) for _ in range(body_len))
    check = _iban_check_digits(country, body)
    candidate = country + check + body
    seps = [(i, ch) for i, ch in enumerate(source) if not ch.isalnum()]
    out = list(candidate)
    for pos, ch in seps:
        out.insert(pos, ch)
    return "".join(out)


# ---------------------------------------------------------------------------
# EIN and SSN


def generate_ein_like(source: str, *, key: str, gen: PseudonymGenerator) -> str:
    """Generate an Employer Identification Number shaped like ``source``."""

    rng = gen.rng("ACCOUNT_EIN", key)

    def build(r: random.Random) -> str:
        digits = "".join(str(r.randint(0, 9)) for _ in range(9))
        return f"{digits[:2]}-{digits[2:]}"

    candidate = build(rng)
    if candidate == source:
        rng = gen.rng("ACCOUNT_EIN", f"{key}:1")
        candidate = build(rng)
    return format_like(source, candidate, rng=rng)


def generate_ssn_like(source: str, *, key: str, gen: PseudonymGenerator) -> str:
    """Generate a US Social Security number with basic validity checks."""

    rng = gen.rng("ACCOUNT_SSN", key)

    def build(r: random.Random) -> str:
        while True:
            area = r.randint(1, 899)
            if area == 666:
                continue
            group = r.randint(1, 99)
            serial = r.randint(1, 9999)
            return f"{area:03d}-{group:02d}-{serial:04d}"

    candidate = build(rng)
    if candidate == source or candidate.startswith("9"):
        rng = gen.rng("ACCOUNT_SSN", f"{key}:1")
        candidate = build(rng)
    return format_like(source, candidate, rng=rng)


__all__ = [
    "generate_cc_like",
    "generate_generic_digits_like",
    "generate_routing_like",
    "generate_iban_like",
    "generate_ein_like",
    "generate_ssn_like",
]
