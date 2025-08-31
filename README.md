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

## Pseudonym rules (shape-preserving)

This milestone adds a library of lightweight generators that craft realistic
looking replacements while keeping the visible shape of the source text.
Examples:

* Names – `JOHN DOE` → `ALAN SMITH`, `J.D.` → `A.C.`
* Organizations – `Acme LLC` → `Apex Vector LLC`
* Banks – `Chase Bank, N.A.` → `Summit Bank, N.A.`
* Addresses – ``1600 Pennsylvania Ave NW`` → ``2458 Oak St NW``
* Numbers – credit cards, routing numbers and IDs retain their punctuation and
  pass simple checksum rules.

Determinism is still guaranteed via the seeding utilities.  Downstream
verification can choose to treat these fakes as allowable data or filter them
from leakage scoring using the audit map.

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

## Global span merger

Detectors often emit overlapping spans describing the same text.  A global
merger resolves these conflicts by applying a configurable precedence order and
deterministic tie-breakers.  Within the same precedence tier, longer spans win
over shorter ones and higher confidence scores break ties.  Address line spans
are therefore typically superseded by their merged multi-line address blocks.

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

## Alias resolution and propagation

Alias definitions are linked to their subjects and grouped into stable entity
clusters.  Once an alias such as ``"Morgan"`` is defined for ``John Doe``, every
later mention of ``Morgan`` is tagged with the same cluster identifier so
pseudonym replacements remain consistent.  Role aliases like ``Buyer`` can be
kept verbatim by setting ``redact.alias_labels`` to ``"keep_roles"`` – they are
still linked for clustering but marked to skip replacement.

## Replacement planning and application

Detected spans are converted into a replacement plan that records the
character offsets and final pseudonyms to insert.  Entries are applied in
reverse order so indices remain valid.  Role labels may be preserved when
``redact.alias_labels`` is set to ``"keep_roles"`` and generic dates remain
unless ``redact.generic_dates`` is enabled.

```text
Before: John Doe (the "Buyer") was born on July 4, 1982.
After:  Alan Smith (the "Buyer") was born on May 9, 1960.
```

The applied plan provides an audit trail showing which spans were replaced and
with what pseudonyms.

## NER (optional)

Named-entity recognition for people, organizations and locations is provided
via spaCy when available. Install the optional dependencies with
`pip install .[ner]` and choose a model through
`config.detectors.ner.model` (defaults to ``en_core_web_trf``). If spaCy or the
model is unavailable, the detector falls back to lightweight pattern rules or a
pure-Python regex engine. Setting `config.detectors.ner.require` to `true`
raises an error instead of falling back.

## Verification and leakage scoring

After replacements are applied you can re-scan the redacted text for residual
PII.  The verification scanner reuses the same detectors and produces a
structured report with counts by entity label and an overall leakage score.

```python
from redactor.config import load_config
from redactor.verify.scanner import scan_text

cfg = load_config()
report = scan_text("Contact john@acme.com", cfg)
print(report.counts_by_label)  # {'EMAIL': 1}
print(report.score)            # 3
```

The command line interface honours `cfg.verification.fail_on_residual` and will
exit with a non-zero status when any residual entities are found.

## Name heuristics

`redactor.detect.names_person` offers dependency-free helpers for judging
whether a string looks like a real personal name. Tokens are analysed for
honorifics, initials, particles such as ``de`` or ``van``, hyphenated or
apostrophized surnames and common suffixes like ``Jr.`` or ``III``. Each
candidate receives a deterministic score based on these patterns (base +0.45 for
``given + surname`` with bonuses for initials, particles and suffixes, and
penalties for digits or role words). Names scoring ``≥ 0.60`` are considered
probable. Examples: ``John Doe``, ``J. D. Salinger`` and ``Ludwig van
Beethoven`` score as names, while ``Bank of America``, ``Buyer`` and
``UNITED STATES`` do not. NER remains the primary detector; these heuristics
refine and validate its output.

## Quick start (CLI)

```bash
redactor run --in samples/snippet.txt --out out/sanitized.txt --report out/report
```

Note: currently runs preprocessing only; full redaction pipeline will be wired in later milestones.
