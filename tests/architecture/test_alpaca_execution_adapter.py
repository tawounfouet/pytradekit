"""Architecture and safety fitness functions for LOT-07 Alpaca execution."""

from __future__ import annotations

import ast
from pathlib import Path

EXECUTION_PATH = Path("src/pytradekit/brokers/adapters/alpaca/execution.py")


def _method_calls() -> list[str]:
    tree = ast.parse(
        EXECUTION_PATH.read_text(encoding="utf-8"),
        filename=str(EXECUTION_PATH),
    )
    return [
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    ]


def test_execution_adapter_has_one_submit_and_one_cancel_transport_call_site() -> None:
    calls = _method_calls()

    assert calls.count("submit_order") == 1
    assert calls.count("cancel_order_by_id") == 1


def test_execution_adapter_never_constructs_clients_or_resolves_secrets() -> None:
    source = EXECUTION_PATH.read_text(encoding="utf-8")

    forbidden = (
        "TradingClient(",
        "paper=True",
        "os.environ",
        "os.getenv",
        "SecretsPort",
        "EnvironmentSecrets",
    )
    assert all(item not in source for item in forbidden)


def test_execution_adapter_has_no_live_endpoint_or_retry_loop() -> None:
    source = EXECUTION_PATH.read_text(encoding="utf-8")

    assert "api.alpaca.markets" not in source
    assert "while " not in source
    assert "for attempt" not in source
    assert "retry(" not in source.lower()


def test_query_path_never_calls_submit_transport() -> None:
    tree = ast.parse(
        EXECUTION_PATH.read_text(encoding="utf-8"),
        filename=str(EXECUTION_PATH),
    )
    query_method = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "query_order"
    )
    called = [
        node.func.attr
        for node in ast.walk(query_method)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    ]

    assert "submit_order" not in called
    assert "cancel_order_by_id" not in called
