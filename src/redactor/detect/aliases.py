"""Alias detector.

Purpose:
    Discover known aliases or AKA references for entities.

Key responsibilities:
    - Scan for patterns like "aka" or "alias" followed by a name.
    - Normalize aliases for linking with primary identities.

Inputs/Outputs:
    - Inputs: text string.
    - Outputs: list of `EntitySpan` for alias names.

Public contracts (planned):
    - `detect(text)`: Return spans for alias mentions.

Notes/Edge cases:
    - Multiple aliases in a single phrase should produce distinct spans.

Dependencies:
    - `patterns` module.
"""
