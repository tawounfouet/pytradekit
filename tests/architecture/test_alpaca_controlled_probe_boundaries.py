"""Architecture safety checks for the controlled Alpaca PAPER order probe."""

from __future__ import annotations

import ast
from pathlib import Path

PROBE_PATH = Path("src/pytradekit/brokers/adapters/alpaca/controlled_order_probe.py")


def _function_calls(function_name: str, method_name: str) -> int:
    tree = ast.parse(PROBE_PATH.read_text(encoding="utf-8"), filename=str(PROBE_PATH))

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name != function_name:
            continue
        return sum(
            1
            for child in ast.walk(node)
            if isinstance(child, ast.Call)
            and isinstance(child.func, ast.Attribute)
            and child.func.attr == method_name
        )

    raise AssertionError(f"Function {function_name} not found")


def test_alpaca_controlled_probe_has_no_live_endpoint_reference() -> None:
    source = PROBE_PATH.read_text(encoding="utf-8")

    assert "TRADING_LIVE" not in source
    assert "api.alpaca.markets" not in source
    assert source.count("paper=True") >= 2


def test_command_client_explicitly_disables_sdk_retries() -> None:
    source = PROBE_PATH.read_text(encoding="utf-8")

    assert "self._retry = 0" in source


def test_submit_once_contains_exactly_one_sdk_submit_call() -> None:
    assert _function_calls("submit_once", "submit_order") == 1


def test_cancel_once_contains_exactly_one_sdk_cancel_call() -> None:
    assert _function_calls("cancel_once", "cancel_order_by_id") == 1
