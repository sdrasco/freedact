"""Evaluation metrics.

Purpose:
    Define metrics for measuring redaction performance.

Key responsibilities:
    - Compute precision, recall, and related statistics.
    - Provide utilities for comparing detector outputs to ground truth.

Inputs/Outputs:
    - Inputs: lists of predicted and true `EntitySpan` objects.
    - Outputs: metric scores as floats.

Public contracts (planned):
    - `precision(references, predictions)`: Compute precision.
    - `recall(references, predictions)`: Compute recall.

Notes/Edge cases:
    - Handling partial overlaps between spans requires special logic.

Dependencies:
    - `detect.base` for `EntitySpan` definitions.
"""
