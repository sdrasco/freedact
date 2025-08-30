"""Account identifier detector.

Purpose:
    Detect bank or credit account numbers in text.

Key responsibilities:
    - Match sequences matching account number formats.
    - Apply checksum algorithms where applicable.

Inputs/Outputs:
    - Inputs: text string.
    - Outputs: list of `EntitySpan` for account identifiers.

Public contracts (planned):
    - `detect(text)`: Return spans for account numbers.

Notes/Edge cases:
    - Should minimize false positives from random digit strings.

Dependencies:
    - `patterns` module and `checksum` utilities (optional).
"""
