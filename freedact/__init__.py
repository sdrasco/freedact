"""Freedact package.

This package exposes the core API for text redaction as well as helper
functions for reading and writing documents.  The command line interface lives
in :mod:`freedact.cli`.
"""

from .redaction import RedactionResult, redact_text_pipeline
from .io_utils import read_input_text, write_docx, write_pdf, write_json_key

__all__ = [
    "RedactionResult",
    "redact_text_pipeline",
    "read_input_text",
    "write_docx",
    "write_pdf",
    "write_json_key",
]

