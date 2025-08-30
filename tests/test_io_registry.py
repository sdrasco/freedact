"""Tests for the extension-based I/O registry."""

from __future__ import annotations

from pathlib import Path

import pytest

from redactor.io import read_file, write_file
from redactor.utils.errors import UnsupportedFormatError


def test_unknown_extension_raises(tmp_path: Path) -> None:
    path = tmp_path / "file.unknown"
    with pytest.raises(UnsupportedFormatError):
        read_file(path)
    with pytest.raises(UnsupportedFormatError):
        write_file(path, "text")


def test_txt_roundtrip_via_registry(tmp_path: Path) -> None:
    content = "hello"
    path = tmp_path / "sample.txt"
    write_file(path, content)
    assert read_file(path) == content


def test_extension_case_insensitive(tmp_path: Path) -> None:
    path = tmp_path / "SAMPLE.TXT"
    write_file(path, "hi")
    assert read_file(path) == "hi"
