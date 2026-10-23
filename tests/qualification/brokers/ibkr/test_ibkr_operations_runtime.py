"""Qualification tests for IBKR LOT-06.6 operational runtime."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from pytradekit.brokers import ProviderStateReconciliationRequired
from pytradekit.brokers.adapters.ibkr import (
    IBKR_MARKET_RULE_VERSION,
    IBKR_OPERATIONAL_RUNTIME_VERSION,
    IBKRErrorObservation,
    IBKROperationalGuard,
    normalize_ibkr_market_rule,
)

_MARKET_RULES = Path(
    "src/pytradekit/brokers/adapters/ibkr/market_rules.py"
)
_OPERATIONS = Path(
    "src/pytradekit/brokers/adapters/ibkr/operations_runtime.py"
)
_EXECUTION = Path(
    "src/pytradekit/brokers/adapters/ibkr/execution.py"
)
_NOW = datetime(2026, 10, 23, 10, 55, tzinfo=UTC)


class _Increment:
    def __init__(self, low_edge: float, increment: float) -> None:
        self.lowEdge = low_edge
        self.increment = increment


def _error(code: int) -> IBKRErrorObservation:
    return IBKRErrorObservation(
        request_id=-1,
        code=code,
        message=f"provider code {code}",
        observed_at=_NOW,
    )


def test_lot06_6_qualifies_dynamic_market_rule_runtime() -> None:
    rule = normalize_ibkr_market_rule(
        market_rule_id=26,
        raw_increments=[
            _Increment(0.0, 0.01),
            _Increment(100.0, 0.05),
        ],
    )

    assert IBKR_MARKET_RULE_VERSION == "0.8.0b7-lot06.6"
    assert rule.validates(
        __import__("decimal", fromlist=["Decimal"]).Decimal("100.10")
    )
    assert not rule.validates(
        __import__("decimal", fromlist=["Decimal"]).Decimal("100.12")
    )


def test_lot06_6_qualifies_reconnect_containment_without_replay() -> None:
    guard = IBKROperationalGuard(
        socket_connected=True,
        provider_connected=True,
        reconciliation_complete=True,
    )

    guard.observe_error(_error(1100), operation="provider_event")
    guard.observe_error(_error(1102), operation="provider_event")

    with pytest.raises(ProviderStateReconciliationRequired):
        guard.require_write_allowed(operation="submit")

    guard.mark_reconciled()
    guard.require_write_allowed(operation="submit")

    operations = _OPERATIONS.read_text(encoding="utf-8")
    execution = _EXECUTION.read_text(encoding="utf-8")
    market_rules = _MARKET_RULES.read_text(encoding="utf-8")

    assert IBKR_OPERATIONAL_RUNTIME_VERSION == "0.8.0b7-lot06.6"
    assert ".placeOrder(" not in operations
    assert ".cancelOrder(" not in operations
    assert execution.count("client.placeOrder(") == 1
    assert execution.count("client.cancelOrder(") == 1
    assert market_rules.count("request.reqMarketRule(") == 1
    assert "Watchdog" not in operations
