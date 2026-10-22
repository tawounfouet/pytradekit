"""Unit tests for generic startup readiness aggregation."""

from pytradekit.runtime import (
    ReadinessCheck,
    ReadinessCheckStatus,
    StartupReadinessReport,
    StartupReadinessState,
)


def test_readiness_report_requires_every_check_to_pass() -> None:
    report = StartupReadinessReport(
        provider="alpaca",
        environment="PAPER",
        account="***1234",
        checks=(
            ReadinessCheck("one", ReadinessCheckStatus.PASS, "ok"),
            ReadinessCheck("two", ReadinessCheckStatus.FAIL, "not ok"),
        ),
    )

    assert report.state is StartupReadinessState.NOT_READY
    assert report.ready_for_startup is False
    assert report.to_dict()["trading_ready"] is False


def test_readiness_report_can_be_ready_for_startup_without_claiming_trading_ready() -> None:
    report = StartupReadinessReport(
        provider="alpaca",
        environment="PAPER",
        account="***1234",
        checks=(ReadinessCheck("one", ReadinessCheckStatus.PASS, "ok"),),
    )

    assert report.state is StartupReadinessState.READY_FOR_STARTUP
    assert report.ready_for_startup is True
    assert report.to_dict()["trading_ready"] is False
