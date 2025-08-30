"""Span merging utilities.

Purpose:
    Combine overlapping or adjacent entity spans into coherent results.

Key responsibilities:
    - Resolve conflicts using label precedence rules.
    - Prefer longest spans when overlaps occur.

Inputs/Outputs:
    - Inputs: iterable of `EntitySpan` objects.
    - Outputs: list of merged `EntitySpan` objects.

Public contracts (planned):
    - `merge(spans)`: Return merged spans applying precedence strategy.

Notes/Edge cases:
    - Nested spans from different detectors require deterministic ordering.

Dependencies:
    - `detect.base` for `EntitySpan` definition.
"""
