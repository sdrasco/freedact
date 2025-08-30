"""Alias resolution utilities.

Purpose:
    Connect detected aliases to their primary entities.

Key responsibilities:
    - Maintain mapping of alias spans to canonical entity identifiers.
    - Provide lookup functions for downstream pseudonymization.

Inputs/Outputs:
    - Inputs: list of `EntitySpan` objects with alias labels.
    - Outputs: updated spans with `entity_id` filled based on alias matches.

Public contracts (planned):
    - `resolve_aliases(spans)`: Assign `entity_id` for alias spans.

Notes/Edge cases:
    - Different entities may share identical aliases; context is needed.

Dependencies:
    - Standard library only.
"""
