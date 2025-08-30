"""Common regular expression patterns for detectors.

Purpose:
    Provide reusable regex expressions for identifying sensitive entities.

Key responsibilities:
    - Store compiled patterns for emails, phones, etc.
    - Expose helpers to apply patterns consistently.

Inputs/Outputs:
    - Inputs: text string to search.
    - Outputs: iterator of match objects or spans.

Public contracts (planned):
    - `get_pattern(name)`: Retrieve compiled regex by key.
    - `iter_matches(name, text)`: Yield spans for a pattern.

Notes/Edge cases:
    - Patterns must balance recall and precision.

Dependencies:
    - `re` module.
"""
