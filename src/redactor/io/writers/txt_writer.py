"""Plain-text writer.

The :func:`write_text` helper persists Unicode strings to disk without altering
existing newline sequences.  Directories required to store the file are created
automatically.  By default UTF-8 encoding without a BOM is used.

This module performs *no* content normalization; the ``text`` argument is
written exactly as provided.
"""

from __future__ import annotations

import os
from pathlib import Path

PathLikeStr = os.PathLike[str]


def write_text(
    path: str | PathLikeStr,
    text: str,
    *,
    encoding: str = "utf-8",
    newline: str | None = "",
) -> None:
    """Write ``text`` to ``path`` exactly as provided.

    Parameters
    ----------
    path:
        Destination file path.
    text:
        The Unicode string to be written.
    encoding:
        Output encoding.  Defaults to UTF-8 without a byte-order mark.
    newline:
        ``newline`` parameter forwarded to :func:`open`.  The default of ``""``
        ensures newline characters in ``text`` are emitted verbatim.

    Notes
    -----
    Parent directories are created with ``exist_ok=True``.  This function
    performs no normalization or mutation of the provided text.
    """

    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding=encoding, newline=newline) as f:
        f.write(text)


__all__ = ["write_text"]
