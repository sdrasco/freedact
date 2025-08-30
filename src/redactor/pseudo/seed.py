"""Deterministic seeding helpers for pseudonymization.

This module derives stable identifiers and reproducible random streams from a
user-provided secret using HMAC-SHA256 with strict domain separation.  Entity
keys are canonicalized to avoid variations in case or whitespace from affecting
hashes.  Scopes can be per-document or cross-document depending on
configuration, enabling deterministic yet isolated pseudonyms.

These helpers only yield opaque identifiers and RNG seeds.  Higher-level
pseudonym generators interpret them to produce human-readable surrogates.

Security notes
--------------
A non-empty secret provides cryptographically strong determinism.  When the
secret is omitted, functions fall back to unkeyed hashes; this is predictable
and suitable only for non-sensitive scenarios.  Secrets and derived digests are
never logged or exposed.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import random
import re
import unicodedata
from typing import Final

from redactor.config import ConfigModel

# ---------------------------------------------------------------------------
# Domain separation constants
# ---------------------------------------------------------------------------

_NS_DOC: Final = b"redactor/v1/doc-seed"
_NS_ENTITY: Final = b"redactor/v1/entity"
_NS_RNG: Final = b"redactor/v1/rng"


# ---------------------------------------------------------------------------
# Canonicalization
# ---------------------------------------------------------------------------


def canonicalize_key(key: str) -> str:
    """Normalize an entity key for hashing.

    The normalization steps are:

    - strip leading/trailing whitespace
    - collapse internal whitespace runs to a single space
    - lowercase
    - NFC normalize (not NFKC)
    """

    normalized = unicodedata.normalize("NFC", key.strip())
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.lower()


# ---------------------------------------------------------------------------
# Document hashing
# ---------------------------------------------------------------------------


def doc_hash(text: str) -> bytes:
    """Return a 32-byte BLAKE2b digest of the raw document text."""

    return hashlib.blake2b(text.encode("utf-8"), digest_size=32).digest()


# ---------------------------------------------------------------------------
# Secret extraction
# ---------------------------------------------------------------------------


def get_secret_bytes(cfg: ConfigModel, *, require: bool = False) -> bytes:
    """Return the seed secret as bytes.

    Parameters
    ----------
    cfg:
        Configuration model holding the pseudonym seed.
    require:
        If ``True`` and the secret is missing, ``ValueError`` is raised.

    Notes
    -----
    An empty secret reduces security; callers may choose ``require=True`` in
    stricter modes.  This function never logs or prints the secret.
    """

    secret = cfg.pseudonyms.seed.secret
    if secret is None:
        if require:
            raise ValueError("Missing pseudonym seed secret")
        return b""
    return secret.get_secret_value().encode("utf-8")


# ---------------------------------------------------------------------------
# Scope derivation
# ---------------------------------------------------------------------------


def doc_scope(cfg: ConfigModel, *, text: str | None) -> bytes:
    """Derive a document scope digest.

    If ``cfg.pseudonyms.cross_doc_consistency`` is ``False``:
        return HMAC(secret, ``_NS_DOC`` || ``doc_hash(text)``)
    Else:
        return HMAC(secret, ``_NS_DOC`` || ``b"GLOBAL"``)
    If secret is empty, fall back to ``doc_hash(text)`` / ``b"GLOBAL"``.
    """

    secret = get_secret_bytes(cfg, require=False)
    if cfg.pseudonyms.cross_doc_consistency:
        data = _NS_DOC + b"GLOBAL"
        if secret:
            return hmac.new(secret, data, hashlib.sha256).digest()
        return b"GLOBAL"

    if text is None:
        raise ValueError("Document text required when cross_doc_consistency is False")
    doc_digest = doc_hash(text)
    data = _NS_DOC + doc_digest
    if secret:
        return hmac.new(secret, data, hashlib.sha256).digest()
    return doc_digest


# ---------------------------------------------------------------------------
# Stable identifiers
# ---------------------------------------------------------------------------


def stable_id(
    kind: str,
    key: str,
    *,
    cfg: ConfigModel,
    scope: bytes,
    length: int = 20,
) -> str:
    """Return a stable, non-reversible identifier token.

    The token is computed as ``HMAC(secret, _NS_ENTITY || kind || scope ||
    canonicalized_key)`` and rendered as URL-safe lowercase Base32 without
    padding.  When the secret is empty, SHA256 over the same concatenation is
    used instead.
    """

    if not 8 <= length <= 52:
        raise ValueError("length must be between 8 and 52")

    canonical = canonicalize_key(key)
    data = _NS_ENTITY + kind.encode("utf-8") + scope + canonical.encode("utf-8")
    secret = get_secret_bytes(cfg, require=False)
    if secret:
        digest = hmac.new(secret, data, hashlib.sha256).digest()
    else:
        digest = hashlib.sha256(data).digest()

    token = base64.b32encode(digest).decode("ascii").lower().rstrip("=")
    return token[:length]


# ---------------------------------------------------------------------------
# Reproducible RNG
# ---------------------------------------------------------------------------


def rng_for(kind: str, key: str, *, cfg: ConfigModel, scope: bytes) -> random.Random:
    """Derive a reproducible RNG seeded from the provided parameters."""

    canonical = canonicalize_key(key)
    data = _NS_RNG + kind.encode("utf-8") + scope + canonical.encode("utf-8")
    secret = get_secret_bytes(cfg, require=False)
    if secret:
        digest = hmac.new(secret, data, hashlib.sha256).digest()
    else:
        digest = hashlib.sha256(data).digest()
    seed_int = int.from_bytes(digest, "big")
    return random.Random(seed_int)


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------


def scoped_stable_id_for_text(
    kind: str,
    key: str,
    text: str,
    cfg: ConfigModel,
    *,
    length: int = 20,
) -> str:
    """Stable identifier for ``key`` scoped to ``text`` using ``cfg``."""

    return stable_id(kind, key, cfg=cfg, scope=doc_scope(cfg, text=text), length=length)


def scoped_rng_for_text(kind: str, key: str, text: str, cfg: ConfigModel) -> random.Random:
    """Reproducible RNG for ``key`` scoped to ``text`` using ``cfg``."""

    return rng_for(kind, key, cfg=cfg, scope=doc_scope(cfg, text=text))


__all__ = [
    "canonicalize_key",
    "doc_hash",
    "get_secret_bytes",
    "doc_scope",
    "stable_id",
    "rng_for",
    "scoped_stable_id_for_text",
    "scoped_rng_for_text",
]
