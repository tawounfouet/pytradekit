"""Bootstrap tests for the root package."""

from pytradekit import __version__
from pytradekit.__main__ import main


def test_bootstrap_version() -> None:
    assert __version__ == "0.1.0"


def test_cli_without_arguments_exits_successfully() -> None:
    assert main([]) == 0
