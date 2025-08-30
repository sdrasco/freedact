"""Tests for case and format preservation utilities."""

from __future__ import annotations

import importlib.util
import random
import sys
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "src" / "redactor" / "pseudo" / "case_preserver.py"
)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
spec = importlib.util.spec_from_file_location("case_preserver", MODULE_PATH)
assert spec is not None and spec.loader is not None
case_preserver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(case_preserver)

match_case = case_preserver.match_case
format_like = case_preserver.format_like


def test_match_case_global() -> None:
    assert match_case("JOHN DOE", "Alex Carter") == "ALEX CARTER"
    assert match_case("john doe", "Alex Carter") == "alex carter"
    assert match_case("John Doe", "alex carter") == "Alex Carter"


def test_match_case_mixed_letterwise() -> None:
    assert match_case("McDONALD", "Smithson") == "SmITHSON"


def test_format_like_interior_punctuation() -> None:
    assert format_like("O'NEIL", "Dangelo") == "D'ANGELO"
    assert format_like("SMITH-JONES", "Carter Green") == "CARTER-GREEN"


def test_format_like_surrounding_punctuation() -> None:
    assert format_like("\u201cJohn\u201d", "Alex") == "\u201cAlex\u201d"
    assert format_like("(John)", "Alex") == "(Alex)"


def test_format_like_possessive() -> None:
    assert format_like("John's", "Alex") == "Alex's"


def test_format_like_initials_preservation() -> None:
    assert format_like("J.D.", "Alex Carter") == "A.C."
    assert format_like("J. D.", "Alex Carter") == "A. C."
    assert format_like("J.D.E.", "Alex C. Thompson") == "A.C.T."
    assert format_like("J.D.", "Alex") == "A.A."


def test_format_like_initials_rng_deterministic() -> None:
    seed = 123
    assert (
        format_like("J.D.", "Alex", rng=random.Random(seed))
        == format_like("J.D.", "Alex", rng=random.Random(seed))
        == "A.B."
    )


def test_format_like_non_letter_string() -> None:
    assert format_like("123-456", "789-012") == "789-012"
