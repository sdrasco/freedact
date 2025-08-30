# Tests for verifying the package skeleton is importable and documented.

import importlib
import pkgutil

import redactor


def test_root_package_has_docstring() -> None:
    """The root package should define a module docstring."""
    assert redactor.__doc__ and redactor.__doc__.strip()


def test_all_modules_have_docstrings() -> None:
    """Ensure every submodule can be imported and has a docstring."""
    for module_info in pkgutil.walk_packages(redactor.__path__, redactor.__name__ + "."):
        module = importlib.import_module(module_info.name)
        assert module.__doc__ and module.__doc__.strip(), f"Missing docstring in {module_info.name}"
