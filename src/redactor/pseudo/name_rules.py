"""Name pseudonymization rules.

Purpose:
    Define how personal names should be transformed into pseudonyms.

Key responsibilities:
    - Preserve formatting such as capitalization and initials.
    - Support deterministic mapping for repeated names.

Inputs/Outputs:
    - Inputs: original name string and seed.
    - Outputs: pseudonymized name string.

Public contracts (planned):
    - `apply(name, seed)`: Return pseudonym for a name.

Notes/Edge cases:
    - Must handle multi-part names and honorifics.

Dependencies:
    - `generator` module.
"""
