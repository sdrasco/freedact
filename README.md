# redactor

The redactor project aims to provide a privacy-first pipeline for sanitizing legal documents before they are shared with cloud-based language models. It replaces sensitive personal and organizational information with deterministic pseudonyms while preserving the technical facts necessary for analysis. The system operates entirely offline by default and relies on open-source tools for detection and replacement of PII. Each modification is auditable so users can trace the origin and rationale for every change. The goal is to ensure zero leakage of personal data, reproducible outputs, and seamless integration into legal workflows. This repository currently contains only the foundational scaffolding; product functionality will be added in future iterations.

