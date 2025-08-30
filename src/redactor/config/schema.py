"""Configuration schema definitions.

Purpose:
    Define structured configuration models for the redaction pipeline.

Key responsibilities:
    - Provide schemas for configuration sections (preprocess, detect, etc.).
    - Validate user-supplied configuration against defaults.

Inputs/Outputs:
    - Inputs: raw configuration data as dictionaries or YAML text.
    - Outputs: validated configuration objects.

Public contracts (planned):
    - `load_defaults()`: Load default configuration values.
    - `validate(config_data)`: Validate user configuration and merge with defaults.

Notes/Edge cases:
    - Schema versioning must be handled to avoid breaking changes.

Dependencies:
    - `pydantic` (optional for validation).
"""
