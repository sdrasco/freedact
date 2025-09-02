"""Deterministic multi-line address replacement generator."""

from __future__ import annotations

import random
import re
from typing import List, cast

from ...detect.base import EntitySpan
from ..generator import PseudonymGenerator
from .address_data import CITIES, STATE_ABBRS, STREET_NAMES, STREET_TYPES

__all__ = ["generate_address_block_like"]


def _random_digits(rng: random.Random, count: int) -> str:
    return "".join(str(rng.randint(0, 9)) for _ in range(count))


def _mutate_like(template: str, rng: random.Random) -> str:
    out: List[str] = []
    for ch in template:
        if ch.isalpha():
            out.append(rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ"))
        elif ch.isdigit():
            out.append(str(rng.randint(0, 9)))
        else:
            out.append(ch)
    return "".join(out)


def generate_address_block_like(
    block: EntitySpan,
    *,
    gen: PseudonymGenerator,
    key: str | None = None,
) -> str:
    """Return a fake address block shaped like ``block``."""

    seed_key = key or block.entity_id or f"ADDR:{block.start}-{block.end}"
    rng = gen.rng("ADDRESS_BLOCK", seed_key)

    line_metas = cast(List[dict[str, object]], block.attrs.get("lines", []))
    raw_lines = block.text.splitlines(keepends=True)
    out_lines: List[str] = []

    for idx, meta in enumerate(line_metas):
        kind = cast(str, meta.get("kind", ""))
        text_meta = cast(str, meta.get("text", ""))
        raw = raw_lines[idx] if idx < len(raw_lines) else ""
        if raw.endswith("\r\n"):
            eol = "\r\n"
            body = raw[:-2]
        elif raw.endswith("\n"):
            eol = "\n"
            body = raw[:-1]
        else:
            eol = ""
            body = raw

        if kind == "po_box":
            prefix = text_meta.split()[0:2]
            prefix_text = " ".join(prefix)
            number = int(_random_digits(rng, rng.randint(3, 5)))
            line = f"{prefix_text} {number}"
        elif kind == "street":
            unit_match = re.search(r"\b(Apt|Ste|Suite|Unit|#)\b", text_meta, re.IGNORECASE)
            number = rng.randint(100, 9999)
            street = rng.choice(STREET_NAMES)
            stype = rng.choice(STREET_TYPES)
            core = f"{number} {street} {stype}"
            if unit_match:
                keyword = unit_match.group(0)
                unit_tail = text_meta[unit_match.end() :].strip()
                ident = _mutate_like(unit_tail, rng)
                line = f"{core} {keyword} {ident}".rstrip()
            else:
                line = core
        elif kind == "unit":
            m = re.match(r"\s*(Apt|Ste|Suite|Unit|#)\b", text_meta, re.IGNORECASE)
            keyword = m.group(1) if m else "Apt"
            ident = text_meta[m.end() :].strip() if m else text_meta.strip()
            ident = _mutate_like(ident, rng)
            line = f"{keyword} {ident}".strip()
        elif kind == "city_state_zip":
            zip_kind = cast(str | None, block.attrs.get("zip_kind"))
            city = rng.choice(CITIES)
            state = rng.choice(STATE_ABBRS)
            zip_code = f"{rng.randint(0, 99999):05d}"
            if zip_kind == "zip9":
                zip_code = f"{zip_code}-{rng.randint(0, 9999):04d}"
            if "," in body:
                comma_pos = body.find(",")
                after = body[comma_pos + 1 :]
                spaces = len(after) - len(after.lstrip(" "))
                after = after.lstrip(" ")
                state_sep = after[2:]
                spaces2 = len(state_sep) - len(state_sep.lstrip(" "))
                sep1 = "," + " " * spaces
                sep2 = " " * spaces2
                line = f"{city}{sep1}{state}{sep2}{zip_code}".rstrip()
            else:
                parts = body.split()
                sep2 = " "
                if len(parts) > 2:
                    sep2 = body[body.find(parts[1]) + len(parts[1]) : body.find(parts[2])]
                line = f"{city} {state}{sep2}{zip_code}".rstrip()
        else:
            line = body

        if len(line) > 120:
            line = line[:120]
        assert "Acct_" not in line and "ACCT_" not in line
        out_lines.append(line + eol)

    result = "".join(out_lines)
    assert "Acct_" not in result and "ACCT_" not in result
    return result
