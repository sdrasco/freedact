from __future__ import annotations

from pydantic import SecretStr

from redactor.config import ConfigModel, load_config
from redactor.pseudo import (
    canonicalize_key,
    scoped_rng_for_text,
    scoped_stable_id_for_text,
)


def cfg_with_secret(s: str, cross_doc: bool = False) -> ConfigModel:
    cfg = load_config()
    seed = cfg.pseudonyms.seed.model_copy(update={"secret": SecretStr(s)})
    pseudo = cfg.pseudonyms.model_copy(update={"cross_doc_consistency": cross_doc, "seed": seed})
    return cfg.model_copy(update={"pseudonyms": pseudo})


def test_determinism() -> None:
    cfg = cfg_with_secret("alpha")
    text_a = "document a"
    id1 = scoped_stable_id_for_text("PERSON", "John   Doe", text_a, cfg)
    id2 = scoped_stable_id_for_text("PERSON", "john doe", text_a, cfg)
    assert id1 == id2
    assert len(id1) == 20


def test_secret_sensitivity() -> None:
    text = "doc"
    cfg_a = cfg_with_secret("alpha")
    cfg_b = cfg_with_secret("beta")
    id_a = scoped_stable_id_for_text("EMAIL", "john@example.com", text, cfg_a)
    id_b = scoped_stable_id_for_text("EMAIL", "john@example.com", text, cfg_b)
    assert id_a != id_b


def test_scope_behavior() -> None:
    cfg_doc = cfg_with_secret("alpha", cross_doc=False)
    id_doc1 = scoped_stable_id_for_text("PERSON", "jane doe", "doc1", cfg_doc)
    id_doc2 = scoped_stable_id_for_text("PERSON", "jane doe", "doc2", cfg_doc)
    assert id_doc1 != id_doc2

    cfg_global = cfg_with_secret("alpha", cross_doc=True)
    id_gl1 = scoped_stable_id_for_text("PERSON", "jane doe", "doc1", cfg_global)
    id_gl2 = scoped_stable_id_for_text("PERSON", "jane doe", "doc2", cfg_global)
    assert id_gl1 == id_gl2


def test_rng_determinism() -> None:
    cfg_doc = cfg_with_secret("alpha", cross_doc=False)
    r1 = scoped_rng_for_text("ADDRESS", "366 broadway", "doc1", cfg_doc)
    r2 = scoped_rng_for_text("ADDRESS", "366 broadway", "doc1", cfg_doc)
    assert [r1.random() for _ in range(3)] == [r2.random() for _ in range(3)]


def test_canonicalize_key() -> None:
    assert canonicalize_key("  JOHN \t DOE ") == "john doe"


def test_empty_secret_fallback() -> None:
    cfg = load_config()
    text = "doc"
    id1 = scoped_stable_id_for_text("PERSON", "jane doe", text, cfg)
    id2 = scoped_stable_id_for_text("PERSON", "jane doe", text, cfg)
    assert id1 == id2
