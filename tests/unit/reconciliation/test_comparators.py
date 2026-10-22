"""LOT-02 deterministic reconciliation comparators."""

from datetime import UTC, datetime
from decimal import Decimal

from pytradekit.orders.domain import OrderId
from pytradekit.portfolio.domain import AccountId
from pytradekit.reconciliation import (
    BrokerSnapshot,
    CanonicalBalance,
    CanonicalFill,
    CanonicalOrder,
    CanonicalPosition,
    InternalSnapshot,
    MismatchType,
    ReconciliationRunId,
    ReconciliationScope,
    SnapshotCompleteness,
    SnapshotWatermark,
)
from pytradekit.reconciliation.services import ConvergenceService, SnapshotComparator
from pytradekit.shared import Currency, InstrumentId


def _snapshots() -> tuple[InternalSnapshot, BrokerSnapshot]:
    now = datetime(2026, 10, 22, 12, tzinfo=UTC)
    account_id = AccountId.new()
    order_id = OrderId.new()
    instrument_id = InstrumentId.new()
    watermark = SnapshotWatermark(captured_at=now)
    order = CanonicalOrder(
        order_id=order_id,
        client_order_id="client-1",
        external_order_id="remote-1",
        status="accepted",
        filled_quantity=Decimal("0"),
    )
    fill = CanonicalFill(
        external_fill_id="fill-1",
        order_id=order_id,
        external_order_id="remote-1",
        quantity=Decimal("1"),
        price=Decimal("10"),
        currency=Currency("USD"),
        occurred_at=now,
    )
    position = CanonicalPosition(
        instrument_id=instrument_id,
        quantity=Decimal("1"),
        average_price=Decimal("10"),
        currency=Currency("USD"),
    )
    balance = CanonicalBalance(currency=Currency("USD"), cash=Decimal("990"))
    internal = InternalSnapshot(
        account_id=account_id,
        orders=(order,),
        fills=(fill,),
        positions=(position,),
        balances=(balance,),
        captured_at=now,
        watermark=watermark,
        completeness=SnapshotCompleteness.COMPLETE,
    )
    broker = BrokerSnapshot(
        account_id=account_id,
        provider="alpaca",
        orders=(order,),
        fills=(fill,),
        positions=(position,),
        balances=(balance,),
        captured_at=now,
        watermark=watermark,
        completeness=SnapshotCompleteness.COMPLETE,
    )
    return internal, broker


def test_equal_complete_snapshots_are_consistent_high() -> None:
    internal, broker = _snapshots()
    run_id = ReconciliationRunId.new()
    mismatches = SnapshotComparator().compare(
        run_id=run_id,
        scope=ReconciliationScope.FULL,
        internal=internal,
        broker=broker,
        detected_at=broker.captured_at,
    )
    convergence = ConvergenceService().evaluate(
        internal_completeness=internal.completeness,
        broker_completeness=broker.completeness,
        mismatches=mismatches,
    )

    assert mismatches == ()
    assert convergence.status.value == "CONSISTENT"
    assert convergence.confidence.value == "HIGH"
    assert not convergence.blocking


def test_missing_internal_fill_is_critical_and_deterministic() -> None:
    internal, broker = _snapshots()
    internal = InternalSnapshot(
        account_id=internal.account_id,
        orders=internal.orders,
        fills=(),
        positions=internal.positions,
        balances=internal.balances,
        captured_at=internal.captured_at,
        watermark=internal.watermark,
        completeness=internal.completeness,
    )
    comparator = SnapshotComparator()
    run_id = ReconciliationRunId.new()

    first = comparator.compare(
        run_id=run_id,
        scope=ReconciliationScope.FULL,
        internal=internal,
        broker=broker,
        detected_at=broker.captured_at,
    )
    second = comparator.compare(
        run_id=run_id,
        scope=ReconciliationScope.FULL,
        internal=internal,
        broker=broker,
        detected_at=broker.captured_at,
    )

    assert first == second
    assert any(item.type is MismatchType.MISSING_INTERNAL_FILL for item in first)


def test_partial_snapshot_never_produces_high_confidence() -> None:
    internal, broker = _snapshots()
    result = ConvergenceService().evaluate(
        internal_completeness=SnapshotCompleteness.COMPLETE,
        broker_completeness=SnapshotCompleteness.PARTIAL,
        mismatches=(),
    )

    assert result.confidence.value != "HIGH"
    assert result.blocking
