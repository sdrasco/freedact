"""Phone number detector.

Purpose:
    Locate telephone numbers in free-form text.

Key responsibilities:
    - Use regex patterns for international formats.
    - Normalize captured numbers for comparison.

Inputs/Outputs:
    - Inputs: text string.
    - Outputs: list of `EntitySpan` representing phone numbers.

Public contracts (planned):
    - `detect(text)`: Return spans for phone numbers.

Notes/Edge cases:
    - Extension numbers and short codes require special handling.

Dependencies:
    - `patterns` module for regexes.
"""
