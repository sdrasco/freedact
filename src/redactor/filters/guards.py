"""Lightweight span guards for safe redaction profiles."""

from __future__ import annotations

import re
from typing import Iterable, List, Tuple

from redactor.detect.base import EntityLabel, EntitySpan


def _is_title_token(tok: str) -> bool:
    base = tok.strip(".:;,'\"-")
    return base[:1].isupper() and base[1:].islower()


def find_heading_ranges(text: str) -> List[Tuple[int, int]]:
    """Return character ranges for common legal heading patterns."""

    ranges: List[Tuple[int, int]] = []
    offset = 0
    roman_re = re.compile(r"^[IVXLCDM]+\.\s+(?:[A-Z][a-z]+\s+){0,7}[A-Z][a-z]+:?$")
    lines = text.splitlines(keepends=True)
    for line in lines:
        stripped = line.strip()
        end = offset + len(line)
        if not stripped:
            offset = end
            continue
        tokens = stripped.split()
        token_count = len(tokens)
        if 2 <= token_count <= 6 and all(_is_title_token(t) for t in tokens):
            ranges.append((offset, end))
        elif roman_re.match(stripped):
            ranges.append((offset, end))
        elif 2 <= token_count <= 6 and stripped.upper() == stripped:
            ranges.append((offset, end))
        offset = end
    return ranges


def _intersects(a: EntitySpan, b: EntitySpan) -> bool:
    return not (a.end <= b.start or a.start >= b.end)


def filter_spans_for_safety(
    spans: List[EntitySpan],
    *,
    heading_ranges: Iterable[Tuple[int, int]],
    address_blocks: Iterable[EntitySpan],
    protect_headings: bool,
    gpe_outside_addresses: bool,
) -> List[EntitySpan]:
    """Return ``spans`` after applying safety guards."""

    result: List[EntitySpan] = []
    headings = list(heading_ranges)
    addr_blocks = list(address_blocks)
    protected_labels = {
        EntityLabel.PERSON,
        EntityLabel.ORG,
        EntityLabel.GPE,
        EntityLabel.LOC,
        EntityLabel.ALIAS_LABEL,
    }
    exempt_labels = {
        EntityLabel.ADDRESS_BLOCK,
        EntityLabel.DOB,
        EntityLabel.EMAIL,
        EntityLabel.PHONE,
        EntityLabel.ACCOUNT_ID,
    }
    for sp in spans:
        if sp.label in exempt_labels:
            result.append(sp)
            continue
        drop = False
        if protect_headings and sp.label in protected_labels:
            for start, end in headings:
                if sp.start >= start and sp.end <= end:
                    drop = True
                    break
        if not drop and gpe_outside_addresses and sp.label in {EntityLabel.GPE, EntityLabel.LOC}:
            if not any(_intersects(sp, ab) for ab in addr_blocks):
                drop = True
        if not drop:
            result.append(sp)
    return result
