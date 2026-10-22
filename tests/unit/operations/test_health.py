"""Unit qualification for operational health and readiness."""

from datetime import UTC, datetime, timedelta

from pytradekit.operations import (
    HealthComponent,
    HealthFreshnessPolicy,
    HealthRegistry,
    HealthReport,
    HealthStatus,
    LivenessService,
    LivenessStatus,
    OperationalReadinessService,
)
from pytradekit.reconciliation.domain import ConsistencyStatus, StateConfidence
from pytradekit.runtime import (
    ReadinessCheck,
    ReadinessCheckStatus,
    TradingReadinessReport,
)
from pytradekit.runtime.operations import RuntimeLifecycleState

NOW = datetime(2026, 10, 22, 21, 0, tzinfo=UTC)


def _trading(*, ready: bool = True) -> TradingReadinessReport:
    return TradingReadinessReport(
        provider="alpaca",
        environment="PAPER",
        account="********1234",
        checks=(
            ReadinessCheck(
                "runtime",
                ReadinessCheckStatus.PASS if ready else ReadinessCheckStatus.FAIL,
                "qualified",
            ),
        ),
        gaps=() if ready else ("blocked",),
        consistency_status=ConsistencyStatus.CONSISTENT,
        state_confidence=StateConfidence.HIGH,
    )


def _healthy(
    component: HealthComponent,
    *,
    observed_at: datetime = NOW,
) -> HealthReport:
    return HealthReport(
        component=component,
        status=HealthStatus.HEALTHY,
        observed_at=observed_at,
        message="healthy",
        last_success_at=observed_at,
    )


def _critical_registry() -> HealthRegistry:
    registry = HealthRegistry()
    for component in (
        HealthComponent.DATABASE,
        HealthComponent.BROKER_COMMAND,
        HealthComponent.RUNTIME,
    ):
        registry.update(_healthy(component))
    return registry


def test_stale_healthy_evidence_becomes_unknown() -> None:
    registry = HealthRegistry(
        freshness=HealthFreshnessPolicy(default_ttl=timedelta(seconds=10))
    )
    registry.update(_healthy(HealthComponent.DATABASE))

    fresh = registry.get(HealthComponent.DATABASE, at=NOW + timedelta(seconds=9))
    stale = registry.get(HealthComponent.DATABASE, at=NOW + timedelta(seconds=10))

    assert fresh is not None
    assert fresh.status is HealthStatus.HEALTHY
    assert stale is not None
    assert stale.status is HealthStatus.UNKNOWN
    assert stale.details["stale"] is True


def test_liveness_does_not_depend_on_external_dependency_health() -> None:
    service = LivenessService()

    assert (
        service.evaluate(RuntimeLifecycleState.DEGRADED)
        is LivenessStatus.PROCESS_LIVE
    )
    assert (
        service.evaluate(RuntimeLifecycleState.STOPPED)
        is LivenessStatus.NOT_LIVE
    )


def test_operational_ready_and_trading_ready_are_independent_signals() -> None:
    registry = _critical_registry()
    service = OperationalReadinessService()

    report = service.evaluate(
        lifecycle=RuntimeLifecycleState.READY,
        health=registry,
        trading=_trading(ready=False),
        observed_at=NOW,
    )

    assert report.operational_ready is True
    assert report.trading_ready is False
    assert report.liveness is LivenessStatus.PROCESS_LIVE


def test_critical_database_failure_removes_operational_readiness() -> None:
    registry = _critical_registry()
    registry.update(
        HealthReport(
            component=HealthComponent.DATABASE,
            status=HealthStatus.UNHEALTHY,
            observed_at=NOW,
            message="database unavailable",
        )
    )

    report = OperationalReadinessService().evaluate(
        lifecycle=RuntimeLifecycleState.READY,
        health=registry,
        trading=_trading(),
        observed_at=NOW,
    )

    assert report.operational_ready is False
    assert report.trading_ready is True
    assert "DATABASE_UNHEALTHY" in report.reasons


def test_missing_critical_health_fails_operational_readiness_closed() -> None:
    registry = HealthRegistry()
    registry.update(_healthy(HealthComponent.RUNTIME))

    report = OperationalReadinessService().evaluate(
        lifecycle=RuntimeLifecycleState.READY,
        health=registry,
        trading=_trading(),
        observed_at=NOW,
    )

    assert not report.operational_ready
    assert "MISSING_HEALTH_DATABASE" in report.reasons
    assert "MISSING_HEALTH_BROKER_COMMAND" in report.reasons
