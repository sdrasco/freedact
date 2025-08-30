"""Plain text reader.

Purpose:
    Load UTF-8 encoded text files into memory.

Key responsibilities:
    - Open text files and return their contents as strings.
    - Handle newline normalization where needed.

Inputs/Outputs:
    - Inputs: file path or file-like object.
    - Outputs: raw text string.

Public contracts (planned):
    - `read_text(path)`: Return file contents as text.

Notes/Edge cases:
    - Large files may require streaming support.

Dependencies:
    - `pathlib`.
"""
