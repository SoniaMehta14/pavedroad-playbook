"""Scaffold smoke tests.

These exist to prove the packaging, import paths, and CI wiring work before any
real components land. Each later phase replaces reliance on these with
substantive tests for its own components.
"""

import importlib

import pytest

PACKAGES = ["interop", "orchestration", "evals", "adapters"]


@pytest.mark.parametrize("package", PACKAGES)
def test_package_imports(package: str) -> None:
    module = importlib.import_module(package)
    assert module.__doc__, f"{package} must state the enterprise problem it solves"
