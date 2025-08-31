"""Merge overlapping spans using precedence and deterministic tie‑breakers.

This module resolves conflicts between detectors by selecting a single
non‑overlapping set of :class:`~redactor.detect.base.EntitySpan` objects.  The
algorithm is intentionally *greedy* and *best‑first*:

1. Spans that clearly do not make sense (``end <= start``) are filtered out
   defensively.
2. Exact duplicates – spans sharing ``[start, end]`` and label – are collapsed
   so the strongest candidate survives deterministically.
3. Remaining spans are sorted by a priority key that encodes configured
   precedence, length, confidence and stable tie‑breakers.
4. A single sweep keeps a span only if it does not overlap an already accepted
   span.  Spans follow the half‑open interval convention ``[start, end)`` so two
   spans touching at their boundaries are considered non‑overlapping.

The priority key is ``(precedence, -length, -confidence, start, label_name,
source, span_id)``.  Earlier precedence wins; longer spans beat shorter ones; a
higher confidence score breaks further ties.  If all of those are equal we fall
back to the original ``start`` and ``label`` so ordering remains deterministic.

Precedence is controlled globally through ``cfg.precedence`` – a list of label
names ordered from strongest to weakest.  Modifying this configuration allows
tests or users to change conflict resolution policy without touching the code.

Why greedy?  We prefer to keep human‑sized logic here and avoid splitting or
trimming spans.  Downstream components expect complete, coherent entities (e.g.
"John Doe" rather than a partial "John").

Address blocks are a good example: detectors may produce individual
``ADDRESS_BLOCK`` spans for each line and a merged multi‑line block covering the
entire address.  The tie‑breaker favouring longer spans ensures the merged block
prevails without any special‑casing.
"""

from __future__ import annotations

import hashlib
from typing import Dict, Iterable, Tuple

from redactor.config.schema import ConfigModel
from redactor.detect.base import EntityLabel, EntitySpan

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

_UNKNOWN_PRECEDENCE = 10_000


def _precedence_index(label: EntityLabel, cfg: ConfigModel) -> int:
    """Return precedence rank for ``label`` using ``cfg``.

    Labels appearing earlier in ``cfg.precedence`` receive smaller (stronger)
    ranks.  Names in the configuration that do not correspond to a known
    :class:`EntityLabel` are ignored.  Unknown labels default to a very large
    rank so that configured labels always take precedence.
    """

    mapping: Dict[str, int] = {
        name: idx for idx, name in enumerate(cfg.precedence) if name in EntityLabel.__members__
    }
    return mapping.get(label.name, _UNKNOWN_PRECEDENCE)


def _priority_key(span: EntitySpan, cfg: ConfigModel) -> Tuple[int, int, float, int, str, str, str]:
    """Return a tuple ranking ``span`` from strongest to weakest."""

    precedence = _precedence_index(span.label, cfg)
    length = span.end - span.start
    confidence = round(span.confidence, 6)
    label_name = span.label.name
    span_id = span.span_id
    if span_id is None:
        digest = hashlib.sha1(
            f"{span.start}:{span.end}:{label_name}:{span.source}:{span.text[:16]}".encode("utf-8")
        ).hexdigest()
        span_id = digest
    return (
        precedence,
        -length,
        -confidence,
        span.start,
        label_name,
        span.source,
        span_id,
    )


def _dedupe_identical_ranges(spans: list[EntitySpan]) -> list[EntitySpan]:
    """Collapse exact ``[start, end]`` duplicates keeping the strongest span."""

    best: Dict[Tuple[int, int, EntityLabel], Tuple[int, EntitySpan]] = {}
    for idx, span in enumerate(spans):
        key = (span.start, span.end, span.label)
        if key not in best:
            best[key] = (idx, span)
            continue
        prev_idx, prev_span = best[key]
        if span.confidence > prev_span.confidence:
            best[key] = (idx, span)
        elif span.confidence == prev_span.confidence:
            if span.source < prev_span.source:
                best[key] = (idx, span)
            # if both confidence and source are equal, keep the earlier span
    # Return spans sorted by their original position
    return [span for _, span in sorted(best.values(), key=lambda t: t[0])]


def _overlaps(a: EntitySpan, b: EntitySpan) -> bool:
    """Return ``True`` if spans ``a`` and ``b`` overlap."""

    return not (a.end <= b.start or b.end <= a.start)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def merge_spans(spans: Iterable[EntitySpan], cfg: ConfigModel) -> list[EntitySpan]:
    """Return a new list of non‑overlapping spans sorted by ``start``.

    Spans are evaluated using a greedy best‑first approach.  Stronger spans
    according to ``cfg.precedence`` and the deterministic priority key are kept
    while weaker, overlapping spans are discarded.
    """

    # Filter out obviously invalid spans defensively
    valid_spans = [s for s in spans if s.end > s.start]

    # Collapse duplicates sharing start/end and label
    deduped = _dedupe_identical_ranges(valid_spans)

    # Sort strongest first
    ordered = sorted(deduped, key=lambda s: _priority_key(s, cfg))

    kept: list[EntitySpan] = []
    for cand in ordered:
        if any(_overlaps(cand, k) for k in kept):
            continue
        kept.append(cand)

    # Final output sorted by start position
    kept.sort(key=lambda s: s.start)
    return kept


__all__ = ["merge_spans"]
