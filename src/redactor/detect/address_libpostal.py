"""Line-level US address detector using ``usaddress``.

This module implements :class:`AddressLineDetector`, a conservative detector that
identifies likely address lines in text.  Each line of input is analysed in
isolation and, when a street, unit, city/state/ZIP or PO Box pattern is
recognised, a span labelled :class:`~redactor.detect.base.EntityLabel.ADDRESS_BLOCK`
is returned.  Leading labels such as ``"Address:"`` and surrounding punctuation
are trimmed before parsing.  The detector currently relies on the ``usaddress``
library and assigns confidences based on the matched line kind.  Merging of
adjacent lines into multi-line address blocks is handled in a later milestone.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable, Sequence

try:
    import usaddress
except Exception:  # pragma: no cover - optional dependency
    usaddress = None

from .base import DetectionContext, EntityLabel, EntitySpan

__all__ = ["AddressLineDetector", "get_detector"]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Characters trimmed from the left and right of each line before parsing.
PREFIX_PUNCT = " \t«“([<{"
SUFFIX_PUNCT = " \t»”’)]}>,;:.!?"

# Prefix labels commonly preceding addresses which should be excluded from the
# parsed span.  The pattern is case-insensitive and accepts an optional trailing
# ``:``, ``-`` or ``–`` followed by whitespace.
PREFIX_LABEL_RE = re.compile(
    r"^(?:address|mailing address|registered office|residence|location|addr)\s*[:\u2013-]?\s*",
    re.IGNORECASE,
)

# Prefilter regexes compiled at import time
RX_POBOX: re.Pattern[str] = re.compile(r"^\s*(P.?\sO.?\sBox)\b", re.IGNORECASE)
RX_UNIT: re.Pattern[str] = re.compile(
    r"\b(Suite|Ste.?|Apt.?|Apartment|Unit|#|Floor|Fl.?|Rm.?|Room)\b", re.IGNORECASE
)
RX_CITY_STATE: re.Pattern[str] = re.compile(r",\s*[A-Z]{2}\b")
RX_ZIP: re.Pattern[str] = re.compile(r"\b\d{5}(?:-\d{4})?\b")


@lru_cache(maxsize=2048)
def _parse_usaddr(core: str) -> list[tuple[str, str]]:
    if usaddress is None:  # pragma: no cover - optional dependency missing
        raise RuntimeError("usaddress library not available")
    return list(usaddress.parse(core))


def _should_parse_line(core: str) -> bool:
    if any(ch.isdigit() for ch in core):
        return True
    if RX_POBOX.search(core):
        return True
    if RX_UNIT.search(core):
        return True
    if RX_CITY_STATE.search(core):
        return True
    if RX_ZIP.search(core):
        return True
    return False


@dataclass(slots=True)
class _ParsedLine:
    tokens: list[tuple[str, str]]
    components: dict[str, str]
    labels: set[str]


class AddressLineDetector:
    """Detect address lines using ``usaddress``."""

    def __init__(self, backend: str | None = None) -> None:
        self._backend = backend or "auto"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def name(self) -> str:  # pragma: no cover - trivial
        return "address_line"

    def detect(self, text: str, context: DetectionContext | None = None) -> list[EntitySpan]:
        """Detect address lines in ``text``."""

        backend = self._select_backend(context)
        if backend != "usaddress":  # pragma: no cover - defensive
            return []
        return self._detect_usaddress(text)

    # ------------------------------------------------------------------
    # Backend selection
    # ------------------------------------------------------------------
    def _select_backend(self, context: DetectionContext | None) -> str:
        backend = self._backend
        if context is not None and getattr(context, "config", None) is not None:
            cfg = context.config
            try:
                backend = cfg.detectors.address.backend  # type: ignore[attr-defined]
            except Exception:  # pragma: no cover - defensive
                backend = backend

        backend = backend or "auto"
        if backend == "auto":
            return "usaddress"
        if backend == "usaddress":
            return "usaddress"
        if backend == "libpostal":
            raise NotImplementedError("libpostal backend not implemented")
        raise ValueError(f"unknown address backend: {backend}")

    # ------------------------------------------------------------------
    # usaddress backend implementation
    # ------------------------------------------------------------------
    def _detect_usaddress(self, text: str) -> list[EntitySpan]:
        spans: list[EntitySpan] = []
        pos = 0
        for line in text.splitlines(keepends=True):
            start_raw = pos
            end_raw_no_eol = start_raw + len(line.rstrip("\r\n"))
            pos += len(line)

            start_core = start_raw
            end_core = end_raw_no_eol

            while start_core < end_core and text[start_core] in PREFIX_PUNCT:
                start_core += 1
            while end_core > start_core and text[end_core - 1] in SUFFIX_PUNCT:
                end_core -= 1
            if start_core >= end_core:
                continue

            core_text = text[start_core:end_core]

            match = PREFIX_LABEL_RE.match(core_text)
            trimmed_prefix = False
            if match:
                trimmed_prefix = True
                start_core += match.end()
                core_text = text[start_core:end_core]
                if not core_text:
                    continue
            if not _should_parse_line(core_text):
                continue

            parsed = self._parse_core(core_text)
            if parsed is None:
                continue

            line_info = self._classify_line(parsed.labels)
            if line_info is None:
                continue
            line_kind, confidence, used_labels = line_info

            span_start, span_end = self._find_span(core_text, parsed.tokens, used_labels)

            start = start_core + span_start
            end = start_core + span_end
            span_text = text[start:end]

            normalized = self._normalize(line_kind, parsed.components)

            attrs = {
                "backend": "usaddress",
                "line_kind": line_kind,
                "components": parsed.components,
                "normalized": normalized,
                "trimmed_prefix": trimmed_prefix,
            }

            spans.append(
                EntitySpan(
                    start,
                    end,
                    span_text,
                    EntityLabel.ADDRESS_BLOCK,
                    "address_line",
                    confidence,
                    attrs,
                )
            )

        unique: dict[tuple[int, int], EntitySpan] = {}
        for span in spans:
            key = (span.start, span.end)
            if key not in unique:
                unique[key] = span
        return sorted(unique.values(), key=lambda s: s.start)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _parse_core(self, core_text: str) -> _ParsedLine | None:
        if usaddress is None:
            return None
        try:
            tokens = _parse_usaddr(core_text)
        except Exception:
            return None
        if not tokens:
            return None
        components: dict[str, str] = {}
        for token, label in tokens:
            clean = token.replace(".", "").rstrip(",")
            if label in components:
                components[label] += f" {clean}"
            else:
                components[label] = clean
        labels = {label for _, label in tokens}
        return _ParsedLine(tokens, components, labels)

    def _classify_line(self, labels: set[str]) -> tuple[str, float, Sequence[str]] | None:
        if {"AddressNumber", "StreetName"}.issubset(labels):
            used = [
                label
                for label in (
                    "AddressNumber",
                    "StreetNamePreDirectional",
                    "StreetName",
                    "StreetNamePostType",
                    "StreetNamePostDirectional",
                    "OccupancyType",
                    "OccupancyIdentifier",
                )
                if label in labels
            ]
            return "street", 0.98, used
        if {"USPSBoxType", "USPSBoxID"}.issubset(labels):
            used = [label for label in ("USPSBoxType", "USPSBoxID") if label in labels]
            return "po_box", 0.97, used
        if {"OccupancyType", "OccupancyIdentifier"}.issubset(labels):
            used = [label for label in ("OccupancyType", "OccupancyIdentifier") if label in labels]
            return "unit", 0.90, used
        if {"PlaceName", "StateName"}.issubset(labels):
            used = [label for label in ("PlaceName", "StateName", "ZipCode") if label in labels]
            return "city_state_zip", 0.96, used
        return None

    def _find_span(
        self, core_text: str, tokens: Sequence[tuple[str, str]], used_labels: Iterable[str]
    ) -> tuple[int, int]:
        used_set = set(used_labels)
        first_token: str | None = None
        last_token: str | None = None
        for token, label in tokens:
            if label in used_set:
                if first_token is None:
                    first_token = token
                last_token = token
        if first_token is None or last_token is None:
            return 0, len(core_text)
        start_rel = core_text.find(first_token)
        end_rel = core_text.rfind(last_token)
        if start_rel == -1 or end_rel == -1:
            return 0, len(core_text)
        return start_rel, end_rel + len(last_token)

    def _normalize(self, line_kind: str, components: dict[str, str]) -> str:
        if line_kind == "street":
            order = [
                "AddressNumber",
                "StreetNamePreDirectional",
                "StreetName",
                "StreetNamePostType",
                "StreetNamePostDirectional",
                "OccupancyType",
                "OccupancyIdentifier",
            ]
        elif line_kind == "po_box":
            order = ["USPSBoxType", "USPSBoxID"]
        elif line_kind == "unit":
            order = ["OccupancyType", "OccupancyIdentifier"]
        else:  # city_state_zip
            order = ["PlaceName", "StateName", "ZipCode"]
        return " ".join(components[c] for c in order if c in components).strip()


def get_detector() -> AddressLineDetector:
    """Return an :class:`AddressLineDetector` instance."""

    return AddressLineDetector()
