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

import calendar
import re
from dataclasses import dataclass
from typing import Callable, cast

from redactor.config import ConfigModel
from redactor.detect.base import EntityLabel, EntitySpan
from redactor.pseudo import PseudonymGenerator, case_preserver, number_rules
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
    attrs: dict[str, object],
    *,
    key: str,
    gen: PseudonymGenerator,
) -> str:
    """Return a deterministic fake date mirroring ``source_text`` style."""

    fmt = cast(str | None, attrs.get("format"))
    normalized = cast(str | None, attrs.get("normalized"))

    def draw(rng_key: str) -> tuple[int, int, int, str]:
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
        return year, month, day, f"{year:04d}-{month:02d}-{day:02d}"

    year, month, day, norm = draw(key)
    if normalized:
        for salt in (":1", ":2"):
            if norm != normalized:
                break
            year, month, day, norm = draw(f"{key}{salt}")

    if fmt == "month_name_mdY":
        month_str = calendar.month_name[month]
        return f"{month_str} {day}, {year}"
    if fmt == "month_name_dmY":
        month_str = calendar.month_name[month]
        return f"{day} {month_str} {year}"
    if fmt == "mdY_numeric":
        m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", source_text)
        if m:
            month_fmt = f"{month:0{len(m.group(1))}d}"
            day_fmt = f"{day:0{len(m.group(2))}d}"
            return f"{month_fmt}/{day_fmt}/{year:04d}"
        return f"{month}/{day}/{year}"
    # default ISO format
    return norm


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
            key_attr = cast(str | None, sp.attrs.get("normalized_block"))
            key = sp.entity_id or key_attr or sp.text
            line_kinds = cast(list[str] | None, sp.attrs.get("line_kinds"))

            def build_addr(
                k: str,
                text: str = sp.text,
                line_kinds: list[str] | None = line_kinds,
            ) -> str:
                return gen.address_block_like(text, key=k, line_kinds=line_kinds)

            replacement = _ensure_diff(sp.text, key, build_addr)
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
        elif label is EntityLabel.PHONE:
            key = sp.entity_id or sp.text

            def build_phone(k: str, text: str = sp.text) -> str:
                return number_rules.generate_generic_digits_like(text, key=k, gen=gen)

            replacement = _ensure_diff(sp.text, key, build_phone)
        elif label is EntityLabel.ACCOUNT_ID:
            subtype = cast(str | None, sp.attrs.get("subtype")) or "generic"
            key = sp.entity_id or sp.text
            if subtype == "cc":

                def build_cc(k: str, text: str = sp.text) -> str:
                    return number_rules.generate_cc_like(text, key=k, gen=gen)

                replacement = _ensure_diff(sp.text, key, build_cc)
            elif subtype == "routing_aba":

                def build_routing(k: str, text: str = sp.text) -> str:
                    return number_rules.generate_routing_like(text, key=k, gen=gen)

                replacement = _ensure_diff(sp.text, key, build_routing)
            elif subtype == "iban":

                def build_iban(k: str, text: str = sp.text) -> str:
                    return number_rules.generate_iban_like(text, key=k, gen=gen)

                replacement = _ensure_diff(sp.text, key, build_iban)
            elif subtype == "ssn":

                def build_ssn(k: str, text: str = sp.text) -> str:
                    return number_rules.generate_ssn_like(text, key=k, gen=gen)

                replacement = _ensure_diff(sp.text, key, build_ssn)
            elif subtype == "ein":

                def build_ein(k: str, text: str = sp.text) -> str:
                    return number_rules.generate_ein_like(text, key=k, gen=gen)

                replacement = _ensure_diff(sp.text, key, build_ein)
            elif subtype == "swift_bic":

                def build_bic(k: str, text: str = sp.text) -> str:
                    return case_preserver.match_case(text, gen.account_number(k, kind="bic"))

                replacement = _ensure_diff(sp.text, key, build_bic)
            else:

                def build_generic(k: str, text: str = sp.text) -> str:
                    return number_rules.generate_generic_digits_like(text, key=k, gen=gen)

                replacement = _ensure_diff(sp.text, key, build_generic)
        elif label is EntityLabel.DOB:
            key = sp.entity_id or cast(str | None, sp.attrs.get("normalized")) or sp.text
            replacement = _generate_fake_date_like(sp.text, sp.attrs, key=key, gen=gen)
        elif label is EntityLabel.DATE_GENERIC:
            if cfg.redact.generic_dates:
                key = sp.entity_id or cast(str | None, sp.attrs.get("normalized")) or sp.text
                replacement = _generate_fake_date_like(sp.text, sp.attrs, key=key, gen=gen)
        elif label is EntityLabel.ALIAS_LABEL:
            alias_kind = cast(str | None, sp.attrs.get("alias_kind"))
            cluster_id = cast(str | None, sp.attrs.get("cluster_id")) or sp.entity_id
            if alias_kind == "role":
                if cfg.redact.alias_labels == "keep_roles":
                    replacement = None
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
        else:
            replacement = None

        if replacement is None:
            continue

        meta: dict[str, object] = {
            "source": sp.source,
            "span_id": sp.span_id,
            "subtype": sp.attrs.get("subtype"),
            "source_label_text": sp.text,
            "skip_replacement": False,
        }
        if label is EntityLabel.ALIAS_LABEL:
            meta["alias_kind"] = sp.attrs.get("alias_kind")
            if sp.entity_id:
                meta["cluster_id"] = sp.entity_id
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
