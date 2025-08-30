from __future__ import annotations

"""Redaction logic for Freedact.

This module contains the core text redaction pipeline and helpers used to
identify and replace personally identifying information.  It is imported by
the CLI entrypoint and is deliberately free of any I/O so that it can be used
programmatically.
"""

import re
import sys
from collections import OrderedDict, defaultdict
from dataclasses import dataclass
from typing import Dict, List, Tuple

# --- Required runtime check for 'unidecode' (hard requirement for normalization) ---
try:
    from unidecode import unidecode
except Exception:
    sys.stderr.write(
        "[ERROR] Missing required dependency 'unidecode'.\n"
        "Install it with:\n    pip install unidecode\n"
    )
    sys.exit(1)


# ----------------------------
# Utility dataclasses & types
# ----------------------------


@dataclass
class RedactionResult:
    text: str
    counts: Dict[str, int]
    placeholder_map: "OrderedDict[str, Dict[str, List[str]]]"  # {placeholder: {'canonical': str, 'aliases': [..]}}


# ----------------------------
# Redaction helpers
# ----------------------------

ORG_KEYWORDS = [
    "university", "college", "credit union", "bank", "trust", "llc", "inc",
    "corp", "company", "foundation", "department", "committee", "society"
]

# Built-in account name labels/brands/keywords (extensible via --account-term)
DEFAULT_ACCOUNT_TERMS = [
    "retirement account", "brokerage account", "checking account", "savings account",
    "money market", "credit card", "current account", "debit card", "investment account",
    "citibank", "fidelity", "tiaa-cref", "tiaa", "calpers", "santander", "hsbc",
    "bank of america", "wells fargo", "chase", "barclays", "capital one",
    "american express", "amex", "discover", "credit union",
]


def normalize_key(s: str) -> str:
    """ASCII lowercase, collapse whitespace and strip punctuation except hyphen/apostrophe for stable matching."""
    s_ascii = unidecode(s)
    s_ascii = s_ascii.replace("’", "'")
    s_ascii = re.sub(r"[^\w\s'\-\.]", " ", s_ascii)  # keep word chars, whitespace, apostrophe, hyphen, period
    s_ascii = re.sub(r"\s+", " ", s_ascii).strip()
    return s_ascii.lower()


def find_alias_links(text: str) -> Dict[str, str]:
    """
    Capture “Hereinafter ‘Alias’” style definitions and map alias -> full name (canonical string).
    Pattern rationale: simple, robust; avoids NLP; supports quotes “ ” ‘ ’ " ".
    """
    # Example: Dr. Jane A. Smith (hereinafter "Janie")
    title = r"(?:Dr|Mr|Mrs|Ms|Prof)\.\s+"
    token_word = r"(?:[A-Z][a-z]+(?:[-'][A-Za-z]+)*)"
    initial = r"(?:[A-Z]\.)"
    token = rf"(?:{token_word}|{initial})"
    full_name = rf"(?:{title})?{token}(?:\s+{token})+"  # ≥2 tokens
    # 'hereinafter' (optionally 'referred to as'), then quoted alias
    alias_pat = re.compile(
        rf"({full_name}).{{0,80}}?hereinafter(?:\s+referred\s+to\s+as)?\s*[“\"'‘]?([A-Za-z][\w\.\-']{{1,}})[”\"'’]?",
        re.IGNORECASE | re.DOTALL,
    )
    links: Dict[str, str] = {}
    for m in alias_pat.finditer(text):
        full = m.group(1)
        alias = m.group(2)
        # Strip leading titles from canonical full name in the mapping
        full_clean = re.sub(rf"^{title}", "", full).strip()
        links[normalize_key(alias)] = full_clean
    return links


