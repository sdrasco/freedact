"""Typed exceptions for span validation/manipulation and I/O formats."""


class SpanError(ValueError):
    """Base class for span related errors."""


class OverlapError(SpanError):
    """Raised when two spans overlap."""


class SpanOutOfBoundsError(SpanError):
    """Raised when span coordinates are invalid or out of bounds."""


class IOFormatError(ValueError):
    """Base class for I/O format related errors."""


class UnsupportedFormatError(IOFormatError):
    """Raised when no reader or writer is registered for a file format."""
