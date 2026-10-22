"""Unit tests for full trading readiness aggregation."""

from pytradekit.runtime import (
    ReadinessCheck,
    ReadinessCheckStatus,
    TradingReadinessReport,
    TradingReadinessState,
)


def test_trading_readiness_requires_all_checks_and_zero_gaps() -> None:
    report = TradingReadinessReport(
        provider="alpaca",
        environment="PAPER",
        account="********1234",
        checks=(
            ReadinessCheck(
                "startup",
                ReadinessCheckStatus.PASS,
                "ok",
            ),
        ),
        gaps=(),
    )

    assert report.state is TradingReadinessState.TRADING_READY
    assert report.trading_ready is True


def test_any_reconciliation_gap_blocks_trading_ready() -> None:
    report = TradingReadinessReport(
        provider="alpaca",
        environment="PAPER",
        account="********1234",
        checks=(
            ReadinessCheck(
                "startup",
                ReadinessCheckStatus.PASS,
                "ok",
            ),
        ),
        gaps=("position mismatch",),
    )

    assert report.state is TradingReadinessState.NOT_READY
    assert report.trading_ready is False
