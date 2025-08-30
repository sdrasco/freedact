"""Text span utilities.

Purpose:
    Provide helper functions for manipulating text spans and offsets.

Key responsibilities:
    - Convert between character and byte offsets.
    - Adjust spans after text modifications.

Inputs/Outputs:
    - Inputs: span tuples or `EntitySpan` objects.
    - Outputs: transformed spans or offset mappings.

Public contracts (planned):
    - `shift_spans(spans, index, delta)`: Adjust spans after insertion.

Notes/Edge cases:
    - Unicode code points vs byte offsets must be handled carefully.

Dependencies:
    - Standard library only.
"""
