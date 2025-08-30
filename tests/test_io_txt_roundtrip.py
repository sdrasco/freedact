"""Tests for plain-text reader and writer."""

from __future__ import annotations

from pathlib import Path

from redactor.io.readers.txt_reader import read_text
from redactor.io.writers.txt_writer import write_text


def test_txt_roundtrip_preserves_mixed_newlines(tmp_path: Path) -> None:
    content = "A\nB\r\nC\rD"
    file_path = tmp_path / "sample.txt"
    write_text(file_path, content)
    assert read_text(file_path) == content


def test_read_text_handles_utf8_bom(tmp_path: Path) -> None:
    content = "hello"
    file_path = tmp_path / "bom.txt"
    with open(file_path, "w", encoding="utf-8-sig", newline="") as f:
        f.write(content)
    assert read_text(file_path) == content


def test_write_text_creates_parent_dirs(tmp_path: Path) -> None:
    file_path = tmp_path / "nested" / "dir" / "file.txt"
    write_text(file_path, "data")
    assert file_path.exists()
    assert read_text(file_path) == "data"
