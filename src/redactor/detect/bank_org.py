"""Bank organization detector.

Purpose:
    Recognize names of financial institutions.

Key responsibilities:
    - Use curated lists or NER models to identify bank names.
    - Emit spans labeled as `BANK_ORG`.

Inputs/Outputs:
    - Inputs: text string.
    - Outputs: list of `EntitySpan` for bank organizations.

Public contracts (planned):
    - `detect(text)`: Return spans for bank names.

Notes/Edge cases:
    - Ambiguous abbreviations require context-aware handling.

Dependencies:
    - Optional external datasets or NER libraries.
"""
