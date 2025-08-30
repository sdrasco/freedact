"""Text segmentation utilities.

Purpose:
    Split normalized text into logical units such as sentences or paragraphs.

Key responsibilities:
    - Provide sentence and paragraph tokenization.
    - Preserve offset mappings for each segment.

Inputs/Outputs:
    - Inputs: normalized text string.
    - Outputs: list of segments with offsets.

Public contracts (planned):
    - `segment(text)`: Return iterable of segments.

Notes/Edge cases:
    - Multilingual segmentation may require external libraries.

Dependencies:
    - `regex` or `nltk` (optional).
"""
