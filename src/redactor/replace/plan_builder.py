"""Replacement plan builder.

This module translates resolved :class:`~redactor.detect.base.EntitySpan`
objects into concrete replacement operations.  Each span is mapped to a
pseudonym according to its :class:`~redactor.detect.base.EntityLabel` and
case/format is preserved.  The resulting plan is safe to apply in reverse order
without shifting indices.

The builder enforces non‑overlapping spans, handles label specific policy such
as keeping role aliases or generic dates, and guarantees deterministic output by
seeding :class:`~redactor.pseudo.generator.PseudonymGenerator` with the provided
configuration and text.  When a generated replacement accidentally matches the
original span text a salted key is used to deterministically retry until a
different value is produced.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Callable, cast

from redactor.config import ConfigModel
from redactor.detect.base import EntityLabel, EntitySpan
from redactor.pseudo import PseudonymGenerator, case_preserver, number_rules
from redactor.pseudo.generators.address import generate_address_block_like
from redactor.utils import datefmt
from redactor.utils.textspan import ensure_non_overlapping

__all__ = ["PlanEntry", "build_replacement_plan"]


@dataclass(slots=True)
class PlanEntry:
    """Description of a single replacement operation."""

    start: int
    end: int
    replacement: str
    label: EntityLabel
    entity_id: str | None
    span_id: str | None
    meta: dict[str, object]


def _ensure_diff(original: str, key: str, builder: Callable[[str], str]) -> str:
    """Return ``builder`` output ensuring it differs from ``original``."""

    for salt in ("", ":1", ":2"):
        candidate = builder(key + salt if salt else key)
        if candidate != original:
            return candidate
    return candidate


def _generate_fake_date_like(
    source_text: str,
    *,
    key: str,
    gen: PseudonymGenerator,
) -> str:
    """Return a deterministic fake date mirroring ``source_text`` style."""

    parsed = datefmt.parse_like(source_text)
    if not parsed:
        return source_text
    original_date, style = parsed

    def draw(rng_key: str) -> date:
        rng = gen.rng("DOB", rng_key)
        year = rng.randint(1930, 2005)
        month = rng.randint(1, 12)
        if month == 2:
            leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
            max_day = 29 if leap else 28
        elif month in {1, 3, 5, 7, 8, 10, 12}:
            max_day = 31
        else:
            max_day = 30
        day = rng.randint(1, max_day)
        return date(year, month, day)

    new_date = draw(key)
    for salt in (":1", ":2"):
        if new_date != original_date:
            break
        new_date = draw(f"{key}{salt}")

    return datefmt.format_like(new_date, style)


def _normalize_digits(text: str) -> str:
    """Return ``text`` stripped to digits only."""

    return re.sub(r"\D", "", text)


def _luhn_valid(num: str) -> bool:
    total = 0
    for idx, ch in enumerate(reversed(num)):
        digit = int(ch)
        if idx % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def _aba_check_digit(eight: str) -> str:
    weights = [3, 7, 1] * 3
    total = sum(int(d) * w for d, w in zip(eight, weights, strict=False))
    return str((10 - total % 10) % 10)


def _format_digits_like(source: str, digits: str) -> str:
    """Replace digits in ``source`` with those from ``digits``."""

    it = iter(digits)
    out: list[str] = []
    for ch in source:
        if ch.isdigit():
            out.append(next(it, "0"))
        else:
            out.append(ch)
    return "".join(out)


def _detect_account_subtype(source: str) -> str:
    if re.fullmatch(r"\d{2}-\d{7}", source):
        return "ein"
    if re.fullmatch(r"\d{3}-\d{2}-\d{4}", source):
        return "ssn"
    if re.fullmatch(r"\d{9}", _normalize_digits(source)) and "-" not in source:
        return "routing_aba"
    if re.search(r"[A-Za-z]", source):
        if re.match(r"[A-Za-z]{2}", source):
            return "iban"
        return "swift_bic"
    digits = _normalize_digits(source)
    if 13 <= len(digits) <= 19:
        return "cc"
    return "generic"


def _ensure_safe_replacement(
    label: EntityLabel,
    source: str,
    candidate: str,
    *,
    key: str,
    gen: PseudonymGenerator,
) -> str:
    """Return a safe replacement value for ``candidate``."""

    for attempt in range(3):
        if label is EntityLabel.EMAIL:
            local, _, domain = candidate.partition("@")
            domain = domain.lower()
            if not domain.isascii() or domain != "example.org":
                candidate = f"{local}@example.org"
                domain = "example.org"
            if domain == "example.org" and domain.isascii():
                return candidate
            token = gen.token("EMAIL", f"{key}:{attempt + 1}", length=10)
            local = f"u{token}"
            if "+" in source.split("@", 1)[0]:
                local = f"{local}+t{token[-3:]}"
            candidate = f"{local}@example.org"
            continue
        if label is EntityLabel.PHONE:
            digits = _normalize_digits(candidate)
            if candidate.startswith("+"):
                if digits.startswith("1555"):
                    return candidate
            elif len(digits) >= 10 and digits[3:6] == "555":
                return candidate
            rng = gen.rng("SAFE_PHONE", f"{key}:{attempt + 1}")
            npa = rng.randint(200, 999)
            line = rng.randint(0, 9999)
            new_digits = f"{npa:03d}555{line:04d}"
            if candidate.startswith("+"):
                new_digits = "1" + new_digits
                candidate = "+" + _format_digits_like(candidate[1:], new_digits)
            else:
                candidate = _format_digits_like(candidate, new_digits)
            continue
        if label is EntityLabel.ACCOUNT_ID:
            subtype = _detect_account_subtype(source)
            digits = _normalize_digits(candidate)
            if subtype == "cc":
                if _luhn_valid(digits):
                    return candidate
                candidate = gen.cc_like(source, key=f"{key}:{attempt + 1}")
                continue
            if subtype == "routing_aba":
                if (
                    len(digits) == 9
                    and digits != "021000021"
                    and _aba_check_digit(digits[:8]) == digits[8]
                ):
                    return candidate
                candidate = gen.routing_like(source, key=f"{key}:{attempt + 1}")
                continue
            if subtype == "ssn":
                area = digits[:3]
                if area not in {"000", "666"} and not area.startswith("9"):
                    return candidate
                candidate = gen.ssn_like(source, key=f"{key}:{attempt + 1}")
                continue
            if subtype == "ein":
                if "-" in candidate and digits != _normalize_digits(source):
                    return candidate
                candidate = gen.ein_like(source, key=f"{key}:{attempt + 1}")
                continue
            if subtype == "iban":
                if candidate != source:
                    return candidate
                candidate = gen.iban_like(source, key=f"{key}:{attempt + 1}")
                continue
            if subtype == "swift_bic":
                if candidate.isascii() and candidate != source:
                    return candidate
                candidate = case_preserver.match_case(
                    source, gen.account_number(f"{key}:{attempt + 1}", kind="bic")
                )
                continue
            if digits != _normalize_digits(source):
                return candidate
            candidate = gen.generic_digits_like(source, key=f"{key}:{attempt + 1}")
            continue
        if label is EntityLabel.DOB:
            if _normalize_digits(candidate) != _normalize_digits(source):
                return candidate
            candidate = _generate_fake_date_like(
                source,
                key=f"{key}:{attempt + 1}",
                gen=gen,
            )
            continue
        return candidate
    return candidate


def build_replacement_plan(
    text: str,
    spans: list[EntitySpan],
    cfg: ConfigModel,
    *,
    clusters: dict[str, dict[str, object]] | None = None,
) -> list[PlanEntry]:
    """Return replacement plan entries for ``spans`` within ``text``."""

    _ = clusters  # unused placeholder for future expansion
    ensure_non_overlapping(spans)
    gen = PseudonymGenerator(cfg, text=text)
    plan: list[PlanEntry] = []

    for sp in sorted(spans, key=lambda s: s.start):
        if cast(bool, sp.attrs.get("skip_replacement")):
            continue

        replacement: str | None = None
        label = sp.label
        skip_flag = False

        if label is EntityLabel.PERSON:
            key = sp.entity_id or sp.text

            def build_person(k: str, text: str = sp.text) -> str:
                return case_preserver.format_like(text, gen.person_name_like(text, key=k))

            replacement = _ensure_diff(sp.text, key, build_person)
        elif label is EntityLabel.ORG:
            key = sp.entity_id or sp.text

            def build_org(k: str, text: str = sp.text) -> str:
                return case_preserver.format_like(text, gen.org_name_like(text, key=k))

            replacement = _ensure_diff(sp.text, key, build_org)
        elif label is EntityLabel.BANK_ORG:
            key = sp.entity_id or sp.text

            def build_bank(k: str, text: str = sp.text) -> str:
                return case_preserver.format_like(text, gen.bank_org_like(text, key=k))

            replacement = _ensure_diff(sp.text, key, build_bank)
        elif label is EntityLabel.ADDRESS_BLOCK:
            base_key = sp.entity_id or f"ADDR:{sp.start}-{sp.end}"
            expected_nl = sp.text.count("\n")
            lines_meta = cast(list[dict[str, object]], sp.attrs.get("lines", []))
            replacement = None
            for salt in ("", ":1", ":2"):
                candidate = generate_address_block_like(
                    sp, gen=gen, key=f"{base_key}{salt}" if salt else base_key
                )
                if candidate.count("\n") == expected_nl:
                    replacement = candidate
                    break
            if replacement is None:
                eol = "\r\n" if "\r\n" in sp.text else "\n"
                replacement = f"1234 Oak St{eol}Springfield, IL 62704"
            if "Acct_" in replacement or "ACCT_" in replacement:
                raise AssertionError("unsafe token in address replacement")
        elif label is EntityLabel.EMAIL:
            base_local = cast(str, sp.attrs.get("base_local") or "").lower()
            tag = cast(str | None, sp.attrs.get("tag"))
            key = base_local or sp.text

            def build_email(token_key: str, tag: str | None = tag) -> str:
                token = gen.token("EMAIL", token_key, length=10)
                local = f"u{token}"
                if tag:
                    local = f"{local}+t{token[-3:]}"
                return f"{local}@example.org"

            replacement = _ensure_diff(sp.text, key, build_email)
            replacement = _ensure_safe_replacement(
                EntityLabel.EMAIL, sp.text, replacement, key=key, gen=gen
            )
        elif label is EntityLabel.PHONE:
            key = sp.entity_id or sp.text

            def build_phone(k: str, text: str = sp.text) -> str:
                return number_rules.generate_generic_digits_like(text, key=k, gen=gen)

            replacement = _ensure_diff(sp.text, key, build_phone)
            replacement = _ensure_safe_replacement(
                EntityLabel.PHONE, sp.text, replacement, key=key, gen=gen
            )
        elif label is EntityLabel.ACCOUNT_ID:
            subtype = cast(str | None, sp.attrs.get("subtype")) or "generic"
            key = sp.entity_id or sp.text
            if subtype == "cc":

                def build_cc(k: str, text: str = sp.text) -> str:
                    return number_rules.generate_cc_like(text, key=k, gen=gen)

                replacement = _ensure_diff(sp.text, key, build_cc)
                replacement = _ensure_safe_replacement(
                    EntityLabel.ACCOUNT_ID, sp.text, replacement, key=key, gen=gen
                )
            elif subtype == "routing_aba":

                def build_routing(k: str, text: str = sp.text) -> str:
                    return number_rules.generate_routing_like(text, key=k, gen=gen)

                replacement = _ensure_diff(sp.text, key, build_routing)
                replacement = _ensure_safe_replacement(
                    EntityLabel.ACCOUNT_ID, sp.text, replacement, key=key, gen=gen
                )
            elif subtype == "iban":

                def build_iban(k: str, text: str = sp.text) -> str:
                    return number_rules.generate_iban_like(text, key=k, gen=gen)

                replacement = _ensure_diff(sp.text, key, build_iban)
                replacement = _ensure_safe_replacement(
                    EntityLabel.ACCOUNT_ID, sp.text, replacement, key=key, gen=gen
                )
            elif subtype == "ssn":

                def build_ssn(k: str, text: str = sp.text) -> str:
                    return number_rules.generate_ssn_like(text, key=k, gen=gen)

                replacement = _ensure_diff(sp.text, key, build_ssn)
                replacement = _ensure_safe_replacement(
                    EntityLabel.ACCOUNT_ID, sp.text, replacement, key=key, gen=gen
                )
            elif subtype == "ein":

                def build_ein(k: str, text: str = sp.text) -> str:
                    return number_rules.generate_ein_like(text, key=k, gen=gen)

                replacement = _ensure_diff(sp.text, key, build_ein)
                replacement = _ensure_safe_replacement(
                    EntityLabel.ACCOUNT_ID, sp.text, replacement, key=key, gen=gen
                )
            elif subtype == "swift_bic":

                def build_bic(k: str, text: str = sp.text) -> str:
                    return case_preserver.match_case(text, gen.account_number(k, kind="bic"))

                replacement = _ensure_diff(sp.text, key, build_bic)
                replacement = _ensure_safe_replacement(
                    EntityLabel.ACCOUNT_ID, sp.text, replacement, key=key, gen=gen
                )
            else:

                def build_generic(k: str, text: str = sp.text) -> str:
                    return number_rules.generate_generic_digits_like(text, key=k, gen=gen)

                replacement = _ensure_diff(sp.text, key, build_generic)
                replacement = _ensure_safe_replacement(
                    EntityLabel.ACCOUNT_ID, sp.text, replacement, key=key, gen=gen
                )
        elif label is EntityLabel.DOB:
            key = sp.entity_id or cast(str | None, sp.attrs.get("normalized")) or sp.text
            replacement = _generate_fake_date_like(sp.text, key=key, gen=gen)
            replacement = _ensure_safe_replacement(
                EntityLabel.DOB, sp.text, replacement, key=key, gen=gen
            )
        elif label is EntityLabel.DATE_GENERIC:
            if cfg.redact.generic_dates:
                key = sp.entity_id or cast(str | None, sp.attrs.get("normalized")) or sp.text
                replacement = _generate_fake_date_like(sp.text, key=key, gen=gen)
        elif label is EntityLabel.ALIAS_LABEL:
            alias_kind = cast(str | None, sp.attrs.get("alias_kind"))
            cluster_id = cast(str | None, sp.attrs.get("cluster_id")) or sp.entity_id
            skip_alias = False
            if alias_kind == "role":
                if cfg.redact.alias_labels == "keep_roles":
                    replacement = sp.text
                    skip_alias = True
                else:

                    def build_role(k: str, text: str = sp.text) -> str:
                        token = gen.token("ROLE", k, length=2)
                        letter = chr(ord("A") + (int(token, 32) % 26))
                        return case_preserver.format_like(text, f"Party {letter}")

                    replacement = _ensure_diff(sp.text, cluster_id or sp.text, build_role)
            else:
                key = cluster_id or sp.text

                def build_nick(k: str, text: str = sp.text) -> str:
                    pseudo_full = gen.person_name_like("John Doe", key=k)
                    first = pseudo_full.split()[0] if pseudo_full.strip() else pseudo_full
                    return case_preserver.format_like(text, first)

                replacement = _ensure_diff(sp.text, key, build_nick)
            skip_flag = skip_alias
        else:
            replacement = None

        if replacement is None:
            continue

        # Never include secrets or cfg values in ``meta``; audit writer will
        # refuse to write if secret-like values appear.
        meta: dict[str, object] = {
            "source": sp.source,
            "span_id": sp.span_id,
            "subtype": sp.attrs.get("subtype"),
            "source_label_text": sp.text,
            "skip_replacement": skip_flag,
        }
        if label is EntityLabel.ALIAS_LABEL:
            meta["alias_kind"] = sp.attrs.get("alias_kind")
            if sp.entity_id:
                meta["cluster_id"] = sp.entity_id
        if label is EntityLabel.ADDRESS_BLOCK:
            meta.update(
                {
                    "block_lines": len(lines_meta),
                    "zip_kind": sp.attrs.get("zip_kind"),
                    "source_hint": sp.attrs.get("source_hint"),
                }
            )
        plan.append(
            PlanEntry(
                start=sp.start,
                end=sp.end,
                replacement=replacement,
                label=label,
                entity_id=sp.entity_id,
                span_id=sp.span_id,
                meta=meta,
            )
        )

    return plan
