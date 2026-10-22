"""Architecture safety checks for the Alpaca PAPER discovery probe."""

from __future__ import annotations

import ast
from pathlib import Path

PROBE_PATH = Path("src/pytradekit/brokers/adapters/alpaca/read_only_probe.py")
FORBIDDEN_PROVIDER_WRITE_METHODS = {
    "submit_order",
    "replace_order_by_id",
    "cancel_orders",
    "cancel_order_by_id",
    "close_all_positions",
    "close_position",
    "exercise_options_position",
}


def test_alpaca_read_only_probe_has_no_provider_write_calls() -> None:
    tree = ast.parse(PROBE_PATH.read_text(encoding="utf-8"), filename=str(PROBE_PATH))
    invoked_methods = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }

    assert not FORBIDDEN_PROVIDER_WRITE_METHODS.intersection(invoked_methods)


def test_alpaca_read_only_probe_has_no_live_endpoint_reference() -> None:
    source = PROBE_PATH.read_text(encoding="utf-8")

    assert "TRADING_LIVE" not in source
    assert "api.alpaca.markets" not in source
    assert source.count("paper=True") >= 2
