from __future__ import annotations

import pytest

from redactor.config import ConfigModel, load_config
from redactor.detect.base import EntityLabel, EntitySpan
from redactor.link import resolve_aliases


@pytest.fixture()
def cfg() -> ConfigModel:
    return load_config()


def _person_span(text: str, name: str) -> EntitySpan:
    start = text.index(name)
    end = start + len(name)
    return EntitySpan(start, end, name, EntityLabel.PERSON, "ner", 0.9, {})


def _org_span(text: str, name: str) -> EntitySpan:
    start = text.index(name)
    end = start + len(name)
    return EntitySpan(start, end, name, EntityLabel.ORG, "ner", 0.9, {})


def _alias_def(
    text: str,
    alias: str,
    *,
    subject_text: str | None = None,
    subject_span: tuple[int, int] | None = None,
    subject_guess: str | None = None,
    role: bool = False,
) -> EntitySpan:
    start = text.index(alias)
    end = start + len(alias)
    attrs: dict[str, object] = {
        "alias": alias,
        "alias_kind": "role" if role else "nickname",
        "trigger": "hereinafter",
        "quote_style": '""',
        "subject_text": subject_text,
        "subject_span": (
            {"start": subject_span[0], "end": subject_span[1]} if subject_span else None
        ),
        "subject_guess": subject_guess,
        "subject_guess_line": 0,
        "scope_hint": "same_line",
        "confidence": 0.99,
        "role_flag": role,
    }
    return EntitySpan(start, end, alias, EntityLabel.ALIAS_LABEL, "aliases", 0.99, attrs)


def test_basic_nickname_propagation(cfg: ConfigModel) -> None:
    text = 'John Doe, hereinafter "Morgan". Later Morgan met Buyer.'
    person = _person_span(text, "John Doe")
    alias_def = _alias_def(
        text,
        "Morgan",
        subject_text="John Doe",
        subject_span=(0, len("John Doe")),
    )
    spans = [person, alias_def]

    out_spans, clusters = resolve_aliases(text, spans, cfg)

    assert len(clusters) == 1
    cluster_id = next(iter(clusters))
    john_span = next(s for s in out_spans if s.label is EntityLabel.PERSON)
    def_span = next(s for s in out_spans if s.source == "aliases")
    mentions = [s for s in out_spans if s.source == "alias_resolver"]

    assert john_span.entity_id == cluster_id
    assert def_span.entity_id == cluster_id
    assert def_span.attrs["is_definition"] is True
    assert mentions and all(m.entity_id == cluster_id for m in mentions)


def test_role_alias_keep_roles(cfg: ConfigModel) -> None:
    cfg.redact.alias_labels = "keep_roles"
    text = 'Acme LLC (hereinafter "Buyer"). Buyer shall pay.'
    org = _org_span(text, "Acme LLC")
    alias_def = _alias_def(
        text,
        "Buyer",
        subject_text="Acme LLC",
        subject_span=(0, len("Acme LLC")),
        role=True,
    )
    spans = [org, alias_def]
    out_spans, clusters = resolve_aliases(text, spans, cfg)
    cluster_id = next(iter(clusters))

    org_span = next(s for s in out_spans if s.label is EntityLabel.ORG)
    assert org_span.entity_id == cluster_id

    mention = next(s for s in out_spans if s.source == "alias_resolver")
    assert mention.attrs["skip_replacement"] is True
    assert clusters[cluster_id]["role_aliases"] == ["Buyer"]


def test_alias_next_line_subject_guess(cfg: ConfigModel) -> None:
    text = 'John Doe\nHereinafter "Morgan"\nLater Morgan went.'
    person = _person_span(text, "John Doe")
    alias_def = _alias_def(
        text,
        "Morgan",
        subject_guess="John Doe",
    )
    spans = [person, alias_def]

    out_spans, clusters = resolve_aliases(text, spans, cfg)
    cluster_id = next(iter(clusters))
    assert any(s.source == "alias_resolver" and s.text == "Morgan" for s in out_spans)
    person_out = next(s for s in out_spans if s.label is EntityLabel.PERSON)
    assert person_out.entity_id == cluster_id


def test_two_aliases_same_subject(cfg: ConfigModel) -> None:
    text = 'John Doe (hereinafter "Morgan"); later (hereinafter "JD"). JD met Morgan.'
    person = _person_span(text, "John Doe")
    john_span = (text.index("John Doe"), text.index("John Doe") + len("John Doe"))
    alias1 = _alias_def(
        text,
        "Morgan",
        subject_text="John Doe",
        subject_span=john_span,
    )
    alias2 = _alias_def(text, "JD", subject_guess="John Doe")
    spans = [person, alias1, alias2]

    out_spans, clusters = resolve_aliases(text, spans, cfg)
    cluster_id = next(iter(clusters))
    mentions = [s.text for s in out_spans if s.source == "alias_resolver"]
    assert {"Morgan", "JD"}.issubset(mentions)
    defs = [s for s in out_spans if s.source == "aliases"]
    assert len({s.entity_id for s in defs}) == 1
    assert all(s.entity_id == cluster_id for s in defs)


def test_no_false_positive_inside_larger_words(cfg: ConfigModel) -> None:
    text = 'John Doe, hereinafter "Morgan". Account at MorganStanley remains.'
    person = _person_span(text, "John Doe")
    alias_def = _alias_def(
        text,
        "Morgan",
        subject_text="John Doe",
        subject_span=(0, len("John Doe")),
    )
    spans = [person, alias_def]
    out_spans, _ = resolve_aliases(text, spans, cfg)
    mentions = [s for s in out_spans if s.source == "alias_resolver"]
    assert mentions == []


def test_punctuation_trimming(cfg: ConfigModel) -> None:
    text = 'John Doe, hereinafter "Morgan". Morgan, went home.'
    person = _person_span(text, "John Doe")
    alias_def = _alias_def(
        text,
        "Morgan",
        subject_text="John Doe",
        subject_span=(0, len("John Doe")),
    )
    spans = [person, alias_def]
    out_spans, _ = resolve_aliases(text, spans, cfg)
    mention = next(s for s in out_spans if s.source == "alias_resolver")
    assert text[mention.end] == ","
    assert mention.text == "Morgan"


def test_offsets_and_dedup(cfg: ConfigModel) -> None:
    text = 'John Doe, hereinafter "Morgan". Morgan went. Morgan again.'
    person = _person_span(text, "John Doe")
    alias_def = _alias_def(
        text,
        "Morgan",
        subject_text="John Doe",
        subject_span=(0, len("John Doe")),
    )
    spans = [person, alias_def]
    out_spans, _ = resolve_aliases(text, spans, cfg)
    mentions = [s for s in out_spans if s.source == "alias_resolver"]
    starts = {m.start for m in mentions}
    assert len(mentions) == 2
    assert len(starts) == 2
