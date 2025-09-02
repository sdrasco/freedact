<p align="center">
  <img src="banner.png" alt="Freedact Project Banner" />
</p>

Freedact automatically replaces private details in text with consistent, realistic pseudonyms. It runs entirely on your own machine, so the redaction itself never uses the cloud or introduces new risks. The result is a version you can safely share with AI tools or other online services without exposing the original sensitive information.

## Table of Contents

- [Features](#features)
- [Install](#install)
  - [Extras](#extras)
- [Quick Start (CLI)](#quick-start-cli)
- [Configuration & Secrets](#configuration--secrets)
- [Architecture](#architecture)
  - [Pipeline, End to End](#pipeline-end-to-end)
- [Pseudonymization](#pseudonymization)
  - [Names, Orgs & Banks](#names-orgs--banks)
  - [Addresses](#addresses)
  - [Dates vs DOB](#dates-vs-dob)
  - [Aliases & Consistency](#aliases--consistency)
  - [Replacement Planning & Safety](#replacement-planning--safety)
- [Verification & Leakage Scoring](#verification--leakage-scoring)
- [Audit & Diff Artifacts](#audit--diff-artifacts)
- [Fixtures](#fixtures)
- [Metrics](#metrics)
- [Performance (profiling)](#performance-profiling)
- [Fuzz Testing](#fuzz-testing)
- [Contributing](#contributing)



## Features

- **Detectors** for emails, phones, bank/org names, addresses (line + merged blocks), account/ID numbers (CC, ABA routing, IBAN, SSN/EIN, BIC), DOB vs generic dates, legal alias terms, and optional NER (spaCy).
- **Linking & coref** to keep mentions of the same person/party consistent (optional fastcoref with regex fallback).
- **Shape‑preserving pseudonyms** for people/organizations, banks, addresses, and numeric IDs (Luhn/ABA‑valid where appropriate).
- **Replacement planner & applier** (reverse, chunked) with strong validation and idempotence.
- **Safety guards** ensure generated emails use `example.org`, phones use safe `555` patterns, and IDs don’t collide with sensitive real values.
- **Verification scanner** to re‑detect residual PII and compute a leakage score.
- **Audit bundle** (`audit.json`, `diff.html`, `plan.json`, `verification.json`) with secret‑safety checks.
- **Fixtures, metrics, fuzz & perf** harnesses to keep quality high in CI.
- **CLI** with strict mode and rich but test‑friendly help output.



## Install

The base install provides the core pipeline and common detectors:

```bash
pip install -e .
```

### Extras

Install only what you need, or everything:

```bash
pip install -e .[dev]         # linters, mypy, pytest, coverage
pip install -e .[addresses]   # usaddress for address line parsing
pip install -e .[ner]         # spaCy for NER (optional)
pip install -e .[coref]       # fastcoref + torch (optional)
pip install -e .[all]         # all optional features
```

NER and coreference are optional and disabled by default. The base install already includes phone and account detectors.



## Quick Start (CLI)

```bash
redactor run   --in samples/snippet.txt   --out out/sanitized.txt   --report out/report   --strict
```

- `--strict` enforces zero residuals; the command exits with code `6` if verification finds PII.
- When `--report DIR` is provided, `verification.json` and audit/diff artifacts are written even on strict failure.

Useful toggles:

- `--keep-roles` / `--redact-roles` — preserve or pseudonymize role labels like “Buyer”
- `--enable-ner` / `--disable-ner` — toggle the spaCy NER
- `--require-secret` — fail fast if a seed secret is not configured

Exit codes: `0` success, `3` I/O error, `4` configuration/secret error, `5` pipeline error, `6` verification failure.

### Safe profile (quick start for legal text)

```bash
redactor run --in input.txt --out out.txt --report report --config examples/safe-overrides.yml
```

Disables NER/coref and generic account IDs while protecting headings and standalone locations.



## Configuration & Secrets

Load defaults via `load_config()` and override with your own YAML. For deterministic pseudonyms across runs, set a seed secret:

```bash
export REDACTOR_SEED_SECRET="your-secret-bytes"
```

Use `--require-secret` to enforce presence in automation. The seed’s *value* is never written to artifacts; only a boolean `seed_present` is recorded. The report writer refuses to write if a secret‑like value would be serialized.



## Architecture

### Top‑level modules

- `config` — configuration & schema
- `io` — file readers/writers
- `preprocess` — normalization & segmentation with char‑maps
- `detect` — detectors (email/phone/account/address/date/DOB/aliases/bank, optional NER)
- `link` — alias resolution, span merge, optional coref
- `pseudo` — seeded ID/key derivation & shape‑preserving generators
- `replace` — plan builder & fast reverse applier
- `verify` — residual scan & leakage scoring; audit/diff writer
- `evaluation` — fixtures, metrics, fuzz, perf
- `utils` — shared helpers

### Pipeline, End to End

1) **Preprocess** (normalize, build line index)  
2) **Detect** entities (pattern and optional NER)  
3) **Merge** address lines into blocks; **resolve aliases**; **merge spans** globally  
4) **Plan** replacements (deterministic pseudonyms) and **apply** in reverse  
5) **Verify** residual PII; compute leakage score  
6) **Report**: write `audit.json`, `diff.html`, `plan.json`, `verification.json` (optional)



## Pseudonymization

### Names, Orgs & Banks

Deterministic, shape‑preserving replacements keep token counts, casing, and punctuation (e.g., `J.D.` → initials form; `Acme LLC` → `Apex Vector LLC`; `Chase Bank, N.A.` → `Summit Bank, N.A.`).

### Addresses

Street, unit, city/state/ZIP and PO Box lines are detected (via `usaddress`) and merged into a multi‑line block so the whole address is replaced at once.

### Dates vs DOB

General dates (`DATE_GENERIC`) are preserved by default; only dates clearly marked as birthdates (`DOB`, with triggers like “DOB”, “D.O.B.”, “Date of Birth”) are replaced, with formats preserved (e.g., `M/D/YYYY` vs `Month D, YYYY`).

### Aliases & Consistency

Legal alias labels (e.g., `hereinafter`, `a/k/a`, `d/b/a`) are detected as `ALIAS_LABEL`. We link alias mentions and subjects so pseudonyms remain consistent. Role aliases (e.g., “Buyer”) can be preserved while keeping links for consistency.

### Replacement Planning & Safety

Plan entries hold exact `[start,end)` ranges and their replacements. We perform bounded safety checks at plan time to coerce risky candidates into safe shapes (emails → `example.org`, phones → `555` patterns, IDs with checksums or non‑colliding digits). Application is reverse, chunked, validated, and idempotent.

Safety is enforced *by construction*: unsafe candidates are rejected and
deterministically regenerated with salted keys up to two times.  Retry counts
and reasons are recorded in the audit summary for traceability.



## Verification & Leakage Scoring

After applying the plan, we re‑run the detectors over the redacted text, ignore our own known replacements, and compute an overall **leakage score** with per‑label residual counts. The CLI enforces strict mode when requested.



## Audit & Diff Artifacts

`write_report_bundle(report_dir, ...)` writes:

- **audit.json** — one entry per replacement (label, original/replacement text, offsets, deltas, metadata)  
- **diff.html** — side‑by‑side, highlighted before/after view  
- **plan.json** — minimal plan for reference  
- **verification.json** — verification report (if provided)

Artifacts intentionally contain original PII (audit.json); keep them local. The writer refuses to write if a secret‑like value would be serialized.



## Fixtures

A small corpus under `evaluation/fixtures` pairs `.txt` content with `.spans.json` annotations using 0‑based, half‑open indices. Run the integrity checks:

```bash
pytest -k fixtures_integrity
```

These samples use synthetic PII and are not for external sharing.



## Metrics

`evaluation.metrics` computes precision/recall/F1 per label using IoU matching (default 0.5). Supports *coarse* labels and *fine* account subtypes (e.g., `ACCOUNT_ID:iban`).

```python
from redactor.config import load_config
from evaluation.metrics import evaluate_all_fixtures

cfg = load_config()
results = evaluate_all_fixtures(cfg)
print(results["aggregate"].micro)
```



## Performance (profiling)

Programmatic per‑stage timings:

```python
from redactor.config import load_config
from evaluation.perf import profile_pipeline

cfg = load_config()
timings = profile_pipeline("example text", cfg)
```

CLI with `--verbose` prints per‑stage timings. The `profile_fixtures` helper uses `REDACTOR_PERF_REPEAT` to synthesize large inputs.



## Fuzz Testing

Deterministic variants (zero‑width chars, NBSPs, hyphenation, quote and label variants, mixed EOLs) stress the pipeline:

```bash
REDACTOR_FUZZ_N=50 pytest -k fuzz
```

Seeds derive from fixture names for reproducibility.



## Contributing

- Keep PRs scope‑small and add tests.
- Run the full suite locally: `ruff check . && black --check . && mypy . && pytest -q`.
- Optional: enable extras you need (`[addresses]`, `[ner]`, `[coref]`).


