"""Property qualification for alert deduplication."""

from datetime import UTC, datetime

from hypothesis import given
from hypothesis import strategies as st

from pytradekit.operations import AlertSeverity, AlertType
from pytradekit.operations.adapters import DefaultAlertRouter, InMemoryAlertRepository
from pytradekit.operations.application import RaiseAlert
from pytradekit.testing import FakeClock

NOW = datetime(2026, 10, 22, 21, 10, tzinfo=UTC)


@given(repeats=st.integers(min_value=1, max_value=50))
def test_repeated_condition_has_one_open_alert(repeats: int) -> None:
    repository = InMemoryAlertRepository()
    raise_alert = RaiseAlert(
        repository=repository,
        router=DefaultAlertRouter(()),
        clock=FakeClock.at(NOW),
    )

    for _ in range(repeats):
        raise_alert.execute(
            alert_type=AlertType.DATABASE_UNAVAILABLE,
            severity=AlertSeverity.CRITICAL,
            title="Database unavailable",
            reason="database probe failed",
            deduplication_key="health:DATABASE",
        )

    assert len(repository.list_open()) == 1
