"""Custom exception types.

Purpose:
    Define project-specific error classes for clarity.

Key responsibilities:
    - Provide base exception for package errors.
    - Distinguish user vs system errors.

Inputs/Outputs:
    - Inputs: error message.
    - Outputs: exception instances.

Public contracts (planned):
    - `RedactorError`: Base class for package exceptions.
    - `ConfigurationError`: Raised for invalid configuration.

Notes/Edge cases:
    - Exceptions should include context to aid debugging.

Dependencies:
    - Standard library only.
"""
