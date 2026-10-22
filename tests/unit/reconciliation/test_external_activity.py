"""LOT-05 external activity and missing fill recovery semantics."""

from datetime import UTC, datetime
from decimal import Decimal

from pytradekit.orders.domain import OrderId
from pytradekit.reconciliation import (
    CanonicalFill,
    CanonicalOrder,
    ExternalActivityOrigin,
)
from pytradekit.reconciliation.application import ExternalActivityClassifier
from pytradekit.shared import Currency


def test_unknown_external_order_is_not_silently_internalized() -> None:
    classification = ExternalActivityClassifier().classify_order(
        CanonicalOrder(
            order_id=None,
            client_order_id="manual-client",
            external_order_id="broker-order",
            status="accepted",
            filled_quantity=Decimal("0"),
        )
    )

    assert classification.origin is ExternalActivityOrigin.UNKNOWN_EXTERNAL


def test_fill_linked_to_canonical_order_is_internal() -> None:
    classification = ExternalActivityClassifier().classify_fill(
        CanonicalFill(
            external_fill_id="fill-1",
            order_id=OrderId.new(),
            external_order_id="order-1",
            quantity=Decimal("1"),
            price=Decimal("10"),
            currency=Currency("USD"),
            occurred_at=datetime(2026, 10, 22, 12, tzinfo=UTC),
        )
    )

    assert classification.origin is ExternalActivityOrigin.INTERNAL
