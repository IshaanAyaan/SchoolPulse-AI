"""Shared test fixtures. Puts the package on sys.path and loads the example config."""

import os
import sys

import pytest

_HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(_HERE, "..", "src"))

from aqualert.config import load_config  # noqa: E402

CONFIG_PATH = os.path.join(_HERE, "..", "config.example.yaml")


@pytest.fixture
def cfg():
    return load_config(CONFIG_PATH)
