from __future__ import annotations
from __future__ import annotations

import re

from pydantic import SecretStr

from redactor.config import ConfigModel, load_config
from redactor.pseudo import PseudonymGenerator


def cfg_with_secret(s: str, cross_doc: bool = False) -> ConfigModel:
    cfg = load_config()
    seed = cfg.pseudonyms.seed.model_copy(update={"secret": SecretStr(s)})
    pseudo = cfg.pseudonyms.model_copy(update={"cross_doc_consistency": cross_doc, "seed": seed})
    return cfg.model_copy(update={"pseudonyms": pseudo})


def test_determinism_within_document() -> None:
    gen = PseudonymGenerator(cfg_with_secret("alpha"), text="doc A")
    assert gen.person_name("John Doe") == gen.person_name("john  doe")
    assert gen.person_name("John Doe").startswith("PERSON_")
    assert gen.org_name("Acme Inc.") != gen.person_name("Acme Inc.")
    assert gen.email("john@example.com").endswith("@example.org")
    assert re.fullmatch(r"\+1555\d{7}", gen.phone("555-1212"))
    assert gen.address("366 Broadway").startswith("ADDRESS_")
    assert gen.account_number("123456789").startswith("ACCT_")


def test_scope_behavior_per_doc() -> None:
    gen_a = PseudonymGenerator(cfg_with_secret("alpha", cross_doc=False), text="doc A")
    gen_b = PseudonymGenerator(cfg_with_secret("alpha", cross_doc=False), text="doc B")
    assert gen_a.person_name("Jane Doe") != gen_b.person_name("Jane Doe")


def test_scope_behavior_cross_doc() -> None:
    gen1 = PseudonymGenerator(cfg_with_secret("alpha", cross_doc=True), text="doc A")
    gen2 = PseudonymGenerator(cfg_with_secret("alpha", cross_doc=True), text="doc B")
    assert gen1.person_name("Jane Doe") == gen2.person_name("Jane Doe")


def test_secret_sensitivity() -> None:
    gen1 = PseudonymGenerator(cfg_with_secret("alpha"), text="doc A")
    gen2 = PseudonymGenerator(cfg_with_secret("beta"), text="doc A")
    assert gen1.email("x@y") != gen2.email("x@y")


def test_phone_stability() -> None:
    gen = PseudonymGenerator(cfg_with_secret("alpha"), text="doc A")
    assert gen.phone("any") == gen.phone("any")
    assert gen.phone("any") != gen.phone("other")


def test_import_export() -> None:
    from redactor.pseudo import PseudonymGenerator as Exported

    assert Exported is PseudonymGenerator

