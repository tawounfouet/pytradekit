"""Unit tests for full trading readiness aggregation."""

from pytradekit.reconciliation import ConsistencyStatus, StateConfidence
from pytradekit.runtime import (
    ReadinessCheck,
    ReadinessCheckStatus,
    TradingReadinessReport,
    TradingReadinessState,
)


def _passing_report(
    *,
    consistency_status: ConsistencyStatus | None = None,
    state_confidence: StateConfidence | None = None,
) -> TradingReadinessReport:
    return TradingReadinessReport(
        provider="alpaca",
        environment="PAPER",
        account="********1234",
        checks=(ReadinessCheck("startup", ReadinessCheckStatus.PASS, "ok"),),
        gaps=(),
        consistency_status=consistency_status,
        state_confidence=state_confidence,
    )


def test_trading_readiness_requires_all_checks_and_zero_gaps() -> None:
    report = _passing_report()
    assert report.state is TradingReadinessState.TRADING_READY
    assert report.trading_ready is True


def test_any_reconciliation_gap_blocks_trading_ready() -> None:
    report = TradingReadinessReport(
        provider="alpaca",
        environment="PAPER",
        account="********1234",
        checks=(ReadinessCheck("startup", ReadinessCheckStatus.PASS, "ok"),),
        gaps=("position mismatch",),
    )
    assert report.state is TradingReadinessState.NOT_READY


def test_consistency_evidence_allows_ready_only_for_consistent_high() -> None:
    ready = _passing_report(
        consistency_status=ConsistencyStatus.CONSISTENT,
        state_confidence=StateConfidence.HIGH,
    )
    blocked = _passing_report(
        consistency_status=ConsistencyStatus.CONSISTENT,
        state_confidence=StateConfidence.MEDIUM,
    )

    assert ready.state is TradingReadinessState.TRADING_READY
    assert blocked.state is TradingReadinessState.NOT_READY
