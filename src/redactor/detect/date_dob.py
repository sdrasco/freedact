"""Date-of-birth detector.

Purpose:
    Identify dates that likely correspond to a person's birthdate.

Key responsibilities:
    - Use contextual cues around generic dates to infer DOB.
    - Emit spans labeled as `DATE_DOB`.

Inputs/Outputs:
    - Inputs: text string.
    - Outputs: list of `EntitySpan` for DOB mentions.

Public contracts (planned):
    - `detect(text)`: Return spans for probable birth dates.

Notes/Edge cases:
    - Age references ("born on") improve precision.

Dependencies:
    - Relies on `date_generic` detector output.
"""
