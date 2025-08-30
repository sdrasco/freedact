"""HTML document reader.

Purpose:
    Extract visible text from HTML pages.

Key responsibilities:
    - Strip HTML tags and scripts.
    - Decode entities and normalize whitespace.

Inputs/Outputs:
    - Inputs: HTML string or file path.
    - Outputs: cleaned text string.

Public contracts (planned):
    - `read_html(source)`: Return visible text from HTML.

Notes/Edge cases:
    - Must avoid executing embedded JavaScript.

Dependencies:
    - `beautifulsoup4` (optional).
"""
