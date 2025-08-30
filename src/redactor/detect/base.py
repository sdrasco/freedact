"""Detection base definitions.

Purpose:
    Outline common data structures and interfaces for all detectors.

Key responsibilities:
    - Define the `EntitySpan` dataclass capturing detected entity metadata.
    - Specify the `Detector` protocol for pluggable detectors.

Inputs/Outputs:
    - Inputs: text string and optional context information.
    - Outputs: list of `EntitySpan` instances.

Public contracts (planned):
    - `EntitySpan`: (start, end, text, label, source, confidence, attrs, entity_id).
    - `Detector.detect(text, context=None)`: Return list of `EntitySpan`.

Notes/Edge cases:
    - Offsets must refer to the original text prior to normalization.

Dependencies:
    - `dataclasses` from standard library.
"""
