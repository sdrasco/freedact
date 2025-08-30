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
