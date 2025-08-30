import pytest

from redactor.detect.names_person import (
    is_core_name_token,
    is_particle,
    is_probable_person_name,
    is_suffix,
    parse_person_name,
    score_person_name,
)


@pytest.mark.parametrize(
    "text",
    [
        "John Doe",
        "J. D. Salinger",
        "Mary-Jane O'Neill-Smith Jr.",
        "Ludwig van Beethoven",
        "Gabriel García Márquez",
        "D'Angelo Russell",
        "JOHN DOE",
    ],
)
def test_positive_names(text: str) -> None:
    assert is_probable_person_name(text)
    assert score_person_name(text) >= 0.60


@pytest.mark.parametrize(
    "text",
    [
        "Buyer",
        "Bank of America",
        "UNITED STATES",
        "Section 2.1",
        "Acme LLC",
        "A.B.",
    ],
)
def test_negative_names(text: str) -> None:
    assert not is_probable_person_name(text)
    assert score_person_name(text) < 0.60


def test_parsing_examples() -> None:
    parsed = parse_person_name("Dr. John R. Smith III")
    assert parsed["honorifics"] == ["Dr."]
    assert parsed["given"] == ["John", "R."]
    assert parsed["surname"] == ["Smith"]
    assert parsed["suffixes"] == ["III"]
    assert parsed["initials"] == ["R."]

    parsed = parse_person_name("Juan de la Cruz")
    assert parsed["particles"] == ["de", "la"]
    assert parsed["surname"] == ["Cruz"]

    parsed = parse_person_name("O'Connor")
    assert parsed["surname"] == ["O'Connor"]
    assert not parsed["is_probable"]


def test_token_helpers() -> None:
    assert is_core_name_token("O'Neil")
    assert is_core_name_token("Mary-Jane")
    assert is_particle("van")
    assert not is_particle("Van")
    assert is_suffix("III")
    assert is_suffix("Esq.")
    assert is_suffix("PHD")
