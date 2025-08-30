"""spaCy-based named-entity detector with graceful fallbacks.

This detector extracts PERSON, ORG and GPE/LOC mentions using spaCy when
available.  It supports three operation modes:

* **spacy** – the configured spaCy model is loaded lazily.  Transformer models
  (names containing ``"trf"``) receive a base confidence of ``0.95`` while
  smaller models default to ``0.92``.
* **ruler_fallback** – spaCy is installed but the model cannot be loaded.
  A lightweight ``blank("en")`` pipeline with an ``EntityRuler`` provides
  heuristic patterns with a confidence of ``0.88``.
* **regex_fallback** – spaCy is entirely unavailable.  Pure regular
  expressions are used with a conservative confidence of ``0.80``.

All modes trim trailing punctuation from spans and suppress obvious role words
such as ``Buyer`` or ``Seller``.  Fully lowercase strings or single-token
uppercase strings are ignored to reduce false positives.  Resolution of
overlapping spans across detectors is handled elsewhere in the pipeline.
"""

from __future__ import annotations

import re

from redactor.config import ConfigModel

from .base import DetectionContext, EntityLabel, EntitySpan

__all__ = ["SpacyNERDetector", "get_detector"]

# ---------------------------------------------------------------------------
# Constants and helpers
# ---------------------------------------------------------------------------

ROLE_LEXICON = {
    "Buyer",
    "Seller",
    "Lender",
    "Borrower",
    "Landlord",
    "Tenant",
    "Guarantor",
    "Licensor",
    "Licensee",
    "Plaintiff",
    "Defendant",
    "Petitioner",
    "Respondent",
    "Trustee",
    "Executor",
    "Administrator",
    "Assignor",
    "Assignee",
    "Discloser",
    "Recipient",
}

TRAILING_PUNCTUATION = ")]}\};:,.!?»”’>"


def _trim_right_punct(text: str, start: int, end: int) -> tuple[int, int]:
    """Trim trailing punctuation from ``text[start:end]``."""

    while end > start and text[end - 1] in TRAILING_PUNCTUATION:
        end -= 1
    return start, end


# Regex patterns for pure Python fallback.
PERSON_RE = re.compile(
    r"\b("  # start
    r"[A-Z][a-z]+(?:[\'’\-][A-Z][a-z]+)?"
    r"(?:\s+[A-Z][a-z]+(?:[\'’\-][A-Z][a-z]+)?){1,3}"  # additional tokens
    r")\b"
)

ORG_RE = re.compile(
    r"\b("  # start
    r"[A-Z][\w&.\'’-]*"
    r"(?:\s+[A-Z][\w&.\'’-]*)*"  # middle tokens
    r"\s+(?:Inc\.|LLC|LLP|Ltd\.?|PLC|N\.?A\.?|N\.?V\.?|Company|Corp\.|Bank|Trust|Credit\s+Union)"
    r")\b"
)

GPE_RE = re.compile(
    r"\b("  # start
    r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*"  # city words
    r",\s*[A-Z]{2}"
    r")\b"
)


def _is_role(text: str) -> bool:
    """Return ``True`` if ``text`` is a role word in the lexicon."""

    return text.strip("\"'“”‘’") in ROLE_LEXICON


def _is_noise(text: str) -> bool:
    """Return ``True`` if ``text`` is obviously not a name."""

    if text.islower():
        return True
    tokens = text.split()
    if len(tokens) == 1 and text.isupper():
        return True
    return False


# ---------------------------------------------------------------------------
# Detector implementation
# ---------------------------------------------------------------------------


