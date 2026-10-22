"""Property qualification for freshness-aware health."""

from datetime import UTC, datetime, timedelta

from hypothesis import given
from hypothesis import strategies as st

from pytradekit.operations import (
    HealthComponent,
    HealthFreshnessPolicy,
    HealthRegistry,
    HealthReport,
    HealthStatus,
)

NOW = datetime(2026, 10, 22, 21, 0, tzinfo=UTC)


@given(ttl_seconds=st.integers(min_value=1, max_value=3600))
def test_stale_healthy_value_cannot_remain_healthy_forever(
    ttl_seconds: int,
) -> None:
    registry = HealthRegistry(
        freshness=HealthFreshnessPolicy(
            default_ttl=timedelta(seconds=ttl_seconds)
        )
    )
    registry.update(
        HealthReport(
            component=HealthComponent.DATABASE,
            status=HealthStatus.HEALTHY,
            observed_at=NOW,
            message="healthy",
            last_success_at=NOW,
        )
    )

    expired = registry.get(
        HealthComponent.DATABASE,
        at=NOW + timedelta(seconds=ttl_seconds),
    )

    assert expired is not None
    assert expired.status is HealthStatus.UNKNOWN
