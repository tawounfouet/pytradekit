"""Unit tests for DomainEvent."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone
from typing import cast

import pytest

from pytradekit.shared import (
    CausationId,
    CorrelationId,
    DomainEvent,
    EventId,
)
from pytradekit.shared.errors import DomainValidationError


def make_event(**overrides: object) -> DomainEvent:
    values: dict[str, object] = {
        "event_id": EventId.new(),
        "occurred_at": datetime(2026, 10, 21, 19, 0, tzinfo=UTC),
        "correlation_id": CorrelationId.new(),
        "causation_id": None,
        "event_version": 1,
    }
    values.update(overrides)
    return DomainEvent(
        event_id=cast(EventId, values["event_id"]),
        occurred_at=cast(datetime, values["occurred_at"]),
        correlation_id=cast(CorrelationId, values["correlation_id"]),
        causation_id=cast(CausationId | None, values["causation_id"]),
        event_version=cast(int, values["event_version"]),
    )


def test_domain_event_accepts_valid_envelope() -> None:
    event = make_event()

    assert isinstance(event.event_id, EventId)
    assert isinstance(event.correlation_id, CorrelationId)
    assert event.causation_id is None
    assert event.event_version == 1


def test_domain_event_accepts_optional_causation_id() -> None:
    causation_id = CausationId.new()

    event = make_event(causation_id=causation_id)

    assert event.causation_id == causation_id


def test_domain_event_rejects_naive_timestamp() -> None:
    with pytest.raises(DomainValidationError, match="timezone-aware"):
        make_event(occurred_at=datetime(2026, 10, 21, 19, 0))


def test_domain_event_rejects_non_utc_timestamp() -> None:
    non_utc = datetime(
        2026,
        10,
        21,
        21,
        0,
        tzinfo=timezone(timedelta(hours=2)),
    )

    with pytest.raises(DomainValidationError, match="must use UTC"):
        make_event(occurred_at=non_utc)


@pytest.mark.parametrize("version", [0, -1, True])
def test_domain_event_rejects_invalid_version(version: int) -> None:
    with pytest.raises(DomainValidationError, match="event_version"):
        make_event(event_version=version)


def test_domain_event_is_immutable() -> None:
    event = make_event()

    with pytest.raises(FrozenInstanceError):
        event.__setattr__("event_version", 2)
