from __future__ import annotations

"""Numeric identifier pseudonym helpers."""

from redactor.pseudo import number_rules
from redactor.pseudo.generator import PseudonymGenerator

__all__ = [
    "generate_cc_like",
    "generate_generic_digits_like",
    "generate_routing_like",
    "generate_iban_like",
    "generate_ein_like",
    "generate_ssn_like",
]


def generate_cc_like(
    source: str, *, key: str, gen: PseudonymGenerator
) -> str:  # pragma: no cover - wrapper
    return number_rules.generate_cc_like(source, key=key, gen=gen)


def generate_generic_digits_like(
    source: str, *, key: str, gen: PseudonymGenerator
) -> str:  # pragma: no cover
    return number_rules.generate_generic_digits_like(source, key=key, gen=gen)


def generate_routing_like(
    source: str, *, key: str, gen: PseudonymGenerator
) -> str:  # pragma: no cover
    return number_rules.generate_routing_like(source, key=key, gen=gen)


def generate_iban_like(
    source: str, *, key: str, gen: PseudonymGenerator
) -> str:  # pragma: no cover
    return number_rules.generate_iban_like(source, key=key, gen=gen)


def generate_ein_like(source: str, *, key: str, gen: PseudonymGenerator) -> str:  # pragma: no cover
    return number_rules.generate_ein_like(source, key=key, gen=gen)


def generate_ssn_like(source: str, *, key: str, gen: PseudonymGenerator) -> str:  # pragma: no cover
    return number_rules.generate_ssn_like(source, key=key, gen=gen)