def replace_person_names(
    text: str,
    include_allcaps: bool,
    mask_mode: bool,
    alias_links: Dict[str, str],
) -> Tuple[str, "OrderedDict[str, Dict[str, List[str]]]", int]:
    """
    Replace person names with deterministic placeholders or [REDACTED] and return:
      (new_text, placeholder_map, count_replacements)

    placeholder_map: OrderedDict mapping placeholder names like 'John Doe' or
    'Fred Doe 2' → {canonical: str, aliases: [..]}
    """
    # Build name pattern: optional title + ≥2 tokens; supports initials and hyphenated/apos names.
    title = r"(?:(?:Dr|Mr|Mrs|Ms|Prof)\.\s+)?"
    token_word = r"(?:[A-Z][a-z]+(?:[-'][A-Za-z]+)*)"
    initial = r"(?:[A-Z]\.)"
    token = rf"(?:{token_word}|{initial})"
    name_core = rf"{token}(?:\s+{token})+"  # at least two tokens
    # Optional possessive ’s or 's captured separately to preserve it.
    name_pat = re.compile(
        rf"(?<!\w){title}(?P<name>{name_core})(?P<pos>['’]s)?",
        re.MULTILINE,
    )

    # State for deterministic numbering and mapping
    namekey_to_placeholder: "OrderedDict[str, str]" = OrderedDict()
    placeholder_map: "OrderedDict[str, Dict[str, List[str]]]" = OrderedDict()
    next_id = 1
    count = 0

    PLACEHOLDER_FIRST_NAMES = [
        "John",
        "Fred",
        "June",
        "Alex",
        "Sam",
        "Pat",
        "Chris",
        "Robin",
        "Taylor",
        "Morgan",
    ]
    PLACEHOLDER_LAST_NAME = "Doe"
    PLACEHOLDER_RE = re.compile(
        r"^(?:" + "|".join(re.escape(n) for n in PLACEHOLDER_FIRST_NAMES) + r") "
        + re.escape(PLACEHOLDER_LAST_NAME)
        + r"(?: \d+)?\b"
    )

    def make_placeholder(idx: int) -> str:
        base = PLACEHOLDER_FIRST_NAMES[(idx - 1) % len(PLACEHOLDER_FIRST_NAMES)]
        cycle = (idx - 1) // len(PLACEHOLDER_FIRST_NAMES) + 1
        if cycle == 1:
            return f"{base} {PLACEHOLDER_LAST_NAME}"
        return f"{base} {PLACEHOLDER_LAST_NAME} {cycle}"

    # convenience
    def assign_placeholder(canonical: str) -> str:
        nonlocal next_id
        k = normalize_key(canonical)
        if k not in namekey_to_placeholder:
            ph = make_placeholder(next_id)
            namekey_to_placeholder[k] = ph
            placeholder_map[ph] = {"canonical": canonical, "aliases": []}
            next_id += 1
        return namekey_to_placeholder[k]

    # organization check
    def looks_like_org(s: str) -> bool:
        s_l = s.lower()
        return any(k in s_l for k in ORG_KEYWORDS)

    # ALL-CAPS detection (skip unless flag on)
    def is_all_caps_tokens(s: str) -> bool:
        words = re.findall(r"[A-Za-z][A-Za-z\-']*", s)
        words = [w for w in words if len(w) > 1]  # ignore 1-letter initials in caps check
        return bool(words) and all(w.isupper() for w in words)

    def repl(m: re.Match) -> str:
        nonlocal count
        raw = m.group(0)
        name_body = m.group("name")
        poss = m.group("pos") or ""

        # Idempotence: skip placeholders or [REDACTED]
        if PLACEHOLDER_RE.match(raw) or raw.strip().upper() == "[REDACTED]":
            return raw

        # Skip organizations
        if looks_like_org(raw):
            return raw

        # Skip ALL-CAPS unless requested (e.g., headings)
        if not include_allcaps and is_all_caps_tokens(name_body):
            return raw

        # Canonicalize: remove any leading title; preserve original spacing
        canonical = name_body.strip()

        # Alias linking: if matched name is an alias, map to its full canonical name
        alias_key = normalize_key(canonical)
        if alias_key in alias_links:
            canonical_full = alias_links[alias_key]
            placeholder = assign_placeholder(canonical_full)
            # track alias
            if normalize_key(canonical_full) != normalize_key(canonical):
                aliases = placeholder_map[placeholder]["aliases"]
                if canonical not in aliases:
                    aliases.append(canonical)
        else:
            placeholder = assign_placeholder(canonical)

        count += 1
        return ("[REDACTED]" if mask_mode else placeholder) + poss

    new_text = name_pat.sub(repl, text)
    # Replace standalone aliases that did not match the multi-token pattern
    if alias_links:
        alias_pattern = re.compile(
            r"\b(" + "|".join(re.escape(a) for a in alias_links.keys()) + r")(['’]s)?",
            re.IGNORECASE,
        )

        def repl_alias(m: re.Match) -> str:
            nonlocal count
            alias = m.group(1)
            poss = m.group(2) or ""
            canonical_full = alias_links[normalize_key(alias)]
            placeholder = assign_placeholder(canonical_full)
            if normalize_key(canonical_full) != normalize_key(alias):
                aliases = placeholder_map[placeholder]["aliases"]
                if alias not in aliases:
                    aliases.append(alias)
            count += 1
            return ("[REDACTED]" if mask_mode else placeholder) + poss

        new_text = alias_pattern.sub(repl_alias, new_text)

    return new_text, placeholder_map, count


