from __future__ import annotations

"""Command line interface for Freedact."""

import argparse
import sys
from pathlib import Path

from .io_utils import read_input_text, write_docx, write_pdf, write_json_key
from .redaction import redact_text_pipeline


HELP_EPILOG = """
Examples:
  python -m freedact input.pdf --pdf --ocr
  python -m freedact input.docx --strict-ids --account-term "Acme Bank"
  python -m freedact input.doc --pdf
  python -m freedact input.pdf --dry-run

Dependencies:
  Required (core): python-docx, reportlab, unidecode, and either pdfplumber or pypdf (for PDF text).
  Optional (.doc): textract and/or antiword (Homebrew: `brew install antiword`).
  Optional OCR: pytesseract, pdf2image (Homebrew: `brew install tesseract poppler`).

Notes:
  • The DOCX output is always attempted. If 'python-docx' is missing, you'll get actionable install guidance.
  • The PDF output is written only when --pdf is passed and 'reportlab' is installed.
  • For PDFs: if text extraction yields nothing and --ocr is provided, OCR is used when pytesseract/pdf2image are installed.
  • All processing is deterministic for a given input and flag set.
  • This tool prioritizes privacy: no network calls, telemetry, or external services.
""".strip()


def build_arg_parser() -> argparse.ArgumentParser:
    desc = (
        "Offline PII redactor for PDF/DOCX/DOC.\n\n"
        "Installs (quick start):\n"
        "  pip install python-docx reportlab unidecode pdfplumber\n"
        "  # or: pip install pypdf\n"
        "Optional:\n"
        "  pip install textract              # .doc support\n"
        "  pip install pytesseract pdf2image # OCR for scanned PDFs (use with --ocr)\n"
        "Homebrew (macOS, optional):\n"
        "  brew install tesseract poppler    # OCR prerequisites for --ocr\n"
        "  brew install antiword             # .doc fallback\n"
    )
    parser = argparse.ArgumentParser(
        prog="freedact",
        description=desc,
        epilog=HELP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.register("action", "true_false", _TrueFalseAction)
    parser.add_argument("input", nargs="?", help="Path to input file (.pdf, .docx, .doc)")
    parser.add_argument("--pdf", action="store_true", help="Also write <input>_redacted.pdf (uses 'reportlab')")
    parser.add_argument("--ocr", action="store_true", help="Enable OCR for PDFs when text is not extractable")
    parser.add_argument("--strict-ids", action="store_true", help="Also redact VIN-like IDs (A-Z0-9, 11–17 chars, no I/O/Q)")
    parser.add_argument("--include-allcaps", action="store_true", help="Treat ALL-CAPS as candidate person names")
    parser.add_argument(
        "--account-term",
        action="append",
        default=[],
        help="Add custom account label/brand to redact (repeatable)",
    )
    parser.add_argument(
        "--mask-mode",
        action="true_false",
        nargs="?",
        const=True,
        default=False,
        help="Use [REDACTED] for names instead of placeholders (default: off)",
    )
    parser.add_argument(
        "--keep-key",
        dest="keep_key",
        action="true_false",
        nargs="?",
        const=True,
        default=True,
        help="Write JSON mapping and append key page (default: on). Disable with --no-keep-key",
    )
    parser.add_argument(
        "--no-keep-key",
        dest="keep_key",
        action="store_false",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be redacted (counts); do not write files",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run built-in acceptance tests and exit",
    )
    return parser


class _TrueFalseAction(argparse.Action):
    """argparse action toggling a bool on presence/absence of a flag."""

    def __call__(self, parser, ns, values, option_string=None):
        setattr(ns, self.dest, values if isinstance(values, bool) else True)


# ----------------------------
# Acceptance tests (--self-test)
# ----------------------------


def self_test() -> int:
    """Run embedded acceptance tests against the redaction pipeline."""

    sample = (
        'Dr. Jane A. Smith ... Hereinafter "Janie". Janie signed.\n'
        "Later, we saw Smith’s car parked outside.\n"
    )
    res = redact_text_pipeline(
        text=sample,
        include_allcaps=False,
        mask_mode=False,
        strict_ids=False,
        extra_account_terms=[],
    )
    assert "John Doe 1" in res.text, "Expected placeholder for person"
    phs = list(res.placeholder_map.keys())
    assert phs and phs[0] == "John Doe 1", "First placeholder should be John Doe 1"
    info = res.placeholder_map["John Doe 1"]
    assert "Jane A. Smith" in info["canonical"], "Canonical full name recorded"
    assert any(a.lower() == "janie" for a in info["aliases"]), "Alias 'Janie' recorded"

    addr_sample = "123 Main St\nBoston, MA 02139\nPO Box 123\nSW1A 1AA\n"
    res2 = redact_text_pipeline(
        text=addr_sample,
        include_allcaps=False,
        mask_mode=False,
        strict_ids=False,
        extra_account_terms=[],
    )
    assert res2.text.count("[REDACTED ADDRESS]") >= 3, "Addresses redacted"

    acct_sample = (
        "My Fidelity brokerage account number is 1234 5678 9012 3456\n"
        "Account #AB-1234567\n"
        "GB29 RBOS 6016 1331 9268 19\n"
        "4111-1111-1111-1111"
    )
    res3 = redact_text_pipeline(
        text=acct_sample,
        include_allcaps=False,
        mask_mode=False,
        strict_ids=False,
        extra_account_terms=[],
    )
    lines = res3.text.splitlines()
    assert "[REDACTED ACCOUNT NAME]" in lines[0], "Account label redacted"
    assert "[REDACTED ACCOUNT NUMBER]" in lines[0], "Account number redacted"
    assert "account #" in lines[1].lower() and "[REDACTED ACCOUNT NUMBER]" in lines[1], "Hash pattern redacted"
    assert "[REDACTED ACCOUNT NUMBER]" in lines[2], "IBAN redacted"
    assert "[REDACTED ACCOUNT NUMBER]" in lines[3], "Card number redacted"

    det_sample = "Dr. Ada Lovelace met Alan Turing. Later, Ada spoke to Turing again."
    res4 = redact_text_pipeline(
        text=det_sample,
        include_allcaps=False,
        mask_mode=False,
        strict_ids=False,
        extra_account_terms=[],
    )
    ph_order = list(res4.placeholder_map.keys())
    assert ph_order == ["John Doe 1", "John Doe 2"], "Deterministic ordering of placeholders"

    assert res.placeholder_map["John Doe 1"]["canonical"].startswith("Jane"), "Key map canonical correct"

    print("All self-tests passed.")
    return 0


# ----------------------------
# Main program
# ----------------------------


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    if args.self_test:
        code = self_test()
        sys.exit(code)

    if not args.input:
        parser.print_help(sys.stderr)
        sys.exit(2)

    in_path = Path(args.input)
    if not in_path.exists():
        sys.stderr.write(f"[ERROR] File not found: {in_path}\n")
        sys.exit(2)

    raw_text = read_input_text(in_path, use_ocr=args.ocr)
    raw_text = raw_text.replace("\r\n", "\n").replace("\r", "\n")

    result = redact_text_pipeline(
        text=raw_text,
        include_allcaps=bool(args.include_allcaps),
        mask_mode=bool(args.mask_mode),
        strict_ids=bool(args.strict_ids),
        extra_account_terms=args.account_term or [],
    )

    persons = result.counts.get("persons", 0)
    addresses = result.counts.get("addresses", 0)
    acct_names = result.counts.get("account_names", 0)
    acct_nums = result.counts.get("account_numbers", 0)
    total_placeholders = len(result.placeholder_map)

    print("=== Redaction Summary ===")
    print(f" Persons replaced:        {persons}")
    print(f" Address lines redacted:  {addresses}")
    print(f" Account names redacted:  {acct_names}")
    print(f" Account numbers redacted:{acct_nums}")
    print(f" Unique persons (key):    {total_placeholders}")
    if args.dry_run:
        print("\n--dry-run: no files written.")
        return

    base = in_path.with_suffix("")
    docx_out = Path(f"{base}_redacted.docx")
    pdf_out = Path(f"{base}_redacted.pdf")
    json_out = Path(f"{base}_redaction_key.json")

    ok_docx = write_docx(docx_out, result.text, result.placeholder_map, keep_key=bool(args.keep_key))
    if ok_docx:
        print(f"Wrote DOCX: {docx_out}")
    else:
        print("Skipped DOCX (missing dependency).")

    if args.pdf:
        ok_pdf = write_pdf(pdf_out, result.text, result.placeholder_map, keep_key=bool(args.keep_key))
        if ok_pdf:
            print(f"Wrote PDF:  {pdf_out}")
        else:
            print("Skipped PDF (missing dependency).")

    if args.keep_key:
        ok_json = write_json_key(json_out, result.placeholder_map)
        if ok_json:
            print(f"Wrote key:  {json_out}")
        else:
            print("Failed to write JSON key.")
    else:
        print("Key disabled (--no-keep-key): JSON/key page not written.")

    print("Done.")


if __name__ == "__main__":
    main()

