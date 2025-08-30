# freedact

Self-contained, offline PII redactor for PDF/DOCX/DOC.

Freedact scans documents and redacts:

- Persons: replaces names with deterministic placeholders (John Doe 1, 2, …) or `[REDACTED]`.
- Addresses: whole-line redaction to `[REDACTED ADDRESS]`.
- Account names: labels/brands → `[REDACTED ACCOUNT NAME]`.
- Account numbers/IDs: card-like, IBAN-like, long digit runs → `[REDACTED ACCOUNT NUMBER]`.

Works entirely offline; no telemetry or network calls.

## Quick Start

- Python 3.9+ recommended.
- Install core packages (in a virtualenv if you like):

  ```bash
  pip install -r requirements.txt
  ```

- Optional support (only if you need them):
  - `.doc` files: `pip install textract` (or install `antiword` via Homebrew)
  - OCR for scanned PDFs: `pip install pytesseract pdf2image` and system tools `brew install tesseract poppler`

## Usage

```
python freedact.py input.pdf --pdf --ocr
python freedact.py input.docx --strict-ids --account-term "Acme Bank"
python freedact.py input.doc --pdf
python freedact.py input.pdf --dry-run
python freedact.py --self-test
```

Outputs (depending on flags):

- `<input>_redacted.docx` (always attempted)
- `<input>_redacted.pdf` (when `--pdf` is passed)
- `<input>_redaction_key.json` (mapping placeholders to originals; disable with `--no-keep-key`)

## One‑liner: Create and push GitHub repo

If you use GitHub CLI (`gh`) and are already authenticated, run this in the project directory to create `sdrasco/freedact` and push the current contents:

```bash
gh repo create sdrasco/freedact --public --source=. --remote=origin --push
```

Alternative (plain git + existing empty repo):

```bash
git init && git add . && git commit -m "Initial commit" \
  && git branch -M main \
  && git remote add origin git@github.com:sdrasco/freedact.git \
  && git push -u origin main
```

## Notes

- This tool operates offline. Some features require optional dependencies as noted above.
- Review outputs before distributing redacted documents.

