"""Smoke tests for package import and version."""

import redactor


def test_import_package() -> None:
    assert isinstance(redactor, object)


def test_version() -> None:
    assert redactor.__version__ == "0.1.0"
