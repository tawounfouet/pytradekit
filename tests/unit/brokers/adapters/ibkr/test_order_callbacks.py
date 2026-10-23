"""Unit tests for IBKR order callback normalization."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from pytradekit.brokers import (
    ProviderExecutionContext,
    ProviderProtocolError,
    ProviderStateReconciliationRequired,
)
from pytradekit.brokers.adapters.ibkr import (
    IBKRClientId,
    IBKROpenOrderObservation,
    IBKROrderErrorObservation,
    IBKROrderIdentityRegistry,
    IBKROrderReference,
    IBKROrderStateDisposition,
    IBKROrderStatus,
    IBKROrderStatusObservation,
    IBKRPermanentOrderId,
    IBKRSessionOrderId,
    ibkr_order_status_rule,
    map_ibkr_order_error_report,
    map_ibkr_order_status_report,
    map_ibkr_order_status_snapshot,
    register_ibkr_open_order_observation,
)
from pytradekit.execution import ExecutionStatus
from pytradekit.orders.domain import OrderId
from pytradekit.shared import CorrelationId, Currency

_NOW = datetime(2026, 10, 23, 3, 30, tzinfo=UTC)


def _context(reference: str = "ptk-callback-1") -> ProviderExecutionContext:
    return ProviderExecutionContext(
        order_id=OrderId.new(),
        correlation_id=CorrelationId.new(),
        client_order_reference=reference,
        quote_currency=Currency("USD"),
    )


def _status(
    provider_status: str,
    *,
    perm_id: int | None = 700,
    filled: str = "0",
    remaining: str = "10",
) -> IBKROrderStatusObservation:
    return IBKROrderStatusObservation(
        client_id=IBKRClientId(1),
        session_order_id=IBKRSessionOrderId(10),
        permanent_order_id=(
            IBKRPermanentOrderId(perm_id) if perm_id is not None else None
        ),
        provider_status=provider_status,
        filled=Decimal(filled),
        remaining=Decimal(remaining),
        average_fill_price=(
            Decimal("100.25") if Decimal(filled) > 0 else None
        ),
        last_fill_price=(
            Decimal("100.25") if Decimal(filled) > 0 else None
        ),
        why_held=None,
        observed_at=_NOW,
    )


def test_open_order_registers_order_ref_route_and_perm_id() -> None:
    registry = IBKROrderIdentityRegistry()
    observation = IBKROpenOrderObservation(
        client_id=IBKRClientId(1),
        session_order_id=IBKRSessionOrderId(10),
        order_reference=IBKROrderReference("ptk-callback-1"),
        permanent_order_id=IBKRPermanentOrderId(700),
        provider_status=IBKROrderStatus.SUBMITTED.value,
        reject_reason=None,
        observed_at=_NOW,
    )

    identity = register_ibkr_open_order_observation(
        observation,
        registry=registry,
    )

    assert identity.routing_key == (1, 10)
    assert identity.client_reference.value == "ptk-callback-1"
    assert identity.permanent_order_id == IBKRPermanentOrderId(700)


def test_submitted_maps_to_accepted_only_after_stable_identity() -> None:
    registry = IBKROrderIdentityRegistry()
    context = _context()

    report = map_ibkr_order_status_report(
        _status(IBKROrderStatus.SUBMITTED.value),
        context=context,
        registry=registry,
    )

    assert report is not None
    assert report.status is ExecutionStatus.ACCEPTED
    assert report.external_order_id == "700"


def test_pending_submit_is_transient_not_accepted() -> None:
    registry = IBKROrderIdentityRegistry()
    context = _context()

    report = map_ibkr_order_status_report(
        _status(IBKROrderStatus.PENDING_SUBMIT.value),
        context=context,
        registry=registry,
    )

    assert report is None
    rule = ibkr_order_status_rule(IBKROrderStatus.PENDING_SUBMIT.value)
    assert rule.disposition is IBKROrderStateDisposition.TRANSIENT


def test_pending_cancel_is_not_terminal_cancelled() -> None:
    registry = IBKROrderIdentityRegistry()
    context = _context()

    report = map_ibkr_order_status_report(
        _status(IBKROrderStatus.PENDING_CANCEL.value),
        context=context,
        registry=registry,
    )

    assert report is None


@pytest.mark.parametrize(
    "provider_status",
    [
        IBKROrderStatus.API_CANCELLED.value,
        IBKROrderStatus.CANCELLED.value,
    ],
)
def test_cancelled_states_map_to_terminal_cancelled(provider_status: str) -> None:
    registry = IBKROrderIdentityRegistry()
    context = _context()

    report = map_ibkr_order_status_report(
        _status(provider_status),
        context=context,
        registry=registry,
    )

    assert report is not None
    assert report.status is ExecutionStatus.CANCELLED
    assert report.external_order_id == "700"


def test_filled_status_is_snapshot_only_until_exec_details_exists() -> None:
    registry = IBKROrderIdentityRegistry()
    context = _context()
    observation = _status(
        IBKROrderStatus.FILLED.value,
        filled="10",
        remaining="0",
    )

    snapshot = map_ibkr_order_status_snapshot(
        observation,
        context=context,
        registry=registry,
    )

    assert snapshot.canonical_status is ExecutionStatus.FILLED
    assert snapshot.filled_quantity == Decimal("10")

    with pytest.raises(
        ProviderStateReconciliationRequired,
        match="execDetails",
    ):
        map_ibkr_order_status_report(
            observation,
            context=context,
            registry=registry,
        )


def test_cumulative_partial_fill_does_not_create_synthetic_fill() -> None:
    registry = IBKROrderIdentityRegistry()
    context = _context()
    observation = _status(
        IBKROrderStatus.SUBMITTED.value,
        filled="4",
        remaining="6",
    )

    snapshot = map_ibkr_order_status_snapshot(
        observation,
        context=context,
        registry=registry,
    )

    assert snapshot.canonical_status is ExecutionStatus.PARTIALLY_FILLED
    assert snapshot.filled_quantity == Decimal("4")

    with pytest.raises(
        ProviderStateReconciliationRequired,
        match="execDetails",
    ):
        map_ibkr_order_status_report(
            observation,
            context=context,
            registry=registry,
        )


def test_inactive_never_becomes_rejected_without_explicit_rejection_fact() -> None:
    registry = IBKROrderIdentityRegistry()
    context = _context()
    register_ibkr_open_order_observation(
        IBKROpenOrderObservation(
            client_id=IBKRClientId(1),
            session_order_id=IBKRSessionOrderId(10),
            order_reference=IBKROrderReference("ptk-callback-1"),
            permanent_order_id=IBKRPermanentOrderId(700),
            provider_status=IBKROrderStatus.INACTIVE.value,
            reject_reason="provider supplied explanatory text",
            observed_at=_NOW,
        ),
        registry=registry,
    )

    snapshot = map_ibkr_order_status_snapshot(
        _status(IBKROrderStatus.INACTIVE.value),
        context=context,
        registry=registry,
    )

    assert snapshot.canonical_status is None
    with pytest.raises(
        ProviderStateReconciliationRequired,
        match="Inactive",
    ):
        map_ibkr_order_status_report(
            _status(IBKROrderStatus.INACTIVE.value),
            context=context,
            registry=registry,
        )


def test_error_201_is_explicit_rejection_without_raw_message_leak() -> None:
    registry = IBKROrderIdentityRegistry()
    context = _context()

    report = map_ibkr_order_error_report(
        IBKROrderErrorObservation(
            client_id=IBKRClientId(1),
            session_order_id=IBKRSessionOrderId(10),
            error_code=201,
            message="sensitive provider rejection details",
            advanced_order_reject_json='{"secret":"must not leak"}',
            observed_at=_NOW,
        ),
        context=context,
        registry=registry,
    )

    assert report is not None
    assert report.status is ExecutionStatus.REJECTED
    assert report.rejection_reason == "IBKR reported order rejection (error 201)."
    assert "sensitive" not in report.rejection_reason
    assert "secret" not in report.rejection_reason


def test_error_202_is_explicit_cancelled_fact() -> None:
    registry = IBKROrderIdentityRegistry()
    context = _context()

    report = map_ibkr_order_error_report(
        IBKROrderErrorObservation(
            client_id=IBKRClientId(1),
            session_order_id=IBKRSessionOrderId(10),
            error_code=202,
            message="Order cancelled - Reason",
            advanced_order_reject_json=None,
            observed_at=_NOW,
        ),
        context=context,
        registry=registry,
    )

    assert report is not None
    assert report.status is ExecutionStatus.CANCELLED


def test_other_order_error_is_not_guessed_into_terminal_state() -> None:
    registry = IBKROrderIdentityRegistry()
    context = _context()

    report = map_ibkr_order_error_report(
        IBKROrderErrorObservation(
            client_id=IBKRClientId(1),
            session_order_id=IBKRSessionOrderId(10),
            error_code=133,
            message="Submit new order failed.",
            advanced_order_reject_json=None,
            observed_at=_NOW,
        ),
        context=context,
        registry=registry,
    )

    assert report is None


def test_unknown_provider_status_is_reconciliation_required() -> None:
    registry = IBKROrderIdentityRegistry()
    context = _context()
    observation = _status("FutureStatus")

    snapshot = map_ibkr_order_status_snapshot(
        observation,
        context=context,
        registry=registry,
    )

    assert snapshot.canonical_status is None
    assert (
        ibkr_order_status_rule("FutureStatus").disposition
        is IBKROrderStateDisposition.RECONCILE
    )

    with pytest.raises(ProviderStateReconciliationRequired):
        map_ibkr_order_status_report(
            observation,
            context=context,
            registry=registry,
        )


def test_status_before_open_order_can_register_from_canonical_context() -> None:
    registry = IBKROrderIdentityRegistry()
    context = _context()

    snapshot = map_ibkr_order_status_snapshot(
        _status(IBKROrderStatus.SUBMITTED.value),
        context=context,
        registry=registry,
    )
    identity = registry.find_by_routing_key(
        client_id=IBKRClientId(1),
        session_order_id=IBKRSessionOrderId(10),
    )

    assert snapshot.identity.client_reference == "ptk-callback-1"
    assert identity is not None
    assert identity.permanent_order_id == IBKRPermanentOrderId(700)


def test_open_order_conflicting_order_ref_is_protocol_error() -> None:
    registry = IBKROrderIdentityRegistry()
    context = _context()
    map_ibkr_order_status_snapshot(
        _status(IBKROrderStatus.SUBMITTED.value),
        context=context,
        registry=registry,
    )

    with pytest.raises(ProviderProtocolError, match="conflicts"):
        register_ibkr_open_order_observation(
            IBKROpenOrderObservation(
                client_id=IBKRClientId(1),
                session_order_id=IBKRSessionOrderId(10),
                order_reference=IBKROrderReference("different-reference"),
                permanent_order_id=IBKRPermanentOrderId(700),
                provider_status=IBKROrderStatus.SUBMITTED.value,
                reject_reason=None,
                observed_at=_NOW,
            ),
            registry=registry,
        )


def test_snapshot_requires_non_zero_perm_id() -> None:
    registry = IBKROrderIdentityRegistry()
    context = _context()

    with pytest.raises(ProviderStateReconciliationRequired, match="permId"):
        map_ibkr_order_status_snapshot(
            _status(
                IBKROrderStatus.SUBMITTED.value,
                perm_id=None,
            ),
            context=context,
            registry=registry,
        )
