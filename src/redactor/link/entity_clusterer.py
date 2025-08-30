"""Entity clustering utilities.

Purpose:
    Group related spans into clusters representing the same real-world entity.

Key responsibilities:
    - Apply heuristic or probabilistic clustering.
    - Output cluster identifiers for sets of spans.

Inputs/Outputs:
    - Inputs: list of `EntitySpan` objects.
    - Outputs: mapping of cluster ID to member span IDs.

Public contracts (planned):
    - `cluster(spans)`: Return cluster assignments for spans.

Notes/Edge cases:
    - Clustering should be deterministic given the same inputs.

Dependencies:
    - `networkx` or similar graph libraries (optional).
"""
