"""HTML document writer.

Purpose:
    Serialize redacted text into a minimal HTML page.

Key responsibilities:
    - Wrap text in basic HTML structure.
    - Escape special characters appropriately.

Inputs/Outputs:
    - Inputs: text string, output path.
    - Outputs: HTML file on disk.

Public contracts (planned):
    - `write_html(text, path)`: Save text within an HTML template.

Notes/Edge cases:
    - CSS and JavaScript are intentionally omitted.

Dependencies:
    - standard library only.
"""
