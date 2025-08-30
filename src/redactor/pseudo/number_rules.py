"""Number pseudonymization rules.

Purpose:
    Transform numeric identifiers such as account or phone numbers.

Key responsibilities:
    - Preserve length and formatting (dashes, spaces).
    - Ensure generated numbers are not valid identifiers.

Inputs/Outputs:
    - Inputs: original number string and seed.
    - Outputs: pseudonymized number string.

Public contracts (planned):
    - `apply(number, seed)`: Return pseudonymous number.

Notes/Edge cases:
    - Checksum digits may need recalculation or removal.

Dependencies:
    - `generator` module.
"""
