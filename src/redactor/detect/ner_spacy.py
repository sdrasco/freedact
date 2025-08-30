"""spaCy-based NER detector.

Purpose:
    Use spaCy's statistical models to find entities not covered by rules.

Key responsibilities:
    - Load spaCy language models lazily.
    - Convert model entities to `EntitySpan` objects.

Inputs/Outputs:
    - Inputs: text string.
    - Outputs: list of `EntitySpan` from spaCy entities.

Public contracts (planned):
    - `detect(text)`: Run spaCy NER on text.

Notes/Edge cases:
    - Heavy dependency; module should fail gracefully if spaCy is missing.

Dependencies:
    - `spacy` (optional, heavy).
"""
