"""Property tests for DomainEvent."""

from datetime import UTC, datetime

from hypothesis import given
from hypothesis import strategies as st

from pytradekit.shared import CorrelationId, DomainEvent, EventId


UTC_DATETIMES = st.datetimes(
    min_value=datetime(2000, 1, 1),
    max_value=datetime(2100, 1, 1),
    timezones=st.just(UTC),
)


@given(UTC_DATETIMES, st.integers(min_value=1, max_value=1000))
def test_domain_event_preserves_valid_utc_timestamp_and_version(
    occurred_at: datetime,
    version: int,
) -> None:
    event = DomainEvent(
        event_id=EventId.new(),
        occurred_at=occurred_at,
        correlation_id=CorrelationId.new(),
        event_version=version,
    )

    assert event.occurred_at == occurred_at
    assert event.event_version == version
    assert event.occurred_at.utcoffset() is not None
