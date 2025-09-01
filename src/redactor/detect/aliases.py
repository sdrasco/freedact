"""Legal alias detector for "hereinafter" / AKA / FKA / DBA patterns.

This module provides :class:`AliasDetector`, a lightweight regular-expression
based detector that identifies legal alias definitions such as
``hereinafter "Buyer"`` or ``a/k/a "Johnny"``.  Only the alias label itself is
returned as a span (the contents inside quotes or the title‑cased token), while
trigger words and surrounding punctuation are excluded.  When possible the
detector associates the alias with a nearby subject mention to aid later
resolution.

The detector emits spans labelled :class:`~redactor.detect.base.EntityLabel`
``ALIAS_LABEL`` with attributes describing the trigger, quote style, subject
information and whether the alias is a role label or a nickname.  It performs a
few conservative sanity checks to avoid false positives and de‑duplicates spans
with identical boundaries.

This detector merely reports alias labels; it does not attempt to link them to
subjects or perform replacements.  Alias resolution is handled in later
pipeline stages.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Iterator

from redactor.preprocess.layout_reconstructor import (
    build_line_index,
    find_line_for_char,
)

from ..utils.constants import rtrim_index
from .base import DetectionContext, EntityLabel, EntitySpan

__all__ = ["AliasDetector", "get_detector"]

# ---------------------------------------------------------------------------
# Regular expressions
# ---------------------------------------------------------------------------

# Basic building blocks -----------------------------------------------------
NAME_TOKEN = r"[A-Z][\w&.’’-]*"
NAME_PHRASE = rf"{NAME_TOKEN}(?:\s+{NAME_TOKEN}){{0,6}}"

QUOTE_CHARS = "\"'“”‘’"
QUOTE_CLASS = re.escape(QUOTE_CHARS)

ROLE_LABELS: frozenset[str] = frozenset(
    {
        "Buyer",
        "Seller",
        "Lender",
        "Borrower",
        "Landlord",
        "Tenant",
        "Guarantor",
        "Licensor",
        "Licensee",
        "Plaintiff",
        "Defendant",
        "Petitioner",
        "Respondent",
        "Trustee",
        "Executor",
        "Administrator",
        "Assignor",
        "Assignee",
        "Discloser",
        "Recipient",
    }
)
RX_ROLE_ALIAS: re.Pattern[str] = re.compile(rf"^(?:{'|'.join(sorted(ROLE_LABELS))})$")


RX_HEREINAFTER_WITH_SUBJ: re.Pattern[str] = re.compile(
    rf"""
    (?P<subject>{NAME_PHRASE})[ \t]*,?[ \t]*\(?[ \t]*
    (?P<trigger>hereinafter|hereafter)\s+
    (?:referred\s+to\s+as\s+)?
    (?P<q1>[{QUOTE_CLASS}])(?P<alias>[^{QUOTE_CLASS}]+?)(?P<q2>[{QUOTE_CLASS}])
    """,
    re.IGNORECASE | re.VERBOSE,
)

RX_HEREINAFTER_ALIAS_ONLY: re.Pattern[str] = re.compile(
    rf"""
    (?P<trigger>hereinafter|hereafter)\s+
    (?:referred\s+to\s+as\s+)?
    (?P<q1>[{QUOTE_CLASS}])(?P<alias>[^{QUOTE_CLASS}]+?)(?P<q2>[{QUOTE_CLASS}])
    """,
    re.IGNORECASE | re.VERBOSE,
)

RX_AKA_FKA_DBA_QUOTED: re.Pattern[str] = re.compile(
    rf"""
    (?P<subject>{NAME_PHRASE})\s*,?\s*
    (?P<trigger>a/k/a|aka|f/k/a|fka|d/b/a|dba)\s+
    (?P<q1>[{QUOTE_CLASS}])(?P<alias>[^{QUOTE_CLASS}]+?)(?P<q2>[{QUOTE_CLASS}])
    """,
    re.IGNORECASE | re.VERBOSE,
)

RX_AKA_FKA_DBA: re.Pattern[str] = re.compile(
    rf"""
    (?P<subject>{NAME_PHRASE})\s*,?\s*
    (?P<trigger>a/k/a|aka|f/k/a|fka|d/b/a|dba)\s+
    (?P<alias>{NAME_PHRASE})(?=[^A-Za-z&.’’-]|$)
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _normalize_trigger(value: str) -> str:
    value = value.lower().replace("/", "")
    if value in {"aka", "fka", "dba", "hereinafter", "hereafter"}:
        return value
    return value


def _is_title_token(token: str) -> bool:
    return bool(re.match(r"^[A-Z][\w&.’’-]*$", token))


def _looks_like_subject(text: str) -> bool:
    if re.search(r"\b(LLC|Inc\.?|Ltd\.?|N\.A\.|Bank|Trust|Company)\b", text):
        return True
    words = text.split()
    for i in range(len(words) - 1):
        if _is_title_token(words[i]) and _is_title_token(words[i + 1]):
            return True
    return False


def _guess_subject(
    start: int, text: str, line_index: tuple[tuple[int, int, str], ...]
) -> tuple[str | None, int | None]:
    try:
        line_no = find_line_for_char(start, line_index)
    except ValueError:
        return None, None
    prev = line_no - 1
    while prev >= 0:
        l_start, l_end, _ = line_index[prev]
        candidate = text[l_start:l_end].strip()
        if candidate and _looks_like_subject(candidate):
            # TODO(M7-T2): prefer name-like candidates using
            # ``is_probable_person_name`` from ``names_person``.
            return candidate, prev
        prev -= 1
    return None, None


def _trim(text: str, start: int, end: int) -> tuple[str, int]:
    end = rtrim_index(text, end)
    return text[start:end], end


@dataclass(slots=True)
class _MatchInfo:
    alias_start: int
    alias_end: int
    trigger: str
    quote_style: str | None
    subject_text: str | None
    subject_span: tuple[int, int] | None
    subject_guess: str | None
    subject_guess_line: int | None
    scope_hint: str
    confidence: float


def _iter_matches(text: str) -> Iterator[_MatchInfo]:
    line_index = build_line_index(text)

    patterns: Iterable[re.Pattern[str]] = (
        RX_HEREINAFTER_WITH_SUBJ,
        RX_AKA_FKA_DBA_QUOTED,
        RX_AKA_FKA_DBA,
    )

    for pattern in patterns:
        for m in pattern.finditer(text):
            alias_start, alias_end = m.span("alias")
            subject_text = m.groupdict().get("subject")
            subject_span = m.span("subject") if subject_text else None
            trigger = _normalize_trigger(m.group("trigger"))
            q1 = m.groupdict().get("q1")
            q2 = m.groupdict().get("q2")
            quote_style = (q1 or "") + (q2 or "") if q1 or q2 else None
            yield _MatchInfo(
                alias_start,
                alias_end,
                trigger,
                quote_style,
                subject_text,
                subject_span,
                None,
                None,
                "same_line",
                0.99,
            )

    for m in RX_HEREINAFTER_ALIAS_ONLY.finditer(text):
        alias_start, alias_end = m.span("alias")
        trigger = _normalize_trigger(m.group("trigger"))
        q1 = m.groupdict().get("q1")
        q2 = m.groupdict().get("q2")
        quote_style = (q1 or "") + (q2 or "") if q1 or q2 else None
        subj_guess, subj_line = _guess_subject(alias_start, text, line_index)
        if subj_guess is not None:
            confidence = 0.97
            scope = "prev_lines"
        else:
            confidence = 0.95
            scope = "same_line"
        yield _MatchInfo(
            alias_start,
            alias_end,
            trigger,
            quote_style,
            None,
            None,
            subj_guess,
            subj_line,
            scope,
            confidence,
        )


class AliasDetector:
    """Detect legal alias labels such as AKA or hereinafter definitions."""

    def name(self) -> str:  # pragma: no cover - trivial
        return "aliases"

    def detect(self, text: str, context: DetectionContext | None = None) -> list[EntitySpan]:
        _ = context
        spans: list[EntitySpan] = []
        for mi in _iter_matches(text):
            alias_text, alias_end = _trim(text, mi.alias_start, mi.alias_end)
            if not alias_text:
                continue
            if "@" in alias_text:
                continue
            tokens = alias_text.split()
            if len(tokens) > 6 and any(t and t[0].islower() for t in tokens):
                continue
            alias_kind = "role" if RX_ROLE_ALIAS.fullmatch(alias_text) else "nickname"
            role_flag = alias_kind == "role"

            attrs: dict[str, object] = {
                "alias": alias_text,
                "alias_kind": alias_kind,
                "trigger": mi.trigger,
                "quote_style": mi.quote_style,
                "subject_text": mi.subject_text,
                "subject_span": (
                    {
                        "start": mi.subject_span[0],
                        "end": mi.subject_span[1],
                    }
                    if mi.subject_span
                    else None
                ),
                "scope_hint": mi.scope_hint,
                "confidence": mi.confidence,
                "role_flag": role_flag,
            }
            if mi.subject_guess is not None:
                attrs["subject_guess"] = mi.subject_guess
                attrs["subject_guess_line"] = mi.subject_guess_line

            spans.append(
                EntitySpan(
                    mi.alias_start,
                    alias_end,
                    alias_text,
                    EntityLabel.ALIAS_LABEL,
                    "aliases",
                    mi.confidence,
                    attrs,
                )
            )

        unique: dict[tuple[int, int], EntitySpan] = {}
        for sp in spans:
            key = (sp.start, sp.end)
            if key not in unique:
                unique[key] = sp
        return sorted(unique.values(), key=lambda s: s.start)


def get_detector() -> AliasDetector:
    """Return an :class:`AliasDetector` instance."""

    return AliasDetector()
