"""Property tests for typed UUID identifiers."""

from uuid import UUID

from hypothesis import given
from hypothesis import strategies as st

from pytradekit.shared import (
    CausationId,
    CorrelationId,
    EventId,
    InstrumentId,
)


@given(st.uuids())
def test_instrument_id_string_round_trip(value: UUID) -> None:
    identifier = InstrumentId(value)

    assert InstrumentId.from_string(str(identifier)) == identifier


@given(st.uuids())
def test_event_id_string_round_trip(value: UUID) -> None:
    identifier = EventId(value)

    assert EventId.from_string(str(identifier)) == identifier


@given(st.uuids())
def test_correlation_id_string_round_trip(value: UUID) -> None:
    identifier = CorrelationId(value)

    assert CorrelationId.from_string(str(identifier)) == identifier


@given(st.uuids())
def test_causation_id_string_round_trip(value: UUID) -> None:
    identifier = CausationId(value)

    assert CausationId.from_string(str(identifier)) == identifier
