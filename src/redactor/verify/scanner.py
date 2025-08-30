"""Residual sensitive data scanner.

Purpose:
    Re-scan redacted text for leftover sensitive information.

Key responsibilities:
    - Run detectors on redacted output to ensure completeness.
    - Aggregate results for reporting.

Inputs/Outputs:
    - Inputs: redacted text.
    - Outputs: list of detected spans or empty list.

Public contracts (planned):
    - `scan(text)`: Return residual spans after redaction.

Notes/Edge cases:
    - Must avoid infinite loops if scanners trigger replacements.

Dependencies:
    - `detect` package.
"""
