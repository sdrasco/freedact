from redactor.config import load_config


def test_default_values() -> None:
    cfg = load_config()
    assert cfg.redact.person_names is True
    assert cfg.redact.generic_dates is False
    assert cfg.verification.fail_on_residual is True
    assert cfg.pseudonyms.cross_doc_consistency is False
    assert cfg.detectors.coref.enabled is False
    assert cfg.detectors.coref.backend == "auto"
    assert cfg.precedence == [
        "ACCOUNT_ID",
        "EMAIL",
        "PHONE",
        "ADDRESS_BLOCK",
        "ALIAS_LABEL",
        "PERSON",
        "ORG",
        "BANK_ORG",
        "GPE",
        "LOC",
        "DOB",
        "DATE_GENERIC",
    ]
