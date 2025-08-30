"""Generic date detector.

Purpose:
    Find date expressions in various formats.

Key responsibilities:
    - Match numeric and textual date representations.
    - Normalize to a standard format for comparison.

Inputs/Outputs:
    - Inputs: text string.
    - Outputs: list of `EntitySpan` for date occurrences.

Public contracts (planned):
    - `detect(text)`: Return spans for dates.

Notes/Edge cases:
    - Ambiguous formats (e.g., 01/02/03) require locale awareness.

Dependencies:
    - `dateutil` (optional).
"""
