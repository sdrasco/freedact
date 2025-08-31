"""Address pseudonym generation helpers.

The functions in this module synthesize plausible but fictitious address
elements.  They preserve the *shape* of the original strings – number of tokens,
punctuation and casing – while guaranteeing that the generated values differ
from the source.  All randomness is drawn from
``PseudonymGenerator.rng(kind, key)`` so results are deterministic per
``(kind, key)`` pair.

The helpers are intentionally lightweight; they do not attempt full postal
validation.  Street names, city names and US state abbreviations come from small
curated lists.  :func:`redactor.pseudo.case_preserver.format_like` is used to
carry over punctuation and letter casing from the source spans.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, List

from .case_preserver import format_like

if TYPE_CHECKING:  # pragma: no cover
    from .generator import PseudonymGenerator

# ---------------------------------------------------------------------------
# Static corpora

STREET_NAMES: List[str] = [
    "Oak",
    "Maple",
    "Pine",
    "Cedar",
    "Elm",
    "Walnut",
    "Willow",
    "Birch",
    "Spruce",
    "Chestnut",
    "Ash",
    "Holly",
    "Magnolia",
    "Cottonwood",
    "Sycamore",
    "Poplar",
    "Hickory",
    "Laurel",
    "Juniper",
    "Aspen",
    "Alder",
    "Beech",
    "Cypress",
    "Hemlock",
    "Linden",
    "Redwood",
    "Sequoia",
    "Fir",
    "Palm",
    "Briar",
    "Brook",
    "Meadow",
    "Sunset",
    "Ridge",
    "Valley",
    "River",
    "Forest",
    "Hill",
    "Lake",
    "Park",
    "Stone",
    "Glen",
    "Highland",
    "King",
    "Queen",
    "Liberty",
    "Heritage",
    "Prairie",
    "Harbor",
    "Garden",
]

STREET_SUFFIXES: List[str] = [
    "St",
    "Ave",
    "Rd",
    "Blvd",
    "Ln",
    "Dr",
    "Ct",
    "Way",
    "Pl",
]

CITY_NAMES: List[str] = [
    "Fairview",
    "Riverton",
    "Hillcrest",
    "Lakeside",
    "Brookfield",
    "Westfield",
    "Meadowview",
    "Oakdale",
    "Pinehurst",
    "Cedar Grove",
    "Clearwater",
    "Grandview",
    "Highland",
    "Mapleton",
    "Northfield",
    "Pleasantville",
    "Rosewood",
    "Silverton",
    "Springfield",
    "Woodland",
]

STATE_CODES: List[str] = [
    "AL",
    "AK",
    "AZ",
    "AR",
    "CA",
    "CO",
    "CT",
    "DE",
    "FL",
    "GA",
    "HI",
    "ID",
    "IL",
    "IN",
    "IA",
    "KS",
    "KY",
    "LA",
    "ME",
    "MD",
    "MA",
    "MI",
    "MN",
    "MS",
    "MO",
    "MT",
    "NE",
    "NV",
    "NH",
    "NJ",
    "NM",
    "NY",
    "NC",
    "ND",
    "OH",
    "OK",
    "OR",
    "PA",
    "RI",
    "SC",
    "SD",
    "TN",
    "TX",
    "UT",
    "VT",
    "VA",
    "WA",
    "WV",
    "WI",
    "WY",
]


def _normalize(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", text).lower()


# ---------------------------------------------------------------------------
# Line generators


def generate_street_line_like(source: str, *, key: str, gen: PseudonymGenerator) -> str:
    """Return a street line shaped like ``source``."""

    unit_match = re.search(r"\b(?:Apt|Suite|Unit|#)\b.*", source, re.IGNORECASE)
    unit_part = unit_match.group(0) if unit_match else ""
    core = source[: unit_match.start()].strip() if unit_match else source.strip()

    # Detect directional prefixes/suffixes
    tokens = core.split()
    pre_dir = ""
    post_dir = ""
    if tokens:
        rest = tokens[1:]
        if rest and re.fullmatch(r"[NSEW]{1,2}", rest[0]):
            pre_dir = rest[0]
            rest = rest[1:]
        if rest and re.fullmatch(r"[NSEW]{1,2}", rest[-1]):
            post_dir = rest[-1]
            rest = rest[:-1]
    for salt in range(5):
        rng = gen.rng("ADDRESS", f"{key}:{salt}" if salt else key)
        number = rng.randint(100, 9999)
        street = rng.choice(STREET_NAMES)
        suffix = rng.choice(STREET_SUFFIXES)
        if pre_dir:
            street = f"{pre_dir} {street}"
        candidate_core = f"{number} {street} {suffix}"
        if post_dir:
            candidate_core = f"{candidate_core} {post_dir}"
        if _normalize(candidate_core) != _normalize(core):
            break

    if unit_part:
        candidate_core = f"{candidate_core} {unit_part}"
    return candidate_core


def generate_unit_line_like(source: str, *, key: str, gen: PseudonymGenerator) -> str:
    """Return a unit/apartment line shaped like ``source``."""

    match = re.search(r"\b(?:Apt|Suite|Unit|#)\b", source, re.IGNORECASE)
    label = match.group(0) if match else "#"
    ident = source[match.end() :].strip() if match else source.strip()

    for salt in range(5):
        rng = gen.rng("ADDRESS_UNIT", f"{key}:{salt}" if salt else key)
        built = []
        for ch in ident:
            if ch.isalpha():
                built.append(rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ"))
            elif ch.isdigit():
                built.append(str(rng.randint(0, 9)))
            else:
                built.append(ch)
        candidate_ident = "".join(built)
        if _normalize(candidate_ident) != _normalize(ident):
            break

    candidate = f"{label} {candidate_ident}".strip()
    return format_like(source, candidate, rng=rng)


def generate_city_state_zip_like(source: str, *, key: str, gen: PseudonymGenerator) -> str:
    """Return a city/state/ZIP line shaped like ``source``."""

    for salt in range(5):
        rng = gen.rng("ADDRESS_CSZ", f"{key}:{salt}" if salt else key)
        city = rng.choice(CITY_NAMES)
        state = rng.choice(STATE_CODES)
        zip_code = f"{rng.randint(0, 99999):05d}"
        candidate = f"{city}, {state} {zip_code}".strip()
        if _normalize(candidate) != _normalize(source):
            break
    return candidate


def generate_address_block_like(
    block_text: str,
    *,
    key: str,
    gen: PseudonymGenerator,
    line_kinds: List[str] | None = None,
) -> str:
    """Return an address block with each line pseudonymized."""

    lines = block_text.splitlines()
    if line_kinds is None:
        kinds: List[str | None] = [None] * len(lines)
    else:
        kinds = list(line_kinds)
    out_lines: List[str] = []
    for idx, (line, kind) in enumerate(zip(lines, kinds, strict=False)):
        sub_key = f"{key}:{idx}"
        if kind is None:
            if re.search(r"\b(?:Apt|Suite|Unit|#)\b", line, re.IGNORECASE):
                kind = "unit"
            elif re.search(r",\s*[A-Z]{2}\b", line):
                kind = "city_state_zip"
            elif re.search(r"\bP\.?O\.\s*Box\b", line, re.IGNORECASE):
                kind = "po_box"
            else:
                kind = "street"
        if kind == "street":
            out = generate_street_line_like(line, key=sub_key, gen=gen)
        elif kind == "unit":
            out = generate_unit_line_like(line, key=sub_key, gen=gen)
        elif kind == "city_state_zip":
            out = generate_city_state_zip_like(line, key=sub_key, gen=gen)
        elif kind == "po_box":
            rng = gen.rng("ADDRESS_PO", sub_key)
            num = rng.randint(100, 99999)
            candidate = f"PO Box {num}"
            out = format_like(line, candidate, rng=rng)
        else:
            out = line
        out_lines.append(out)
    return "\n".join(out_lines)


__all__ = [
    "STREET_NAMES",
    "STREET_SUFFIXES",
    "CITY_NAMES",
    "STATE_CODES",
    "generate_street_line_like",
    "generate_unit_line_like",
    "generate_city_state_zip_like",
    "generate_address_block_like",
]
