"""Architecture checks for the frozen Alpaca 0.5 integration contract."""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path

CONTRACT_PATH = Path("src/pytradekit/brokers/adapters/alpaca/contract.py")
CONTROLLED_PROBE_PATH = Path(
    "src/pytradekit/brokers/adapters/alpaca/controlled_order_probe.py"
)
PYPROJECT_PATH = Path("pyproject.toml")


def _invoked_methods(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    ]


def test_alpaca_dependency_remains_exactly_pinned_for_contract_freeze() -> None:
    pyproject = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    alpaca_extra = pyproject["project"]["optional-dependencies"]["alpaca"]

    assert alpaca_extra == ["alpaca-py==0.44.0"]


def test_frozen_contract_is_paper_only() -> None:
    source = CONTRACT_PATH.read_text(encoding="utf-8")

    assert 'ALPACA_ENVIRONMENT: Final = "PAPER"' in source
    assert "TRADING_LIVE" not in source
    assert "api.alpaca.markets" not in source


def test_controlled_probe_keeps_single_submit_and_cancel_call_sites() -> None:
    methods = _invoked_methods(CONTROLLED_PROBE_PATH)

    assert methods.count("submit_order") == 1
    assert methods.count("cancel_order_by_id") == 1


def test_controlled_probe_still_forces_sdk_command_retry_counter_to_zero() -> None:
    source = CONTROLLED_PROBE_PATH.read_text(encoding="utf-8")

    assert "self._retry = 0" in source


def test_contract_does_not_expand_into_live_or_unsupported_provider_operations() -> None:
    source = CONTRACT_PATH.read_text(encoding="utf-8")

    forbidden = (
        "replace_order_by_id",
        "close_all_positions",
        "close_position",
        "exercise_options_position",
        "BrokerClient",
    )
    assert all(item not in source for item in forbidden)
