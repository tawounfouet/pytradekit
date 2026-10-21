"""Unit tests for correlation and causation identifiers."""

from typing import cast
from uuid import UUID

from pytradekit.shared import CausationId, CorrelationId


def test_correlation_id_round_trip() -> None:
    identifier = CorrelationId.from_string(
        "8fb1062e-16ec-45ae-9c99-b06874085c0f"
    )

    assert isinstance(identifier.value, UUID)
    assert CorrelationId.from_string(str(identifier)) == identifier


def test_causation_id_round_trip() -> None:
    identifier = CausationId.from_string(
        "2e1f702f-9464-439c-ac08-9f52d20e0524"
    )

    assert isinstance(identifier.value, UUID)
    assert CausationId.from_string(str(identifier)) == identifier


def test_correlation_and_causation_ids_are_distinct_types() -> None:
    value = UUID("8fb1062e-16ec-45ae-9c99-b06874085c0f")

    correlation_id = CorrelationId(value)
    causation_id = CausationId(value)

    assert correlation_id != cast(object, causation_id)
