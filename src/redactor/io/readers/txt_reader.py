"""Plain-text reader.

This module exposes :func:`read_text` which loads text files without performing
any content normalization.  Newline characters are preserved exactly as stored
on disk and UTF-8 byte-order marks (BOM) are handled transparently by using the
``"utf-8-sig"`` codec by default.

Example
-------
``read_text(path)`` round-trips ``\n``, ``\r\n`` and ``\r`` sequences without
modification.  ``FileNotFoundError`` and other I/O errors propagate to the
caller.
"""

from __future__ import annotations

import os

PathLikeStr = os.PathLike[str]


def read_text(
    path: str | PathLikeStr,
    *,
    encoding: str = "utf-8-sig",
    errors: str = "strict",
) -> str:
    """Read a plain-text file as-is.

    Parameters
    ----------
    path:
        Path to the file on disk.
    encoding:
        Text encoding to use.  Defaults to ``"utf-8-sig"`` so that a UTF-8 BOM
        is consumed when present.
    errors:
        Error handling strategy passed to :func:`open`.

    Returns
    -------
    str
        The file contents without any newline translation.

    Notes
    -----
    ``newline=""`` is used when opening the file to prevent Python from
    converting newline characters.  This function performs no normalization of
    whitespace or line endings.
    """

    with open(path, "r", encoding=encoding, errors=errors, newline="") as f:
        return f.read()


__all__ = ["read_text"]
