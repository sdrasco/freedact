# redactor

The redactor project aims to provide a privacy-first pipeline for sanitizing legal documents before they are shared with cloud-based language models. It replaces sensitive personal and organizational information with deterministic pseudonyms while preserving the technical facts necessary for analysis. The system operates entirely offline by default and relies on open-source tools for detection and replacement of PII. Each modification is auditable so users can trace the origin and rationale for every change. The goal is to ensure zero leakage of personal data, reproducible outputs, and seamless integration into legal workflows. This repository currently contains only the foundational scaffolding; product functionality will be added in future iterations.

## Architecture at a glance

### Top-level modules
- `config`: configuration loading and validation
- `io`: file readers and writers
- `preprocess`: text normalization and segmentation
- `detect`: entity detectors
- `link`: span linking and coreference resolution
- `pseudo`: pseudonym generation rules
- `replace`: building and applying replacements
- `verify`: post-redaction checks
- `evaluation`: metrics and test fixtures
- `utils`: shared helper utilities

### Pipeline stages
1. **Preprocess** input text
2. **Detect** sensitive entities
3. **Link** and resolve entity references
4. **Generate pseudonyms** for entities
5. **Plan & apply replacements**
6. **Verify** redacted output
7. **Evaluate** performance (optional)

Modules are intentionally empty pending M1-T3 and later tasks.

## Preprocessing

Normalization cleans up a few Unicode quirks while preserving line breaks and
most spacing.  It also returns a ``char_map`` so that every character in the
normalized text can be traced back to its original index.  Sentence segmentation
is intentionally conservative and aims only to provide reasonable hints for
later detectors.

## Configuration

The library loads default settings from `redactor/config/defaults.yml`. You can
override these by supplying your own YAML file:

```yaml
# myconfig.yml
pseudonyms:
  cross_doc_consistency: true
```

Load overrides with `load_config("myconfig.yml")`. Secrets such as the
pseudonym seed are provided via environment variables; set
`REDACTOR_SEED_SECRET` (or a custom variable defined by
`pseudonyms.seed.secret_env`) to deterministically seed pseudonyms.

## Deterministic seeding

Seeding controls how identifiers and random number generators are derived from
input text. By default, identifiers are scoped to each document, so the same
person in two files receives different pseudonyms. Setting
`pseudonyms.cross_doc_consistency` to `true` switches to global scoping where
the same entity maps to the same pseudonym across documents.

Provide a secret via the `REDACTOR_SEED_SECRET` environment variable (or the
name configured in `pseudonyms.seed.secret_env`) to cryptographically tie these
values to your deployment. Omitting the secret still yields deterministic
output but without cryptographic protection.

## Pseudonym generator (stub)

The current pseudonym generator maps each entity to a deterministic placeholder
such as `PERSON_xxxxx` or `ORG_xxxxx`. These tokens are stable for a given
configuration and scope but are clearly fake. Future milestones will introduce
shape-preserving fakes and integrate them with case/format preservation.

## Case and format preservation

Pseudonym replacements mirror the casing and punctuation shape of the source
text.  Generated names adapt to match initials patterns and interior
punctuation, keeping the redacted output natural.  For example, a source token
like ``O’NEIL`` would become ``D’ANGELO`` when replaced.

## Addresses

Street, unit, city/state/ZIP and PO Box lines are detected using the
``usaddress`` library.  Adjacent lines are merged into a single multi-line
address block so redaction replaces the entire address at once.  The merger is
layout-aware and tolerates a single blank line between components.

## Dates vs DOBs

The redactor differentiates between general dates and dates of birth.  Dates in
contracts or correspondence are labelled ``DATE_GENERIC`` and preserved so they
remain visible in the redacted text.  A date is upgraded to ``DOB`` only when
nearby lexical triggers such as "DOB", "Date of Birth" or "born" make the
birthdate intent clear.

## Legal aliases

Alias labels defined with phrases such as ``hereinafter``, ``a/k/a`` (also known
as), ``f/k/a`` (formerly known as) or ``d/b/a`` (doing business as) are detected
as ``ALIAS_LABEL`` spans.  Only the alias term itself is captured – for example
``"Buyer"`` or ``"Morgan"`` – while trigger words and punctuation are ignored.
When a subject name appears nearby, the detector records it so later stages can
link all references to a consistent pseudonym.

## NER (optional)

Named-entity recognition for people, organizations and locations is provided
via spaCy when available. Install the optional dependencies with
`pip install .[ner]` and choose a model through
`config.detectors.ner.model` (defaults to ``en_core_web_trf``). If spaCy or the
model is unavailable, the detector falls back to lightweight pattern rules or a
pure-Python regex engine. Setting `config.detectors.ner.require` to `true`
raises an error instead of falling back.

## Quick start (CLI)

```bash
redactor run --in samples/snippet.txt --out out/sanitized.txt --report out/report
```

Note: currently runs preprocessing only; full redaction pipeline will be wired in later milestones.
