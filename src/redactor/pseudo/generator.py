"""Deterministic pseudonym generator stubs.

This module provides a lightweight :class:`PseudonymGenerator` that maps an
entity's canonical key to a deterministic placeholder token.  The generator is
seeded from a :class:`~redactor.config.ConfigModel` and a document scope so that
the same configuration, scope and key always yield the same pseudonym.

Security note: generated placeholders are opaque, non-reversible tokens.  They
currently take simple forms like ``PERSON_xxxxx`` or ``ORG_xxxxx`` and are not
intended to resemble real data.  Future milestones will swap in realistic,
shape-preserving fakes.

Relationship to case/format preservation: the raw pseudonyms returned here may
be passed through :mod:`redactor.pseudo.case_preserver` helpers to mimic the
casing or punctuation pattern of the original text.
"""

from __future__ import annotations

import random

from redactor.config import ConfigModel
from .seed import canonicalize_key, doc_scope, rng_for, stable_id


class PseudonymGenerator:
    """Generate deterministic placeholder pseudonyms."""

    def __init__(self, cfg: ConfigModel, *, text: str | None = None, scope: bytes | None = None) -> None:
        """Initialize the generator.

        Parameters
        ----------
        cfg:
            Configuration used for seeding.
        text:
            Raw document text.  Required when ``scope`` is ``None`` and
            ``cfg.pseudonyms.cross_doc_consistency`` is ``False``.
        scope:
            Optional precomputed scope digest.  If omitted, it is derived from
            ``cfg`` and ``text`` via :func:`redactor.pseudo.seed.doc_scope`.
        """

        if scope is None:
            scope = doc_scope(cfg, text=text)
        self.cfg: ConfigModel = cfg
        self.scope: bytes = scope

    def token(self, kind: str, key: str, *, length: int = 12) -> str:
        """Return a stable token suffix for ``key`` of a given ``kind``."""

        canonical = canonicalize_key(key)
        return stable_id(kind, canonical, cfg=self.cfg, scope=self.scope, length=length)

    def rng(self, kind: str, key: str) -> random.Random:
        """Return a reproducible random number generator for ``key``."""

        canonical = canonicalize_key(key)
        return rng_for(kind, canonical, cfg=self.cfg, scope=self.scope)

    def person_name(self, key: str) -> str:
        """Return a deterministic placeholder for a person name."""

        return f"PERSON_{self.token('PERSON', key)}"

    def org_name(self, key: str) -> str:
        """Return a deterministic placeholder for an organization name."""

        return f"ORG_{self.token('ORG', key)}"

    def bank_org_name(self, key: str) -> str:
        """Return a deterministic placeholder for a bank organization name."""

        return f"BANK_{self.token('BANK_ORG', key)}"

    def email(self, key: str) -> str:
        """Return a deterministic placeholder e-mail address."""

        return f"u{self.token('EMAIL', key, length=10)}@example.org"

    def phone(self, key: str) -> str:
        """Return a deterministic E.164-like US phone number placeholder."""

        rng = self.rng('PHONE', key)
        seven = rng.randint(0, 9_999_999)
        return f"+1555{seven:07d}"

    def address(self, key: str) -> str:
        """Return a deterministic placeholder for an address block."""

        return f"ADDRESS_{self.token('ADDRESS_BLOCK', key)}"

    def account_number(self, key: str, kind: str = "generic") -> str:
        """Return a deterministic placeholder account number."""

        return f"ACCT_{self.token(f'ACCOUNT_{kind}', key, length=16)}"
