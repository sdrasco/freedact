"""Email address detector.

Purpose:
    Identify email addresses in text using pattern matching.

Key responsibilities:
    - Apply regex patterns for various email formats.
    - Emit `EntitySpan` objects labeled as emails.

Inputs/Outputs:
    - Inputs: text string.
    - Outputs: list of `EntitySpan` representing emails.

Public contracts (planned):
    - `detect(text)`: Return spans for email addresses.

Notes/Edge cases:
    - Should ignore false positives in code blocks or URLs.

Dependencies:
    - `patterns` module for regexes.
"""
