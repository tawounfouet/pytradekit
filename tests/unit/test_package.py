"""Bootstrap tests for the root package."""

import tomllib
from pathlib import Path

from pytradekit import __version__
from pytradekit.__main__ import main

ROOT = Path(__file__).resolve().parents[2]


def test_bootstrap_version_matches_project_metadata() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert __version__ == project["project"]["version"]


def test_cli_without_arguments_exits_successfully() -> None:
    assert main([]) == 0
