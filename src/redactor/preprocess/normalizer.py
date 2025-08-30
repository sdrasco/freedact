"""Text normalization utilities.

Purpose:
    Standardize input text before detection.

Key responsibilities:
    - Normalize whitespace and Unicode characters.
    - Apply configurable lowercasing or transliteration.

Inputs/Outputs:
    - Inputs: raw text string.
    - Outputs: normalized text string.

Public contracts (planned):
    - `normalize(text, config)`: Return normalized text according to settings.

Notes/Edge cases:
    - Should preserve original offsets when possible.

Dependencies:
    - `unicodedata`.
"""
