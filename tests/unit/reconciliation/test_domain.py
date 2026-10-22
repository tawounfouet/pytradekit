"""LOT-01 reconciliation domain foundations."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from pytradekit.portfolio.domain import AccountId
from pytradekit.reconciliation import (
    BrokerSnapshot,
    CanonicalBalance,
    CanonicalOrder,
    ConsistencyStatus,
    ReconciliationRun,
    ReconciliationRunStatus,
    ReconciliationScope,
    ReconciliationTrigger,
    SnapshotCompleteness,
    SnapshotWatermark,
    StateConfidence,
)
from pytradekit.shared import CorrelationId, Currency, DomainValidationError


def test_reconciliation_run_completed_does_not_imply_consistent() -> None:
    now = datetime(2026, 10, 22, 12, tzinfo=UTC)
    run = ReconciliationRun.create(
        account_id=AccountId.new(),
        scope=ReconciliationScope.FULL,
        trigger=ReconciliationTrigger.STARTUP,
        started_at=now,
        correlation_id=CorrelationId.new(),
    )

    run.transition_to(ReconciliationRunStatus.CAPTURING)
    run.transition_to(ReconciliationRunStatus.COMPARING)
    run.complete(
        completed_at=now,
        result_status=ConsistencyStatus.INCONSISTENT,
        confidence=StateConfidence.LOW,
        mismatch_count=1,
        critical_mismatch_count=1,
    )

    assert run.status is ReconciliationRunStatus.COMPLETED
    assert run.result_status is ConsistencyStatus.INCONSISTENT


def test_broker_snapshot_contains_only_canonical_facts() -> None:
    now = datetime(2026, 10, 22, 12, tzinfo=UTC)
    account_id = AccountId.new()
    watermark = SnapshotWatermark(captured_at=now, provider_as_of=now)
    order = CanonicalOrder(
        order_id=None,
        client_order_id="client-1",
        external_order_id="provider-1",
        status="accepted",
        filled_quantity=Decimal("0"),
    )
    snapshot = BrokerSnapshot(
        account_id=account_id,
        provider="alpaca",
        orders=(order,),
        fills=(),
        positions=(),
        balances=(
            CanonicalBalance(currency=Currency("USD"), cash=Decimal("1000")),
        ),
        captured_at=now,
        watermark=watermark,
        completeness=SnapshotCompleteness.COMPLETE,
    )

    assert snapshot.provider == "alpaca"
    assert snapshot.orders == (order,)


def test_invalid_run_transition_is_rejected() -> None:
    now = datetime(2026, 10, 22, 12, tzinfo=UTC)
    run = ReconciliationRun.create(
        account_id=AccountId.new(),
        scope=ReconciliationScope.FULL,
        trigger=ReconciliationTrigger.MANUAL,
        started_at=now,
        correlation_id=CorrelationId.new(),
    )

    with pytest.raises(DomainValidationError):
        run.transition_to(ReconciliationRunStatus.COMPLETED)
