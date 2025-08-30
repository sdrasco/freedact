"""Core detection model and protocol definitions.

This module defines the minimal strongly‑typed primitives shared by all
detectors.  Spans follow the half‑open interval convention ``[start, end)``
where ``start`` is inclusive and ``end`` is exclusive.  Detectors must ensure
that returned spans fall within the bounds of the analysed text and do not
contain duplicates.  Overlap resolution is deferred to later pipeline steps.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, runtime_checkable

from redactor.utils.errors import SpanOutOfBoundsError


class EntityLabel(Enum):
    """Enumeration of supported entity labels."""

    PERSON = "PERSON"
    ORG = "ORG"
    BANK_ORG = "BANK_ORG"
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    ACCOUNT_ID = "ACCOUNT_ID"
    ADDRESS_BLOCK = "ADDRESS_BLOCK"
    DOB = "DOB"
    DATE_GENERIC = "DATE_GENERIC"
    ALIAS_LABEL = "ALIAS_LABEL"
    GPE = "GPE"
    LOC = "LOC"
    OTHER = "OTHER"


@dataclass(slots=True, frozen=True)
class EntitySpan:
    """Detected entity information.

    Attributes follow the half‑open interval convention where ``start`` is
    inclusive and ``end`` is exclusive.  ``confidence`` must be between ``0``
    and ``1``.
    """

    start: int
    end: int
    text: str
    label: EntityLabel
    source: str
    confidence: float
    attrs: dict[str, object] = field(default_factory=dict)
    entity_id: str | None = None
    span_id: str | None = None

    def __post_init__(self) -> None:  # noqa: D401 - simple validation
        if self.end <= self.start or self.start < 0:
            raise SpanOutOfBoundsError(f"invalid span [{self.start}, {self.end})")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be within [0.0, 1.0]")

    @property
    def length(self) -> int:
        """Return span length in characters."""

        return self.end - self.start


@runtime_checkable
class Detector(Protocol):
    """Protocol for entity detectors.

    A detector analyses input text and returns zero or more :class:`EntitySpan`
    objects describing detected entities.
    """

    def name(self) -> str:
        """Return a short, stable identifier for the detector."""

        ...

    def detect(self, text: str, context: "DetectionContext | None" = None) -> list[EntitySpan]:
        """Detect entities in ``text``.

        Parameters
        ----------
        text:
            The original text to analyse.
        context:
            Optional :class:`DetectionContext` with metadata that may influence
            detection.
        """

        ...


@dataclass(slots=True, frozen=True)
class DetectionContext:
    """Optional context information supplied to detectors."""

    doc_id: str | None = None
    locale: str | None = None
    line_starts: tuple[int, ...] | None = None
    config: object | None = None