class SpacyNERDetector:
    """Detect PERSON/ORG/GPE spans using spaCy with fallbacks."""

    def __init__(self, cfg: ConfigModel):
        self._cfg = cfg
        self._model_name = cfg.detectors.ner.model
        self._enabled = cfg.detectors.ner.enabled
        self._require = cfg.detectors.ner.require
        self._nlp: object | None = None
        self._mode: str | None = None
        self._confidence_base: float = 0.0

    def name(self) -> str:  # pragma: no cover - trivial
        return "ner_spacy"

    # ------------------------------------------------------------------
    # Pipeline initialisation
    # ------------------------------------------------------------------
    def _ensure_pipeline(self) -> None:
        if self._mode is not None:
            return

        try:
            import spacy
            from spacy.language import Language  # noqa: F401 - type hint only
        except Exception as e:  # pragma: no cover - import guard
            if self._require:
                raise RuntimeError(
                    "spaCy is required for NER detection. Install with `pip install redactor[ner]`."
                ) from e
            self._mode = "regex_fallback"
            return

        # Try to load requested model.
        try:
            self._nlp = spacy.load(self._model_name)
            self._mode = "spacy"
            self._confidence_base = 0.95 if "trf" in self._model_name else 0.92
            return
        except Exception as e:
            if self._model_name == "en_core_web_trf":
                try:
                    self._nlp = spacy.load("en_core_web_sm")
                    self._model_name = "en_core_web_sm"
                    self._mode = "spacy"
                    self._confidence_base = 0.92
                    return
                except Exception:
                    pass
            if self._require:
                raise RuntimeError(
                    "spaCy model '%s' is not available. Install with `pip install redactor[ner]`."
                    % self._model_name
                ) from e

        # Build EntityRuler fallback
        nlp = spacy.blank("en")
        ruler = nlp.add_pipe("entity_ruler")

        patterns: list[dict[str, object]] = []

        name_token = {"TEXT": {"REGEX": r"[A-Z][a-z]+(?:[\'’\-][A-Z][a-z]+)?"}}
        for length in range(2, 5):
            patterns.append({"label": "PERSON", "pattern": [name_token] * length})

        org_token = {"TEXT": {"REGEX": r"[A-Z][\w&.\'’-]*"}}
        org_suffixes = [
            ["Inc."],
            ["LLC"],
            ["LLP"],
            ["Ltd."],
            ["Ltd"],
            ["PLC"],
            ["N.A."],
            ["N.V."],
            ["Company"],
            ["Corp."],
            ["Bank"],
            ["Trust"],
            ["Credit", "Union"],
        ]
        for pre in range(1, 4):  # number of tokens before suffix
            for suf in org_suffixes:
                patterns.append(
                    {
                        "label": "ORG",
                        "pattern": [org_token] * pre + [{"TEXT": s} for s in suf],
                    }
                )

        city_token = {"TEXT": {"REGEX": r"[A-Z][a-z]+"}}
        for length in range(1, 4):
            pattern = [city_token] * length + [
                {"TEXT": ","},
                {"TEXT": {"REGEX": r"[A-Z]{2}"}},
            ]
            patterns.append({"label": "GPE", "pattern": pattern})

        ruler.add_patterns(patterns)

        self._nlp = nlp
        self._mode = "ruler_fallback"
        self._confidence_base = 0.88

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------
    def detect(self, text: str, context: DetectionContext | None = None) -> list[EntitySpan]:
        if not self._enabled:
            return []

        if self._mode is None:
            self._ensure_pipeline()

        spans: list[EntitySpan] = []

        if self._mode == "spacy" or self._mode == "ruler_fallback":
            assert self._nlp is not None
            doc = self._nlp(text)  # type: ignore[operator]
            for ent in doc.ents:
                if ent.label_ not in {"PERSON", "ORG", "GPE", "LOC"}:
                    continue
                start, end = _trim_right_punct(text, ent.start_char, ent.end_char)
                label_map = {
                    "PERSON": EntityLabel.PERSON,
                    "ORG": EntityLabel.ORG,
                    "GPE": EntityLabel.GPE,
                    "LOC": EntityLabel.LOC,
                }
                label = label_map[ent.label_]
                span_text = text[start:end]
                if label is EntityLabel.PERSON and _is_role(span_text):
                    continue
                if _is_noise(span_text):
                    continue

                attrs: dict[str, object] = {"mode": self._mode, "spacy_label": ent.label_}
                if self._mode == "spacy":
                    attrs["model"] = self._model_name
                    confidence = self._confidence_base
                else:  # ruler fallback
                    confidence = self._confidence_base

                spans.append(
                    EntitySpan(start, end, span_text, label, "ner_spacy", confidence, attrs)
                )

        else:  # regex fallback
            confidence = 0.80
            for match in PERSON_RE.finditer(text):
                start, end = _trim_right_punct(text, *match.span(0))
                span_text = text[start:end]
                if _is_role(span_text) or _is_noise(span_text):
                    continue
                spans.append(
                    EntitySpan(
                        start,
                        end,
                        span_text,
                        EntityLabel.PERSON,
                        "ner_spacy",
                        confidence,
                        {"mode": "regex"},
                    )
                )

            for match in ORG_RE.finditer(text):
                start, end = _trim_right_punct(text, *match.span(0))
                span_text = text[start:end]
                if _is_noise(span_text):
                    continue
                spans.append(
                    EntitySpan(
                        start,
                        end,
                        span_text,
                        EntityLabel.ORG,
                        "ner_spacy",
                        confidence,
                        {"mode": "regex"},
                    )
                )

            for match in GPE_RE.finditer(text):
                start, end = _trim_right_punct(text, *match.span(0))
                span_text = text[start:end]
                if _is_noise(span_text):
                    continue
                spans.append(
                    EntitySpan(
                        start,
                        end,
                        span_text,
                        EntityLabel.GPE,
                        "ner_spacy",
                        confidence,
                        {"mode": "regex"},
                    )
                )

        # De-duplicate spans by (start, end)
        unique: dict[tuple[int, int], EntitySpan] = {}
        for span in spans:
            key = (span.start, span.end)
            if key not in unique:
                unique[key] = span
        return sorted(unique.values(), key=lambda s: s.start)


def get_detector(cfg: ConfigModel) -> SpacyNERDetector:
    """Return a :class:`SpacyNERDetector` instance."""

    return SpacyNERDetector(cfg)
