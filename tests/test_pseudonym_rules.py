from __future__ import annotations

import re

from pydantic import SecretStr

from redactor.config import ConfigModel, load_config
from redactor.pseudo import PseudonymGenerator


def cfg_with_secret(s: str) -> ConfigModel:
    cfg = load_config()
    seed = cfg.pseudonyms.seed.model_copy(update={"secret": SecretStr(s)})
    pseudo = cfg.pseudonyms.model_copy(update={"seed": seed})
    return cfg.model_copy(update={"pseudonyms": pseudo})


def luhn_valid(num: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(num)):
        d = int(ch)
        if i % 2 == 1:
            d = d * 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def aba_valid(num: str) -> bool:
    weights = [3, 7, 1] * 3
    total = sum(int(d) * w for d, w in zip(num, weights, strict=False))
    return total % 10 == 0


def test_person_name_determinism() -> None:
    gen = PseudonymGenerator(cfg_with_secret("alpha"), text="doc")
    a = gen.person_name_like("John Doe", "key")
    b = gen.person_name_like("John Doe", "key")
    c = gen.person_name_like("John Doe", "other")
    assert a == b
    assert a != c
    assert a.lower() != "john doe"


def test_person_name_shapes() -> None:
    gen = PseudonymGenerator(cfg_with_secret("alpha"), text="doc")
    out = gen.person_name_like("JOHN DOE", "u")
    assert out.isupper()
    assert len(out.split()) == 2
    init = gen.person_name_like("J.D.", "i")
    assert re.fullmatch(r"[A-Z]\.[A-Z]\.", init.replace(" ", ""))
    complex_name = gen.person_name_like("Mary-Jane O'Neil", "c")
    parts = complex_name.split()
    assert "-" in parts[0]
    assert "'" in parts[1]


def test_org_and_bank() -> None:
    gen = PseudonymGenerator(cfg_with_secret("alpha"), text="doc")
    org = gen.org_name_like("Acme LLC", "o")
    assert org.split()[-1].upper().replace(".", "") == "LLC"
    assert len(org.split()) >= 2
    bank = gen.bank_org_like("Chase Bank, N.A.", "b")
    assert "Bank" in bank
    assert ", N.A." in bank


def test_address_lines() -> None:
    gen = PseudonymGenerator(cfg_with_secret("alpha"), text="doc")
    street = gen.address_line_like("1600 Pennsylvania Ave NW", "s", line_kind="street")
    assert re.match(r"\d+ ", street)
    assert street.strip().endswith("NW")
    unit = gen.address_line_like("Suite 210", "u", line_kind="unit")
    assert unit.startswith("Suite")
    assert unit != "Suite 210"
    csz = gen.address_line_like("San Francisco, CA 94105", "c", line_kind="city_state_zip")
    assert re.search(r",\s*[A-Z]{2}\s*\d{5}", csz)
    block = gen.address_block_like(
        "1600 Pennsylvania Ave NW\nSuite 210\nSan Francisco, CA 94105", "blk"
    )
    lines = block.splitlines()
    assert len(lines) == 3
    assert lines[0] != "1600 Pennsylvania Ave NW"


def test_numbers() -> None:
    gen = PseudonymGenerator(cfg_with_secret("alpha"), text="doc")
    cc = gen.cc_like("4111 1111 1111 1111", "cc")
    assert cc != "4111 1111 1111 1111"
    assert re.fullmatch(r"(\d{4} ){3}\d{4}", cc)
    assert luhn_valid(cc.replace(" ", ""))
    routing = gen.routing_like("021000021", "rt")
    assert routing != "021000021"
    assert re.fullmatch(r"\d{9}", routing)
    assert aba_valid(routing)
    ssn = gen.ssn_like("123-45-6789", "ssn")
    assert ssn != "123-45-6789"
    assert re.fullmatch(r"\d{3}-\d{2}-\d{4}", ssn)
    assert not ssn.startswith("000")
    ein = gen.ein_like("12-3456789", "ein")
    assert ein != "12-3456789"
    assert re.fullmatch(r"\d{2}-\d{7}", ein)
    generic = gen.generic_digits_like("0034-567-89012", "g")
    assert generic != "0034-567-89012"
    assert re.fullmatch(r"\d{4}-\d{3}-\d{5}", generic)
