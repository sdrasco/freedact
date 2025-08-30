"""Extension based registry for file I/O.

Only a minimal ``.txt`` reader/writer pair is registered by default.  The
registry dispatches based on the file extension and performs no content
normalization.  Newline characters and BOMs are handled by the underlying
readers and writers.

``UnsupportedFormatError`` is raised when attempting to read or write a file
whose extension has no registered handler.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable

from ..utils.errors import UnsupportedFormatError
from .readers.txt_reader import read_text
from .writers.txt_writer import write_text

ReaderFunc = Callable[[str | os.PathLike[str]], str]
WriterFunc = Callable[[str | os.PathLike[str], str], None]

_READERS: dict[str, Callable[..., str]] = {}
_WRITERS: dict[str, Callable[..., None]] = {}


def register_reader(ext: str, func: Callable[..., str]) -> None:
    """Register a reader for files ending with ``ext``.

    Parameters
    ----------
    ext:
        File extension including the dot (e.g. ``".txt"``).  Matching is
        case-insensitive.
    func:
        Callable that reads a file and returns a string.
    """

    _READERS[ext.lower()] = func


def register_writer(ext: str, func: Callable[..., None]) -> None:
    """Register a writer for files ending with ``ext``."""

    _WRITERS[ext.lower()] = func


def get_extension(path: str | os.PathLike[str]) -> str:
    """Return the lower-cased file extension of ``path`` (including the dot).

    Returns an empty string when the path has no extension.
    """

    suffix = Path(path).suffix
    return suffix.lower() if suffix else ""


def read_file(path: str | os.PathLike[str], **kwargs: Any) -> str:
    """Read ``path`` using the registered reader for its extension.

    Parameters
    ----------
    path:
        Path to the file being read.
    **kwargs:
        Additional keyword arguments forwarded to the underlying reader.

    Raises
    ------
    UnsupportedFormatError
        If no reader is registered for the file extension.
    """

    ext = get_extension(path)
    reader = _READERS.get(ext)
    if reader is None:
        raise UnsupportedFormatError(f"Unsupported file extension: '{ext}'") from None
    return reader(path, **kwargs)


def write_file(path: str | os.PathLike[str], text: str, **kwargs: Any) -> None:
    """Write ``text`` to ``path`` using the registered writer for its extension.

    Parameters
    ----------
    path:
        Destination file path.
    text:
        String content to be written.
    **kwargs:
        Additional keyword arguments forwarded to the underlying writer.

    Raises
    ------
    UnsupportedFormatError
        If no writer is registered for the file extension.
    """

    ext = get_extension(path)
    writer = _WRITERS.get(ext)
    if writer is None:
        raise UnsupportedFormatError(f"Unsupported file extension: '{ext}'") from None
    writer(path, text, **kwargs)


register_reader(".txt", read_text)
register_writer(".txt", write_text)

__all__ = [
    "ReaderFunc",
    "WriterFunc",
    "register_reader",
    "register_writer",
    "get_extension",
    "read_file",
    "write_file",
]
