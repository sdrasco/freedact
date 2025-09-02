from __future__ import annotations

"""Email pseudonym helpers.

These helpers render deterministic placeholder emails while preserving the
visible shape of the local part.  Domains are always coerced to
``example.org`` to avoid accidentally generating a real address.
"""

from redactor.pseudo.generator import PseudonymGenerator

__all__ = ["generate_email_like"]


def generate_email_like(source: str, *, key: str, gen: PseudonymGenerator) -> str:
    """Return an email shaped like ``source`` using ``example.org`` domain."""

    local_src, _, _domain = source.partition("@")
    base, plus, tag = local_src.partition("+")
    length = len(base)
    token = gen.token("EMAIL", key, length=length or 1)
    safe_base = token[:length] if length else token
    local = safe_base
    if plus:
        local += "+" + tag
    return f"{local}@example.org"