def redact_addresses(text: str) -> Tuple[str, int]:
    """
    Redact address-like lines with [REDACTED ADDRESS].

    Heuristics:
      • Line matches: "<number> <street> <type>", e.g., "123 Main St", with common street types.
      • US "City, ST 12345" with optional ZIP+4.
      • UK postcodes (approximate but robust): "SW1A 1AA", "KY16 8QP" etc.
      • P.O. Box lines.
      • If a street line is redacted, redact the immediately following Apt/Apartment/Unit/Suite line too.
    """
    street_types = r"(?:St|Street|Rd|Road|Ave|Avenue|Blvd|Boulevard|Ln|Lane|Dr|Drive|Ct|Court|Broadway|Way|Ter|Terrace|Pl|Place|Pkwy|Parkway|Cir|Circle)\.?"
    street_line = re.compile(rf"^\s*\d{{1,6}}\s+[A-Za-z0-9\.\-\' ]+\s+{street_types}\s*$", re.IGNORECASE)
    po_box_line = re.compile(r"^\s*P\.?\s*O\.?\s*Box\s*\d+\s*$", re.IGNORECASE)
    city_state_zip = re.compile(r"^\s*[A-Za-z][A-Za-z\- ]+,\s*[A-Z]{2}\s+\d{5}(?:-\d{4})?\s*$", re.IGNORECASE)
    uk_postcode_anywhere = re.compile(r"\b(?:[A-Z]{1,2}\d{1,2}[A-Z]?\s*\d[A-Z]{2})\b", re.IGNORECASE)
    apt_next_line = re.compile(r"^\s*(?:Apt|Apartment|Unit|Suite|Ste)\s*[#\-]?\s*[A-Za-z0-9\-]+\s*$", re.IGNORECASE)

    lines = text.splitlines()
    redacted = 0
    i = 0
    out_lines: List[str] = []
    while i < len(lines):
        line = lines[i]
        is_street = bool(street_line.search(line)) or bool(po_box_line.search(line))
        is_city_zip = bool(city_state_zip.search(line))
        has_uk_postcode = bool(uk_postcode_anywhere.search(line))
        if is_street or is_city_zip or has_uk_postcode:
            out_lines.append("[REDACTED ADDRESS]")
            redacted += 1
            # If street, check next line for Apt/Apartment and redact it as well
            if is_street and (i + 1) < len(lines) and apt_next_line.search(lines[i + 1] or ""):
                out_lines.append("[REDACTED ADDRESS]")
                redacted += 1
                i += 2
                continue
            i += 1
            continue
        else:
            out_lines.append(line)
            i += 1
    return "\n".join(out_lines), redacted


