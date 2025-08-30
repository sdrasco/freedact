"""Replacement plan builder.

Purpose:
    Construct a set of operations to replace detected spans.

Key responsibilities:
    - Combine spans and pseudonyms into an ordered plan.
    - Ensure offsets remain valid after sequential replacements.

Inputs/Outputs:
    - Inputs: original text, list of spans, pseudonym generator.
    - Outputs: replacement plan data structure.

Public contracts (planned):
    - `build_plan(text, spans, pseudo)`: Create plan for text replacement.

Notes/Edge cases:
    - Overlapping spans must be resolved before plan creation.

Dependencies:
    - `link` and `pseudo` modules.
"""
