"""PDF document reader.

Purpose:
    Extract text from PDF files using lightweight parsing.

Key responsibilities:
    - Convert PDF pages to text strings.
    - Maintain page boundaries for downstream processing.

Inputs/Outputs:
    - Inputs: path to a PDF file.
    - Outputs: list of page texts or combined string.

Public contracts (planned):
    - `read_pdf(path)`: Yield text content from each page.

Notes/Edge cases:
    - Scanned PDFs may require OCR (not included).

Dependencies:
    - `pdfplumber` or similar (optional).
"""
