import importlib.util

import pytest

from redactor.config import load_config
from redactor.detect.base import EntityLabel, EntitySpan
from redactor.link import coref
from redactor.replace.plan_builder import build_replacement_plan


def _make_span(
    text: str,
    label: EntityLabel,
    start: int,
    end: int,
    *,
    entity_id: str | None = None,
) -> EntitySpan:
    return EntitySpan(
        start=start,
        end=end,
        text=text[start:end],
        label=label,
        source="test",
        confidence=1.0,
        entity_id=entity_id,
    )


def test_coref_regex_fallback_merges_names() -> None:
    text = "John Doe said he would pay. Later, Mr. Doe confirmed."
    spans = [
        _make_span(
            text,
            EntityLabel.PERSON,
            text.index("John Doe"),
            text.index("John Doe") + len("John Doe"),
        ),
        _make_span(
            text,
            EntityLabel.PERSON,
            text.index("Mr. Doe"),
            text.index("Mr. Doe") + len("Mr. Doe"),
        ),
    ]
    cfg = load_config()
    cfg.detectors.coref.enabled = True
    cfg.detectors.coref.backend = "regex"

    coref_res = coref.compute_coref(text, spans, cfg)
    assert len(coref_res.mentions) >= 2
    ids = {m.cluster_id for m in coref_res.mentions if m.text in {"John Doe", "Mr. Doe"}}
    assert len(ids) == 1
    assert any(m.is_pronoun for m in coref_res.mentions)

    mapping = coref.unify_with_alias_clusters(spans, coref_res, alias_clusters=None)
    coref.assign_coref_entity_ids(spans, coref_res, mapping)
    assert spans[0].entity_id is not None
    assert spans[0].entity_id == spans[1].entity_id


def test_coref_unify_with_alias_cluster() -> None:
    text = 'John Doe, hereinafter "Morgan". He later signed.'
    john_start = text.index("John Doe")
    john_end = john_start + len("John Doe")
    alias_start = text.index("Morgan")
    alias_end = alias_start + len("Morgan")
    spans = [
        _make_span(text, EntityLabel.PERSON, john_start, john_end, entity_id="C_ALIAS"),
        _make_span(text, EntityLabel.ALIAS_LABEL, alias_start, alias_end, entity_id="C_ALIAS"),
    ]
    cfg = load_config()
    cfg.detectors.coref.enabled = True
    cfg.detectors.coref.backend = "regex"

    coref_res = coref.compute_coref(text, spans, cfg)
    mapping = coref.unify_with_alias_clusters(spans, coref_res, {"C_ALIAS": {}})
    coref.assign_coref_entity_ids(spans, coref_res, mapping)
    cluster_id = next(m.cluster_id for m in coref_res.mentions if m.text == "John Doe")
    assert mapping[cluster_id] == "C_ALIAS"
    assert spans[0].entity_id == "C_ALIAS"


def test_coref_fastcoref_backend() -> None:
    pytest.importorskip("fastcoref")
    text = "John Doe said he would pay. Later, Mr. Doe confirmed."
    spans = [
        _make_span(
            text,
            EntityLabel.PERSON,
            text.index("John Doe"),
            text.index("John Doe") + len("John Doe"),
        ),
        _make_span(
            text,
            EntityLabel.PERSON,
            text.index("Mr. Doe"),
            text.index("Mr. Doe") + len("Mr. Doe"),
        ),
    ]
    cfg = load_config()
    cfg.detectors.coref.enabled = True
    cfg.detectors.coref.backend = "fastcoref"
    coref_res = coref.compute_coref(text, spans, cfg)
    assert coref_res.backend == "fastcoref"
    assert coref_res.mentions
    assert coref_res.clusters


def test_coref_fastcoref_missing() -> None:
    if importlib.util.find_spec("fastcoref") is not None:
        pytest.skip("fastcoref available")
    text = "John Doe said he would pay."
    spans = [
        _make_span(
            text,
            EntityLabel.PERSON,
            text.index("John Doe"),
            text.index("John Doe") + len("John Doe"),
        )
    ]
    cfg = load_config()
    cfg.detectors.coref.enabled = True
    cfg.detectors.coref.backend = "fastcoref"
    cfg.detectors.coref.require = True
    with pytest.raises(RuntimeError):
        coref.compute_coref(text, spans, cfg)


def test_coref_replacement_consistency() -> None:
    text = "John Doe said he would pay. Later, Mr. Doe confirmed."
    spans = [
        _make_span(
            text,
            EntityLabel.PERSON,
            text.index("John Doe"),
            text.index("John Doe") + len("John Doe"),
        ),
        _make_span(
            text,
            EntityLabel.PERSON,
            text.index("Mr. Doe"),
            text.index("Mr. Doe") + len("Mr. Doe"),
        ),
    ]
    cfg = load_config()
    cfg.detectors.coref.enabled = True
    cfg.detectors.coref.backend = "regex"
    coref_res = coref.compute_coref(text, spans, cfg)
    mapping = coref.unify_with_alias_clusters(spans, coref_res, alias_clusters=None)
    coref.assign_coref_entity_ids(spans, coref_res, mapping)
    plan = build_replacement_plan(text, spans, cfg)
    replacements = [p.replacement for p in plan if p.label is EntityLabel.PERSON]
    assert len(replacements) == 2
    # The last names should match ensuring consistent pseudonyms
    assert replacements[0].split()[-1] == replacements[1].split()[-1]
