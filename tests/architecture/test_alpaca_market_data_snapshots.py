"""Architecture fitness functions for LOT-08 Alpaca read-only snapshots."""

import ast
from pathlib import Path

SNAPSHOTS_PATH = Path("src/pytradekit/brokers/adapters/alpaca/snapshots.py")
RESOLVER_PATH = Path("src/pytradekit/brokers/adapters/alpaca/reference_resolver.py")
QUOTE_PATH = Path("src/pytradekit/market_data/domain/quote.py")


def test_snapshot_layer_is_strictly_read_only() -> None:
    source = SNAPSHOTS_PATH.read_text(encoding="utf-8")

    forbidden = (
        "submit_order",
        "cancel_order",
        "replace_order",
        "close_position",
        "close_all_positions",
        "exercise",
        "delete(",
        "post(",
        "patch(",
    )
    assert all(item not in source for item in forbidden)


def test_snapshot_layer_is_hard_locked_to_iex_for_latest_equity_quote() -> None:
    source = SNAPSHOTS_PATH.read_text(encoding="utf-8")

    assert "DataFeed.IEX" in source
    assert "DataFeed.SIP" not in source
    assert "DataFeed.OTC" not in source


def test_snapshot_layer_does_not_construct_clients_or_resolve_secrets() -> None:
    source = SNAPSHOTS_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(SNAPSHOTS_PATH))
    constructed = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert "TradingClient" not in constructed
    assert "StockHistoricalDataClient" not in constructed
    assert "SecretsPort" not in source
    assert "EnvironmentSecrets" not in source
    assert "os.environ" not in source
    assert "os.getenv" not in source


def test_snapshot_layer_does_not_depend_on_execution_port() -> None:
    source = SNAPSHOTS_PATH.read_text(encoding="utf-8")

    assert "ExecutionPort" not in source
    assert "pytradekit.orders.ports" not in source


def test_canonical_quote_has_no_alpaca_dependency() -> None:
    source = QUOTE_PATH.read_text(encoding="utf-8")

    assert "alpaca" not in source.lower()


def test_static_reference_resolver_contains_no_provider_network_calls() -> None:
    source = RESOLVER_PATH.read_text(encoding="utf-8")

    forbidden = (
        "get_asset",
        "get_all_positions",
        "get_stock_latest_quote",
        "submit_order",
    )
    assert all(item not in source for item in forbidden)