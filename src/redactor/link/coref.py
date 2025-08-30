"""Coreference resolution utilities.

Purpose:
    Link pronouns and repeated mentions to primary entities.

Key responsibilities:
    - Group spans referring to the same entity across the document.
    - Provide mappings from aliases or pronouns to canonical IDs.

Inputs/Outputs:
    - Inputs: list of `EntitySpan` objects.
    - Outputs: updated spans with `entity_id` fields populated.

Public contracts (planned):
    - `resolve(spans, text)`: Annotate spans with coreference information.

Notes/Edge cases:
    - Requires context windowing to avoid cross-document leaks.

Dependencies:
    - NLP coreference libraries (optional).
"""
