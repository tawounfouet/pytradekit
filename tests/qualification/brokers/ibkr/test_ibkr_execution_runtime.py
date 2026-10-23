"""Qualification tests for IBKR LOT-06.5 economic-write execution."""

from pathlib import Path

from pytradekit.brokers.adapters.ibkr import (
    IBKR_ECONOMIC_WRITE_VERSION,
    IBKREconomicWriteAdmission,
)

_SOURCE = Path(
    "src/pytradekit/brokers/adapters/ibkr/execution.py"
)


def test_lot06_5_qualifies_single_write_call_sites_and_fail_closed_policy() -> None:
    source = _SOURCE.read_text(encoding="utf-8")

    assert IBKR_ECONOMIC_WRITE_VERSION == "0.8.0b6-lot06.5"
    assert source.count("client.placeOrder(") == 1
    assert source.count("client.cancelOrder(") == 1
    assert "for attempt in" not in source
    assert "while True" not in source
    assert "retry(" not in source
    assert "IBKRPriceIncrementMode.MARKET_RULE" in source
    assert "external_order_id=str(permanent_order_id)" in source


def test_lot06_5_admission_is_explicit_and_paper_scoped() -> None:
    admitted = IBKREconomicWriteAdmission(
        paper_endpoint_verified=True,
        account_ready=True,
        reconciliation_complete=True,
        api_read_only=False,
        economic_write_enabled=True,
    )
    blocked = IBKREconomicWriteAdmission(
        paper_endpoint_verified=True,
        account_ready=True,
        reconciliation_complete=False,
        api_read_only=False,
        economic_write_enabled=True,
    )

    assert admitted.admitted
    assert not blocked.admitted
