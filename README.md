# freedact

Offline PII redactor for PDF, DOCX and DOC documents.

## Quick Start

Python 3.9+ is recommended.

```bash
pip install -r requirements.txt
```

## Usage

```bash
python freedact.py input.pdf --pdf
python freedact.py --self-test
```

Outputs:

- `<input>_redacted.docx`
- `<input>_redacted.pdf` (with `--pdf`)
- `<input>_redaction_key.json` (omit with `--no-keep-key`)

## License

Released under the MIT License.

