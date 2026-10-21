"""Unit tests for canonical execution facts."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from pytradekit.execution import (
    ExecutionReport,
    ExecutionStatus,
    Fill,
    FillId,
    SubmissionResult,
    SubmissionStatus,
)
from pytradekit.orders import OrderId
from pytradekit.shared import CorrelationId, Currency, DomainValidationError, Price, Quantity

NOW = datetime(2026, 10, 21, 20, 0, tzinfo=UTC)
USD = Currency("USD")


def test_fill_requires_positive_quantity() -> None:
    with pytest.raises(DomainValidationError):
        Fill(
            id=FillId.new(),
            order_id=OrderId.new(),
            quantity=Quantity(Decimal("0")),
            price=Price(Decimal("100"), USD),
            occurred_at=NOW,
        )


def test_external_fill_id_is_deduplication_key() -> None:
    fill = Fill(
        id=FillId.new(),
        order_id=OrderId.new(),
        quantity=Quantity(Decimal("1")),
        price=Price(Decimal("100"), USD),
        occurred_at=NOW,
        external_fill_id="provider-fill-1",
    )

    assert fill.deduplication_key == "provider-fill-1"


def test_fill_report_requires_fill_payload() -> None:
    with pytest.raises(DomainValidationError):
        ExecutionReport(
            order_id=OrderId.new(),
            status=ExecutionStatus.FILLED,
            occurred_at=NOW,
            correlation_id=CorrelationId.new(),
        )


def test_acknowledged_submission_requires_external_order_id() -> None:
    with pytest.raises(DomainValidationError):
        SubmissionResult(status=SubmissionStatus.ACKNOWLEDGED)
