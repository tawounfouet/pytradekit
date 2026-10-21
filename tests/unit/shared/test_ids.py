"""Unit tests for typed UUID identifiers."""

from dataclasses import FrozenInstanceError
from typing import cast
from uuid import UUID

import pytest

from pytradekit.shared import EventId, InstrumentId
from pytradekit.shared.errors import DomainValidationError


def test_instrument_id_new_returns_valid_uuid() -> None:
    identifier = InstrumentId.new()

    assert isinstance(identifier.value, UUID)
    assert UUID(str(identifier)) == identifier.value


def test_event_id_new_returns_valid_uuid() -> None:
    identifier = EventId.new()

    assert isinstance(identifier.value, UUID)
    assert UUID(str(identifier)) == identifier.value


@pytest.mark.parametrize("identifier_type", [InstrumentId, EventId])
def test_typed_id_from_string_round_trip(
    identifier_type: type[InstrumentId] | type[EventId],
) -> None:
    value = "7e4b0a83-9f6a-4a2a-8781-4fc6c5308b16"

    identifier = identifier_type.from_string(value)

    assert str(identifier) == value
    assert identifier_type.from_string(str(identifier)) == identifier


@pytest.mark.parametrize("identifier_type", [InstrumentId, EventId])
@pytest.mark.parametrize("value", ["", " ", "not-a-uuid", "1234"])
def test_typed_id_rejects_invalid_uuid_string(
    identifier_type: type[InstrumentId] | type[EventId],
    value: str,
) -> None:
    with pytest.raises(DomainValidationError):
        identifier_type.from_string(value)


def test_typed_ids_with_same_uuid_but_different_types_are_not_equal() -> None:
    value = UUID("7e4b0a83-9f6a-4a2a-8781-4fc6c5308b16")

    instrument_id = InstrumentId(value)
    event_id = EventId(value)

    assert instrument_id != cast(object, event_id)


def test_typed_id_is_immutable() -> None:
    identifier = InstrumentId.new()

    with pytest.raises(FrozenInstanceError):
        identifier.__setattr__(
            "value",
            UUID("00000000-0000-0000-0000-000000000001"),
        )


def test_typed_id_is_hashable() -> None:
    value = UUID("7e4b0a83-9f6a-4a2a-8781-4fc6c5308b16")

    left = InstrumentId(value)
    right = InstrumentId(value)

    assert hash(left) == hash(right)
    assert {left, right} == {left}
