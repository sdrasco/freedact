from __future__ import annotations

"""Phone number pseudonym helpers."""

import re
from redactor.pseudo.generator import PseudonymGenerator

__all__ = ["generate_phone_like"]


def _format_digits_like(source: str, digits: str) -> str:
    it = iter(digits)
    out: list[str] = []
    for ch in source:
        if ch.isdigit():
            out.append(next(it, "0"))
        else:
            out.append(ch)
    return "".join(out)


def generate_phone_like(source: str, *, key: str, gen: PseudonymGenerator) -> str:
    """Return a phone number shaped like ``source`` with a safe 555 exchange."""

    digits = re.sub(r"\D", "", source)
    rng = gen.rng("SAFE_PHONE", key)
    line = rng.randint(0, 9999)
    if source.strip().startswith("+"):
        new_digits = f"1555{line:04d}"
        return "+" + _format_digits_like(source[1:], new_digits)
    area = digits[:3] if len(digits) >= 10 else f"{rng.randint(200,999):03d}"
    new_digits = f"{area}555{line:04d}"
    return _format_digits_like(source, new_digits)
