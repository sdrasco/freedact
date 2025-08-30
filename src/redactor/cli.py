"""Command-line interface.

Purpose:
    Provide entry points for running the redaction pipeline from the terminal.

Key responsibilities:
    - Parse command-line arguments.
    - Invoke high-level pipeline functions.

Inputs/Outputs:
    - Inputs: CLI arguments and options.
    - Outputs: exit codes and console output.

Public contracts (planned):
    - `main(argv=None)`: Parse args and execute commands.

Notes/Edge cases:
    - Should minimize startup time and avoid heavy imports when unused.

Dependencies:
    - `argparse` from standard library.
"""
