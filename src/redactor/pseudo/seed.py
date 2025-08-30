"""Pseudorandom seed management.

Purpose:
    Provide deterministic seeding for pseudonym generation.

Key responsibilities:
    - Derive seeds using HMAC with a secret key.
    - Ensure reproducibility across runs without exposing the secret.

Inputs/Outputs:
    - Inputs: secret from environment, optional user identifier.
    - Outputs: integer seed values for random generators.

Public contracts (planned):
    - `derive_seed(key_material)`: Return deterministic seed.

Notes/Edge cases:
    - Secret key must never be persisted; environment only.

Dependencies:
    - `hashlib` and `hmac` from standard library.
"""
