"""Entity detection components for identifying sensitive information."""

try:  # pragma: no cover - optional dependency
    from .account_ids import AccountIdDetector
except Exception:  # pragma: no cover - missing stdnum
    AccountIdDetector = None  # type: ignore

try:  # pragma: no cover - optional dependency
    from .address_libpostal import AddressLineDetector
except Exception:  # pragma: no cover - missing usaddress
    AddressLineDetector = None  # type: ignore

from .aliases import AliasDetector
from .bank_org import BankOrgDetector
from .date_dob import DOBDetector
from .date_generic import DateGenericDetector
from .email import EmailDetector
from .names_person import (
    is_probable_person_name,
    parse_person_name,
    score_person_name,
)
from .ner_spacy import SpacyNERDetector

try:  # pragma: no cover - optional dependency
    from .phone import PhoneDetector
except Exception:  # pragma: no cover - missing phonenumbers
    PhoneDetector = None  # type: ignore

__all__ = [
    "AccountIdDetector",
    "BankOrgDetector",
    "AddressLineDetector",
    "EmailDetector",
    "PhoneDetector",
    "DateGenericDetector",
    "DOBDetector",
    "AliasDetector",
    "SpacyNERDetector",
    "is_probable_person_name",
    "score_person_name",
    "parse_person_name",
]
