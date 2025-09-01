from __future__ import annotations

import os
import time

import pytest

from evaluation.fixtures import loader as fixtures_loader
from redactor.config import load_config
from redactor.detect.account_ids import AccountIdDetector
from redactor.detect.address_libpostal import AddressLineDetector
from redactor.detect.aliases import AliasDetector
from redactor.detect.bank_org import BankOrgDetector
from redactor.detect.base import DetectionContext, Detector
from redactor.detect.date_dob import DOBDetector
from redactor.detect.date_generic import DateGenericDetector
from redactor.detect.email import EmailDetector
from redactor.detect.phone import PhoneDetector
from redactor.utils.textspan import build_line_starts

if os.getenv("SKIP_PERF_TESTS") == "1":
    pytest.skip("Performance tests skipped by SKIP_PERF_TESTS", allow_module_level=True)


def _get_env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, "").strip() or default)
    except ValueError:
        return default


def _get_env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "").strip() or default)
    except ValueError:
        return default


def _synth_text(names: list[str], repeat: int) -> str:
    parts = [fixtures_loader.load_fixture(n)[0] for n in names]
    base = "\n\n".join(parts)
    return "\n\n".join([base] * repeat)


def test_detector_budget() -> None:
    repeat = _get_env_int("PERF_REPEAT", 120)
    text = _synth_text(["banks_ids", "emails_phones"], repeat)

    cfg = load_config()
    cfg = cfg.model_copy(
        update={
            "detectors": cfg.detectors.model_copy(
                update={
                    "ner": cfg.detectors.ner.model_copy(
                        update={"enabled": False, "require": False}
                    ),
                    "coref": cfg.detectors.coref.model_copy(
                        update={
                            "enabled": False,
                            "backend": "regex",
                            "require": False,
                        }
                    ),
                }
            )
        }
    )
    context = DetectionContext(locale=cfg.locale, line_starts=build_line_starts(text), config=cfg)

    detectors: list[Detector] = [
        EmailDetector(),
        PhoneDetector(),
        AccountIdDetector(),
        BankOrgDetector(),
        AddressLineDetector(),
        DateGenericDetector(),
        DOBDetector(),
        AliasDetector(),
    ]
    budget = _get_env_float("PERF_MAX_SEC_DET", 1.5)

    for det in detectors:
        start = time.perf_counter()
        det.detect(text, context)
        elapsed = time.perf_counter() - start
        assert (
            elapsed <= budget
        ), f"{det.__class__.__name__} took {elapsed:.3f}s (budget {budget:.3f}s)"
