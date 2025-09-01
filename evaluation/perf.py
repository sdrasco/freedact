"""Lightweight profiling harness for pipeline performance measurements.

This module exposes two helpers:

``profile_pipeline``
    Time individual stages of the redaction pipeline for a single piece of
    text using the same in-process wiring as the CLI (no I/O).

``profile_fixtures``
    Convenience wrapper that loads evaluation fixtures, synthesises larger
    documents by repeating their contents and returns per-stage timings for
    each.

Neither function prints or logs; results are returned to the caller so tests or
tools can aggregate them as needed.
"""

from __future__ import annotations

import os
from time import perf_counter
from typing import Dict, List

from evaluation.fixtures import loader as fixtures_loader
from redactor.cli import _run_detectors
from redactor.config import ConfigModel, load_config
from redactor.detect.base import DetectionContext
from redactor.link import alias_resolver, coref, span_merger
from redactor.preprocess import layout_reconstructor
from redactor.preprocess.normalizer import normalize
from redactor.replace.applier import apply_plan
from redactor.replace.plan_builder import build_replacement_plan
from redactor.utils.textspan import build_line_starts
from redactor.verify import scanner

__all__ = ["profile_pipeline", "profile_fixtures"]


def profile_pipeline(text: str, cfg: ConfigModel) -> Dict[str, float]:
    """Return per-stage timings (seconds) for running the pipeline on ``text``.

    Stages closely mirror the CLI implementation.  ``total`` measures the full
    wall clock duration; values are floats expressed in seconds.  Coreference is
    only executed when enabled in ``cfg`` and otherwise records ``0.0``.
    """

    timings: Dict[str, float] = {}
    total_start = perf_counter()

    t0 = perf_counter()
    norm = normalize(text)
    normalized = norm.text
    timings["normalize"] = perf_counter() - t0

    line_starts = build_line_starts(normalized)
    context = DetectionContext(locale=cfg.locale, line_starts=line_starts, config=cfg)

    t0 = perf_counter()
    spans = _run_detectors(normalized, cfg, context)
    timings["detect"] = perf_counter() - t0

    t0 = perf_counter()
    spans = layout_reconstructor.merge_address_lines_into_blocks(normalized, spans)
    timings["address_merge"] = perf_counter() - t0

    t0 = perf_counter()
    spans, clusters = alias_resolver.resolve_aliases(normalized, spans, cfg)
    timings["alias_resolve"] = perf_counter() - t0

    if cfg.detectors.coref.enabled:
        t0 = perf_counter()
        coref_result = coref.compute_coref(normalized, spans, cfg)
        mapping = coref.unify_with_alias_clusters(spans, coref_result, clusters)
        coref.assign_coref_entity_ids(spans, coref_result, mapping)
        timings["coref"] = perf_counter() - t0
    else:
        timings["coref"] = 0.0

    t0 = perf_counter()
    merged = span_merger.merge_spans(spans, cfg)
    timings["merge_spans"] = perf_counter() - t0

    t0 = perf_counter()
    plan = build_replacement_plan(normalized, merged, cfg, clusters=clusters)
    timings["plan_build"] = perf_counter() - t0

    t0 = perf_counter()
    redacted, applied = apply_plan(normalized, plan)
    timings["apply"] = perf_counter() - t0

    t0 = perf_counter()
    scanner.scan_text(redacted, cfg, applied_plan=applied)
    timings["verify"] = perf_counter() - t0

    timings["total"] = perf_counter() - total_start
    return timings


def profile_fixtures(
    names: List[str] | None = None,
    *,
    ner: bool = False,
    repeat: int | None = None,
) -> List[Dict[str, object]]:
    """Return timing bundles for fixture texts.

    Parameters
    ----------
    names:
        Optional list of fixture basenames.  When ``None`` all fixtures are
        profiled.
    ner:
        Enable the NER detector in the configuration.
    repeat:
        Number of times to repeat each fixture's content when constructing the
        synthetic profiling text.  ``None`` consults the ``REDACTOR_PERF_REPEAT``
        environment variable and falls back to ``10``.
    """

    all_names = fixtures_loader.list_fixtures()
    selected = all_names if names is None else [n for n in all_names if n in set(names)]

    if repeat is None:
        try:
            repeat = int(os.getenv("REDACTOR_PERF_REPEAT", "10"))
        except ValueError:
            repeat = 10

    cfg = load_config()
    cfg.detectors.ner.enabled = ner

    results: List[Dict[str, object]] = []
    for name in selected:
        text, _ann = fixtures_loader.load_fixture(name)
        synthetic = "\n\n".join(text for _ in range(repeat))
        stages = profile_pipeline(synthetic, cfg)
        results.append(
            {
                "name": name,
                "chars": len(synthetic),
                "stages": stages,
                "ner": ner,
                "repeat": repeat,
            }
        )
    return results


if __name__ == "__main__":  # pragma: no cover - convenience wrapper
    import argparse

    parser = argparse.ArgumentParser(description="Profile evaluation fixtures")
    parser.add_argument("--names", type=str, default=None, help="Comma separated fixture names")
    parser.add_argument("--ner", action="store_true", help="Enable NER detector")
    parser.add_argument("--repeat", type=int, default=None, help="Repeat count")
    args = parser.parse_args()

    names_arg = args.names.split(",") if args.names else None
    out = profile_fixtures(names_arg, ner=args.ner, repeat=args.repeat)

    # Simple plain text table
    header = f"{'name':<20} {'chars':>6} {'repeat':>6} {'ner':>3} {'total_ms':>9}"
    print(header)
    print("-" * len(header))
    for item in out:
        total_ms = item["stages"]["total"] * 1000.0  # type: ignore[index]
        print(
            f"{item['name']:<20} {item['chars']:>6} {item['repeat']:>6} {str(item['ner']):>3} {total_ms:>9.1f}"
        )
