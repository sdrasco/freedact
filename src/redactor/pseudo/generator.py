"""Pseudonym generator.

Purpose:
    Produce consistent surrogate values for detected entities.

Key responsibilities:
    - Use seeded random sources to generate pseudonyms.
    - Support multiple entity types (names, addresses, numbers).

Inputs/Outputs:
    - Inputs: entity label, original text, seed.
    - Outputs: pseudonym string.

Public contracts (planned):
    - `generate(label, text, seed)`: Return pseudonym for entity.

Notes/Edge cases:
    - Generated values must avoid real-world collisions.

Dependencies:
    - `seed` module.
"""
