"""Typed exceptions for span validation and manipulation."""


class SpanError(ValueError):
    """Base class for span related errors."""


class OverlapError(SpanError):
    """Raised when two spans overlap."""


class SpanOutOfBoundsError(SpanError):
    """Raised when span coordinates are invalid or out of bounds."""
