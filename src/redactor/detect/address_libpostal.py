"""Address detector using libpostal.

Purpose:
    Parse and identify mailing addresses in text.

Key responsibilities:
    - Leverage libpostal for normalization and parsing.
    - Emit spans labeled as `ADDRESS` with structured components.

Inputs/Outputs:
    - Inputs: text string.
    - Outputs: list of `EntitySpan` for addresses.

Public contracts (planned):
    - `detect(text)`: Return spans representing addresses.

Notes/Edge cases:
    - Requires libpostal data installation; handle absence gracefully.

Dependencies:
    - `libpostal` (optional, heavy).
"""
