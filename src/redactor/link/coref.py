"""Lightweight coreference linking for PERSON spans.

This module assigns stable cluster identifiers to spans referring to the same
entity so that different name variants share the same pseudonym.  Coreference is
optional and disabled by default.  When enabled, two backends are available:

* ``fastcoref`` – a neural model providing full document clustering.  It is an
  optional dependency installed via ``.[coref]``.  When unavailable, the
  heuristics fall back to regex rules unless ``require`` is set in the
  configuration.
* ``regex`` – a lightweight fallback that links pronouns and short name
  variants within a two‑sentence window.  The heuristic only touches existing
  PERSON spans; it never creates new spans for pronouns.

Cluster identifiers are derived from the canonical mention text using the
``scoped_stable_id_for_text`` helper which hashes the canonical surface together
with the document scope and pseudonym seed.  Mentions are exposed via
``CorefMention`` records and cluster metadata summarises surfaces seen for each
cluster.  Downstream stages use these IDs to ensure consistent pseudonyms.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any, Iterable, List, Tuple, cast

from redactor.config import ConfigModel
from redactor.detect.base import EntityLabel, EntitySpan
from redactor.preprocess.segmenter import segment_sentences
from redactor.pseudo import seed

__all__ = [
    "CorefMention",
    "CorefResult",
    "compute_coref",
    "unify_with_alias_clusters",
    "assign_coref_entity_ids",
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class CorefMention:
    start: int
    end: int
    text: str
    cluster_id: str
    is_pronoun: bool
    backend: str


@dataclass(slots=True, frozen=True)
class CorefResult:
    mentions: list[CorefMention]
    clusters: dict[str, dict[str, object]]
    backend: str
    mode: str


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


_PRONOUN_RE = re.compile(
    r"\b(" "he|she|they|him|her|his|hers|their|theirs|mr\.|mrs\.|ms\.|mx\.|dr\." r")\b",
    re.IGNORECASE,
)


def _is_pronoun(text: str) -> bool:
    return bool(_PRONOUN_RE.fullmatch(text.lower()))


# ---------------------------------------------------------------------------
# fastcoref backend
# ---------------------------------------------------------------------------


def _compute_fastcoref(text: str, cfg: ConfigModel) -> CorefResult:
    from fastcoref import FCoref

    model = FCoref()  # default model, CPU when no GPU
    try:
        doc = model.predict(text)
    except Exception:
        # some versions expect a list
        doc = model.predict(texts=[text])[0]
    raw_clusters: Iterable[Iterable[Tuple[int, int]]] = doc.get_clusters(as_strings=False)

    mentions: list[CorefMention] = []
    clusters: dict[str, dict[str, Any]] = {}
    for cluster in raw_clusters:
        surfaces: List[str] = []
        cand_canonical = None
        max_len = -1
        m_records: List[Tuple[int, int, str, bool]] = []
        for start, end in cluster:
            surface = text[start:end]
            lower = surface.lower()
            surfaces.append(lower)
            is_pron = _is_pronoun(lower)
            if not is_pron and len(surface) > max_len:
                cand_canonical = surface
                max_len = len(surface)
            m_records.append((start, end, surface, is_pron))
        if cand_canonical is None and m_records:
            cand_canonical = m_records[0][2]
        canonical = cand_canonical or ""
        cluster_id = seed.scoped_stable_id_for_text(
            "COREF", canonical.lower(), text, cfg, length=20
        )
        clusters[cluster_id] = {
            "surfaces": sorted(set(surfaces)),
            "canonical": canonical,
            "backend": "fastcoref",
            "size": len(m_records),
        }
        for start, end, surface, is_pron in m_records:
            mentions.append(
                CorefMention(
                    start=start,
                    end=end,
                    text=surface,
                    cluster_id=cluster_id,
                    is_pronoun=is_pron,
                    backend="fastcoref",
                )
            )
    return CorefResult(mentions=mentions, clusters=clusters, backend="fastcoref", mode="fastcoref")


# ---------------------------------------------------------------------------
# Regex fallback backend
# ---------------------------------------------------------------------------


def _update_cluster(
    clusters: dict[str, dict[str, object]],
    cluster_id: str,
    canonical: str,
    surface: str,
    backend: str,
) -> None:
    rec = clusters.setdefault(
        cluster_id,
        {"surfaces": [], "canonical": canonical, "backend": backend, "size": 0},
    )
    lower = surface.lower()
    surfaces = cast(list[str], rec["surfaces"])
    if lower not in surfaces:
        surfaces.append(lower)
    rec["size"] = cast(int, rec["size"]) + 1


def _compute_regex(text: str, spans: list[EntitySpan], cfg: ConfigModel) -> CorefResult:
    person_spans = [sp for sp in spans if sp.label is EntityLabel.PERSON]
    person_spans.sort(key=lambda sp: sp.start)
    sentences = segment_sentences(text)

    mentions: list[CorefMention] = []
    clusters: dict[str, dict[str, object]] = {}
    cluster_by_span: dict[int, str] = {}
    canonical_by_cluster: dict[str, str] = {}

    span_idx = 0
    prev_last: EntitySpan | None = None

    for sent in sentences:
        sent_persons: list[EntitySpan] = []
        while span_idx < len(person_spans) and person_spans[span_idx].start < sent.end:
            sp = person_spans[span_idx]
            if sp.end <= sent.end:
                sent_persons.append(sp)
                span_idx += 1
            else:
                break

        events: list[Tuple[int, str, object]] = []
        for sp in sent_persons:
            events.append((sp.start, "person", sp))
        for m in _PRONOUN_RE.finditer(sent.text):
            events.append((sent.start + m.start(), "pronoun", m))
        events.sort(key=lambda t: t[0])

        current_last: EntitySpan | None = None
        candidate: EntitySpan | None = prev_last

        for pos, kind, obj in events:
            if kind == "person":
                sp = obj  # type: ignore[assignment]
                cluster_id: str
                canonical: str
                if candidate is not None and candidate.text.split()[-1] == sp.text.split()[-1]:
                    cluster_id = cluster_by_span[id(candidate)]
                    canonical = canonical_by_cluster[cluster_id]
                else:
                    canonical = sp.text
                    cluster_id = seed.scoped_stable_id_for_text(
                        "COREF", canonical.lower(), text, cfg, length=20
                    )
                cluster_by_span[id(sp)] = cluster_id
                canonical_by_cluster.setdefault(cluster_id, canonical)
                mentions.append(
                    CorefMention(
                        start=sp.start,
                        end=sp.end,
                        text=sp.text,
                        cluster_id=cluster_id,
                        is_pronoun=False,
                        backend="regex",
                    )
                )
                _update_cluster(clusters, cluster_id, canonical, sp.text, "regex")
                current_last = sp
                candidate = sp
            else:  # pronoun
                m = obj  # type: ignore[assignment]
                if candidate is None:
                    continue
                cluster_id = cluster_by_span[id(candidate)]
                canonical = canonical_by_cluster[cluster_id]
                token = m.group(0)
                start = pos
                end = pos + len(token)
                mentions.append(
                    CorefMention(
                        start=start,
                        end=end,
                        text=token,
                        cluster_id=cluster_id,
                        is_pronoun=True,
                        backend="regex",
                    )
                )
                _update_cluster(clusters, cluster_id, canonical, token, "regex")

        # surname-only tokens
        surname_source = current_last or prev_last
        if surname_source is not None:
            parts = surname_source.text.split()
            if len(parts) >= 2:
                surname = parts[-1]
                pattern = re.compile(rf"\b{re.escape(surname)}\b")
                for m in pattern.finditer(sent.text):
                    start = sent.start + m.start()
                    end = sent.start + m.end()
                    if any(start < sp.end and end > sp.start for sp in sent_persons):
                        continue
                    cluster_id = cluster_by_span[id(surname_source)]
                    canonical = canonical_by_cluster[cluster_id]
                    token = m.group(0)
                    mentions.append(
                        CorefMention(
                            start=start,
                            end=end,
                            text=token,
                            cluster_id=cluster_id,
                            is_pronoun=True,
                            backend="regex",
                        )
                    )
                    _update_cluster(clusters, cluster_id, canonical, token, "regex")

        if current_last is not None:
            prev_last = current_last

    return CorefResult(mentions=mentions, clusters=clusters, backend="regex", mode="regex")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_coref(text: str, spans: list[EntitySpan], cfg: ConfigModel) -> CorefResult:
    """Compute coreference clusters for ``spans`` in ``text``."""

    settings = cfg.detectors.coref
    if not settings.enabled:
        return CorefResult([], {}, backend="regex", mode=settings.backend)

    backend = settings.backend
    if backend in {"auto", "fastcoref"}:
        try:
            import fastcoref  # noqa: F401  # type: ignore

            return _compute_fastcoref(text, cfg)
        except Exception as exc:
            if backend == "fastcoref" and settings.require:
                raise RuntimeError(
                    "fastcoref backend requested but not available. "
                    "Install with 'pip install .[coref]'."
                ) from exc
            backend = "regex"

    return _compute_regex(text, spans, cfg)


def unify_with_alias_clusters(
    spans: list[EntitySpan],
    coref: CorefResult,
    alias_clusters: dict[str, dict[str, object]] | None,
) -> dict[str, str]:
    """Map coref cluster IDs to existing alias cluster IDs when overlapping."""

    mapping: dict[str, str] = {}
    if not coref.mentions:
        return mapping

    alias_ids = set(alias_clusters.keys()) if alias_clusters else set()
    for mention in coref.mentions:
        for sp in spans:
            if (
                sp.entity_id
                and sp.label in {EntityLabel.PERSON, EntityLabel.ORG, EntityLabel.BANK_ORG}
                and sp.entity_id in alias_ids
                and sp.start < mention.end
                and sp.end > mention.start
            ):
                mapping.setdefault(mention.cluster_id, sp.entity_id)
    return mapping


def assign_coref_entity_ids(
    spans: list[EntitySpan], coref: CorefResult, mapping: dict[str, str] | None = None
) -> None:
    """Assign entity IDs to PERSON spans based on coref clusters."""

    if not coref.mentions:
        return
    map_dict = mapping or {}
    mention_index = {(m.start, m.end): m for m in coref.mentions if not m.is_pronoun}
    for i, sp in enumerate(spans):
        if sp.label is not EntityLabel.PERSON or sp.entity_id is not None:
            continue
        key = (sp.start, sp.end)
        m = mention_index.get(key)
        if m is not None:
            new_id = map_dict.get(m.cluster_id, m.cluster_id)
            spans[i] = replace(sp, entity_id=new_id)
