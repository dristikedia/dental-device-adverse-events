"""Shared test helpers.

Our scripts start with a number (01_download_data.py), and Python cannot import a
name that starts with a number using a normal import line. load_script() loads the
file by its path instead, so the tests can call the functions inside it.
"""

import importlib.util
from pathlib import Path

import pytest

PROJECT_DIR = Path(__file__).resolve().parent.parent
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def load_script(file_name):
    """Load a script from src/ as a module, without running its main()."""
    path = PROJECT_DIR / "src" / file_name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def fixtures_dir():
    return FIXTURES_DIR
