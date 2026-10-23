"""LOT-05.4 qualification for IBKR callback and status normalization."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from pytradekit.brokers import (
    ProviderExecutionContext,
    ProviderStateReconciliationRequired,
)
from pytradekit.brokers.adapters.ibkr import (
    IBKRClientId,
    IBKROrderErrorObservation,
    IBKROrderIdentityRegistry,
    IBKROrderStatus,
    IBKROrderStatusObservation,
    IBKRPermanentOrderId,
    IBKRSessionOrderId,
    map_ibkr_order_error_report,
    map_ibkr_order_status_report,
)
from pytradekit.execution import ExecutionStatus
from pytradekit.orders.domain import OrderId
from pytradekit.shared import CorrelationId, Currency

_NOW = datetime(2026, 10, 23, 3, 45, tzinfo=UTC)


def _context() -> ProviderExecutionContext:
    return ProviderExecutionContext(
        order_id=OrderId.new(),
        correlation_id=CorrelationId.new(),
        client_order_reference="ptk-lot05-4",
        quote_currency=Currency("USD"),
    )


def _status(
    status: str,
    *,
    filled: str = "0",
    remaining: str = "5",
) -> IBKROrderStatusObservation:
    return IBKROrderStatusObservation(
        client_id=IBKRClientId(3),
        session_order_id=IBKRSessionOrderId(101),
        permanent_order_id=IBKRPermanentOrderId(900101),
        provider_status=status,
        filled=Decimal(filled),
        remaining=Decimal(remaining),
        average_fill_price=(
            Decimal("250.10") if Decimal(filled) > 0 else None
        ),
        last_fill_price=(
            Decimal("250.10") if Decimal(filled) > 0 else None
        ),
        why_held=None,
        observed_at=_NOW,
    )


def test_lot05_4_maps_only_complete_non_fill_status_facts() -> None:
    registry = IBKROrderIdentityRegistry()
    context = _context()

    accepted = map_ibkr_order_status_report(
        _status(IBKROrderStatus.SUBMITTED.value),
        context=context,
        registry=registry,
    )
    cancelled = map_ibkr_order_status_report(
        _status(IBKROrderStatus.CANCELLED.value),
        context=context,
        registry=registry,
    )

    assert accepted is not None
    assert accepted.status is ExecutionStatus.ACCEPTED
    assert cancelled is not None
    assert cancelled.status is ExecutionStatus.CANCELLED


def test_lot05_4_requires_exec_details_for_cumulative_fill_state() -> None:
    registry = IBKROrderIdentityRegistry()
    context = _context()

    with pytest.raises(ProviderStateReconciliationRequired, match="execDetails"):
        map_ibkr_order_status_report(
            _status(
                IBKROrderStatus.FILLED.value,
                filled="5",
                remaining="0",
            ),
            context=context,
            registry=registry,
        )


def test_lot05_4_uses_explicit_error_201_for_rejection() -> None:
    registry = IBKROrderIdentityRegistry()
    context = _context()

    rejected = map_ibkr_order_error_report(
        IBKROrderErrorObservation(
            client_id=IBKRClientId(3),
            session_order_id=IBKRSessionOrderId(101),
            error_code=201,
            message="provider details are not canonicalized",
            advanced_order_reject_json=None,
            observed_at=_NOW,
        ),
        context=context,
        registry=registry,
    )

    assert rejected is not None
    assert rejected.status is ExecutionStatus.REJECTED
    assert rejected.rejection_reason == "IBKR reported order rejection (error 201)."
