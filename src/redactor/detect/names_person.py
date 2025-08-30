"""Personal name detector.

Purpose:
    Identify person names using heuristics or NER.

Key responsibilities:
    - Combine pattern matching with NLP models.
    - Output spans labeled as `PERSON`.

Inputs/Outputs:
    - Inputs: text string.
    - Outputs: list of `EntitySpan` for names.

Public contracts (planned):
    - `detect(text)`: Return spans for person names.

Notes/Edge cases:
    - Must handle honorifics and initials gracefully.

Dependencies:
    - `spacy` or similar (optional).
"""
