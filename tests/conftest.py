"""Shared fixtures for the abvio test suite."""

import os
from pathlib import Path

import pytest
from pymatgen.core import Structure


def pytest_configure(config):
    config.addinivalue_line("markers", "network: mark test as requiring network access")


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--network", default=False):
        skip = pytest.mark.skip(reason="pass --network to run network tests")
        for item in items:
            if item.get_closest_marker("network"):
                item.add_marker(skip)


def pytest_addoption(parser):
    parser.addoption("--network", action="store_true", default=False,
                     help="Run tests that require network access")

TESTS_DIR      = Path(__file__).parent
STRUCTURES_DIR = TESTS_DIR / "structures"
FILES_DIR      = TESTS_DIR / "files"
VASPSETS_DIR   = TESTS_DIR / "vaspsets"


@pytest.fixture(scope="session")
def structures_dir() -> Path:
    return STRUCTURES_DIR


@pytest.fixture(scope="session")
def files_dir() -> Path:
    return FILES_DIR


@pytest.fixture(scope="session")
def perovskite(structures_dir) -> Structure:
    return Structure.from_file(structures_dir / "CaTiO3.vasp")


@pytest.fixture(scope="session")
def fluorite(structures_dir) -> Structure:
    return Structure.from_file(structures_dir / "CaF2.vasp")