def redact_account_names(text: str, custom_terms: List[str]) -> Tuple[str, int]:
    """
    Redact account labels/brands to [REDACTED ACCOUNT NAME].
    Terms are matched case-insensitively with word boundaries (hyphen allowed).
    """
    terms = [t.lower() for t in DEFAULT_ACCOUNT_TERMS] + [t.lower() for t in custom_terms]

    def term_to_pattern(t: str) -> str:
        parts = re.split(r"\s+", t)
        escaped = (re.escape(p) for p in parts)
        return r"\b" + r"(?:\s+|-)?".join(escaped) + r"\b"

    pattern = re.compile("|".join(term_to_pattern(t) for t in terms), re.IGNORECASE)
    count = 0

    def repl(m: re.Match) -> str:
        nonlocal count
        count += 1
        return "[REDACTED ACCOUNT NAME]"

    return pattern.sub(repl, text), count


def redact_account_numbers(text: str, strict_ids: bool) -> Tuple[str, int]:
    """
    Redact account numbers / IDs → [REDACTED ACCOUNT NUMBER].

    Patterns (applied in this order to avoid double-counting):
      1) account #<value>  (leave the 'account #' label)
      2) card-like #### #### #### #### (spaces/dashes optional)
      3) IBAN-like: 2 letters, 2 digits, 11–30 alnum
      4) 7+ digit runs
      5) VIN-like 11–17 uppercase A-HJ-NPR-Z0-9 (only with --strict-ids)
    """
    total = 0
    out = text

    acct_hash = re.compile(r"(?i)\b(account\s*#\s*)([A-Za-z0-9][A-Za-z0-9\- ]{2,})\b")

    def repl_acct_hash(m: re.Match) -> str:
        nonlocal total
        total += 1
        return m.group(1) + "[REDACTED ACCOUNT NUMBER]"

    out = acct_hash.sub(repl_acct_hash, out)

    card_like = re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b")
    out, n = card_like.subn("[REDACTED ACCOUNT NUMBER]", out)
    total += n

    iban_like = re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{2,4}){3,7}\b")
    out, n = iban_like.subn("[REDACTED ACCOUNT NUMBER]", out)
    total += n

    long_digits = re.compile(r"(?<!\[REDACTED ACCOUNT NUMBER\])\b\d{7,}\b")
    out, n = long_digits.subn("[REDACTED ACCOUNT NUMBER]", out)
    total += n

    if strict_ids:
        vin_like = re.compile(r"\b[A-HJ-NPR-Z0-9]{11,17}\b")
        out, n = vin_like.subn("[REDACTED ACCOUNT NUMBER]", out)
        total += n

    return out, total


# ----------------------------
# Redaction pipeline
# ----------------------------


def redact_text_pipeline(
    text: str,
    include_allcaps: bool,
    mask_mode: bool,
    strict_ids: bool,
    extra_account_terms: List[str],
) -> RedactionResult:
    """Run the full redaction pipeline and return results with counts and mapping."""
    counts: Dict[str, int] = defaultdict(int)

    alias_links = find_alias_links(text)

    text, c = redact_addresses(text)
    counts["addresses"] += c

    text, c = redact_account_names(text, custom_terms=extra_account_terms)
    counts["account_names"] += c

    text, c = redact_account_numbers(text, strict_ids=strict_ids)
    counts["account_numbers"] += c

    text, placeholder_map, c = replace_person_names(
        text=text,
        include_allcaps=include_allcaps,
        mask_mode=mask_mode,
        alias_links=alias_links,
    )
    counts["persons"] += c

    return RedactionResult(text=text, counts=dict(counts), placeholder_map=placeholder_map)

