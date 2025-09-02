"""Alias resolution and propagation.

This module links alias definition spans emitted by
:mod:`redactor.detect.aliases` to their corresponding subjects and synthesises
additional alias mention spans.  Each subject and its aliases are grouped into a
stable entity cluster so later stages can apply consistent replacements.  The
propagation scope for an alias runs from the end of its definition until the
next alias definition for the same subject or the end of the document.

Role labels such as ``Buyer`` may optionally be preserved depending on the
configuration.  When ``cfg.redact.alias_labels`` is set to ``"keep_roles"``,
role aliases are still linked to their subjects but synthesised mention spans
are flagged with ``skip_replacement`` so downstream replacement stages can keep
them verbatim.  Non-role aliases are always propagated and replaced.

Conflict resolution between overlapping spans is deferred to the global span
merger; this module simply emits additional spans where appropriate.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Dict, Iterable, List, Tuple, cast

from redactor.config import ConfigModel
from redactor.detect.base import EntityLabel, EntitySpan
from redactor.preprocess.layout_reconstructor import (
    LineIndex,
    build_line_index,
    find_line_for_char,
)
from redactor.pseudo import seed

__all__ = ["resolve_aliases"]


# ---------------------------------------------------------------------------
# Helper type aliases
# ---------------------------------------------------------------------------

SpanRange = Tuple[int, int]


@dataclass(slots=True)
class AliasCluster:
    primary_surface: str
    aliases: List[str]
    role_aliases: List[str]
    subject_spans: List[Dict[str, int]]
    alias_def_spans: List[Dict[str, int]]
    alias_mention_spans: List[Dict[str, int]]
    entity_type: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_alias_defs(spans: List[EntitySpan]) -> List[EntitySpan]:
    """Return alias definition spans emitted by the alias detector."""

    return [sp for sp in spans if sp.label is EntityLabel.ALIAS_LABEL and sp.source == "aliases"]


def _entity_type_from_label(label: EntityLabel) -> str:
    if label is EntityLabel.PERSON:
        return "person"
    if label in {EntityLabel.ORG, EntityLabel.BANK_ORG}:
        return "org"
    return "unknown"


def _find_subject_for_def(
    def_span: EntitySpan,
    spans: List[EntitySpan],
    text: str,
    line_index: LineIndex | None = None,
) -> Tuple[str | None, SpanRange | None, str, str | None]:
    """Determine subject information for an alias definition."""

    if line_index is None:
        line_index = build_line_index(text)

    subject_span_dict = cast(Dict[str, int] | None, def_span.attrs.get("subject_span"))
    subject_text_attr = cast(str | None, def_span.attrs.get("subject_text"))
    if subject_span_dict and subject_text_attr:
        span_tuple: SpanRange = (
            int(subject_span_dict["start"]),
            int(subject_span_dict["end"]),
        )
        entity_type = "unknown"
        existing_id: str | None = None
        for sp in spans:
            if (
                sp.start < span_tuple[1]
                and sp.end > span_tuple[0]
                and sp.label
                in {
                    EntityLabel.PERSON,
                    EntityLabel.ORG,
                    EntityLabel.BANK_ORG,
                }
            ):
                entity_type = _entity_type_from_label(sp.label)
                existing_id = sp.entity_id
                break
        return subject_text_attr, span_tuple, entity_type, existing_id

    # search for nearest PERSON/ORG/BANK_ORG span
    def_line = find_line_for_char(def_span.start, line_index)
    best: Tuple[int, EntitySpan] | None = None
    for sp in spans:
        if sp.label not in {EntityLabel.PERSON, EntityLabel.ORG, EntityLabel.BANK_ORG}:
            continue
        line_no = find_line_for_char(sp.start, line_index)
        if line_no > def_line or def_line - line_no > 1:
            continue
        distance = max(0, def_span.start - sp.end)
        if sp.end > def_span.start or distance <= 80:
            if best is None or distance < best[0]:
                best = (distance, sp)
    if best is not None:
        sp = best[1]
        entity_type = _entity_type_from_label(sp.label)
        return text[sp.start : sp.end], (sp.start, sp.end), entity_type, sp.entity_id

    subject_guess = cast(str | None, def_span.attrs.get("subject_guess"))
    guess_line = cast(int | None, def_span.attrs.get("subject_guess_line"))
    if subject_guess:
        if guess_line is not None and 0 <= guess_line < len(line_index):
            g_start, g_end, _ = line_index[guess_line]
            for sp in spans:
                if sp.label not in {
                    EntityLabel.PERSON,
                    EntityLabel.ORG,
                    EntityLabel.BANK_ORG,
                }:
                    continue
                if sp.start < g_end and sp.end > g_start:
                    entity_type = _entity_type_from_label(sp.label)
                    return text[sp.start : sp.end], (sp.start, sp.end), entity_type, sp.entity_id
        return subject_guess, None, "unknown", None
    return None, None, "unknown", None


def _cluster_id_for(subject_key: str, text: str, cfg: ConfigModel) -> str:
    """Return a deterministic cluster identifier for ``subject_key``."""

    return seed.scoped_stable_id_for_text("ENTITY_CLUSTER", subject_key, text, cfg, length=20)


def _register_cluster(
    clusters: Dict[str, AliasCluster],
    cluster_id: str,
    subject_text: str,
    subject_span: SpanRange | None,
    entity_type: str,
) -> None:
    """Ensure ``cluster_id`` exists in ``clusters`` and update its metadata."""

    cluster = clusters.get(cluster_id)
    if cluster is None:
        cluster = AliasCluster(
            primary_surface=subject_text,
            aliases=[],
            role_aliases=[],
            subject_spans=[],
            alias_def_spans=[],
            alias_mention_spans=[],
            entity_type=entity_type,
        )
        clusters[cluster_id] = cluster
    if not cluster.primary_surface and subject_text:
        cluster.primary_surface = subject_text
    if subject_span is not None:
        span_rec = {"start": subject_span[0], "end": subject_span[1]}
        if span_rec not in cluster.subject_spans:
            cluster.subject_spans.append(span_rec)
    if cluster.entity_type == "unknown" and entity_type != "unknown":
        cluster.entity_type = entity_type


def _add_alias_to_cluster(
    clusters: Dict[str, AliasCluster],
    cluster_id: str,
    alias: str,
    is_role: bool,
    def_span: EntitySpan,
) -> None:
    """Record ``alias`` and its definition span for ``cluster_id``."""

    cluster = clusters[cluster_id]
    if alias not in cluster.aliases:
        cluster.aliases.append(alias)
    if is_role and alias not in cluster.role_aliases:
        cluster.role_aliases.append(alias)
    cluster.alias_def_spans.append({"start": def_span.start, "end": def_span.end})


def _scan_alias_mentions(
    text: str,
    alias: str,
    start_offset: int,
    end_stop: int | None,
    occupied_ranges: List[SpanRange],
) -> List[SpanRange]:
    """Return future occurrences of ``alias`` avoiding ``occupied_ranges``."""

    pattern = re.compile(rf"\b{re.escape(alias)}\b")
    stop = end_stop if end_stop is not None else len(text)
    matches: List[SpanRange] = []
    for m in pattern.finditer(text, start_offset, stop):
        start, end = m.span()
        overlap = any(s < end and e > start for s, e in occupied_ranges)
        if overlap:
            continue
        matches.append((start, end))
    return matches


def _synthesize_alias_mention(
    alias: str,
    cluster_id: str,
    start: int,
    end: int,
    is_role: bool,
    policy_keep_roles: bool,
) -> EntitySpan:
    """Create an alias mention span for propagation."""

    alias_kind = "role" if is_role else "nickname"
    attrs = {
        "alias": alias,
        "alias_kind": alias_kind,
        "trigger": "propagation",
        "cluster_id": cluster_id,
        "role_flag": is_role,
        "skip_replacement": policy_keep_roles and is_role,
    }
    return EntitySpan(
        start,
        end,
        alias,
        EntityLabel.ALIAS_LABEL,
        "alias_resolver",
        0.96,
        attrs,
        entity_id=cluster_id,
    )


def _assign_entity_id_to_subject_spans(
    spans: List[EntitySpan], subject_span: SpanRange, cluster_id: str
) -> None:
    """Assign ``cluster_id`` to subject spans overlapping ``subject_span``."""

    subj_start, subj_end = subject_span
    for i, sp in enumerate(spans):
        if sp.label not in {
            EntityLabel.PERSON,
            EntityLabel.ORG,
            EntityLabel.BANK_ORG,
        }:
            continue
        if sp.start < subj_end and sp.end > subj_start:
            if sp.entity_id is None:
                spans[i] = replace(sp, entity_id=cluster_id)


def _occupied_ranges(spans: Iterable[EntitySpan]) -> List[SpanRange]:
    """Return sorted ``(start, end)`` tuples for ``spans``."""

    return sorted([(sp.start, sp.end) for sp in spans])


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve_aliases(
    text: str, spans: List[EntitySpan], cfg: ConfigModel
) -> Tuple[List[EntitySpan], Dict[str, Dict[str, object]]]:
    """Resolve alias definitions and propagate later mentions.

    Parameters
    ----------
    text:
        Original document text.
    spans:
        Detected entity spans, including alias definition spans from the
        alias detector and other entity detectors.
    cfg:
        Active configuration model controlling role alias policy.

    Returns
    -------
    tuple
        ``(updated_spans, clusters)`` where ``updated_spans`` includes the
        original spans plus any synthesised alias mention spans and ``clusters``
        contains metadata for each entity cluster.
    """

    alias_defs = _extract_alias_defs(spans)
    if not alias_defs:
        return list(spans), {}

    line_index = build_line_index(text)
    idx_map = {id(sp): i for i, sp in enumerate(spans)}
    updated_spans = list(spans)

    # Gather definition info first
    @dataclass
    class _DefInfo:
        span: EntitySpan
        idx: int
        alias: str
        is_role: bool
        subject_text: str | None
        subject_span: SpanRange | None
        entity_type: str
        cluster_id: str
        next_start: int | None = None

    def_infos: List[_DefInfo] = []
    for def_sp in sorted(alias_defs, key=lambda s: s.start):
        alias = cast(str, def_sp.attrs.get("alias", def_sp.text))
        is_role = bool(def_sp.attrs.get("role_flag", False))
        subject_text, subject_span, entity_type, existing_id = _find_subject_for_def(
            def_sp, spans, text, line_index
        )
        subject_key = subject_text if subject_text is not None else alias
        cluster_id = existing_id or _cluster_id_for(subject_key, text, cfg)
        def_infos.append(
            _DefInfo(
                span=def_sp,
                idx=idx_map[id(def_sp)],
                alias=alias,
                is_role=is_role,
                subject_text=subject_text,
                subject_span=subject_span,
                entity_type=entity_type,
                cluster_id=cluster_id,
            )
        )

    # Compute next definition start for each cluster
    by_cluster: Dict[str, List[_DefInfo]] = {}
    for info in def_infos:
        by_cluster.setdefault(info.cluster_id, []).append(info)
    for infos in by_cluster.values():
        infos.sort(key=lambda i: i.span.start)
        for i, info in enumerate(infos[:-1]):
            info.next_start = infos[i + 1].span.start

    clusters: Dict[str, AliasCluster] = {}
    policy_keep_roles = cfg.redact.alias_labels == "keep_roles"
    occupied = _occupied_ranges(updated_spans)
    synthesized: List[EntitySpan] = []

    # Process definitions in document order
    for info in sorted(def_infos, key=lambda i: i.span.start):
        cluster_id = info.cluster_id
        # update definition span
        attrs = dict(info.span.attrs)
        attrs["cluster_id"] = cluster_id
        attrs["is_definition"] = True
        def_span_updated = replace(info.span, attrs=attrs, entity_id=cluster_id)
        updated_spans[info.idx] = def_span_updated

        # assign entity id to subject spans
        if info.subject_span is not None:
            _assign_entity_id_to_subject_spans(updated_spans, info.subject_span, cluster_id)

        # register cluster and alias
        subject_surface = info.subject_text or info.alias
        _register_cluster(
            clusters, cluster_id, subject_surface, info.subject_span, info.entity_type
        )
        _add_alias_to_cluster(clusters, cluster_id, info.alias, info.is_role, def_span_updated)

        scope_start = info.span.end
        scope_end = info.next_start
        cluster_aliases = clusters[cluster_id].aliases
        role_aliases = set(clusters[cluster_id].role_aliases)
        for alias in cluster_aliases:
            ranges = _scan_alias_mentions(text, alias, scope_start, scope_end, occupied)
            for start, end in ranges:
                mention_span = _synthesize_alias_mention(
                    alias,
                    cluster_id,
                    start,
                    end,
                    alias in role_aliases,
                    policy_keep_roles,
                )
                synthesized.append(mention_span)
                occupied.append((start, end))
                clusters[cluster_id].alias_mention_spans.append({"start": start, "end": end})

    result = updated_spans + synthesized
    result.sort(key=lambda s: s.start)
    clusters_out: Dict[str, Dict[str, object]] = {
        cid: {
            "primary_surface": cl.primary_surface,
            "aliases": cl.aliases,
            "role_aliases": cl.role_aliases,
            "subject_spans": cl.subject_spans,
            "alias_def_spans": cl.alias_def_spans,
            "alias_mention_spans": cl.alias_mention_spans,
            "entity_type": cl.entity_type,
        }
        for cid, cl in clusters.items()
    }
    return result, clusters_out
