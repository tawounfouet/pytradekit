"""LOT-08 PostgreSQL recovery and crash qualification."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from pytradekit.orders import Order, OrderId, OrderSide, TimeInForce
from pytradekit.persistence.unit_of_work import PostgresUnitOfWork
from pytradekit.portfolio.domain import Account, AccountId, Balance
from pytradekit.reconciliation import (
    BrokerSnapshot,
    CanonicalBalance,
    CanonicalFill,
    CanonicalOrder,
    CanonicalPosition,
    ConsistencyStatus,
    ExternalActivityOrigin,
    ReconciliationRunStatus,
    ReconciliationScope,
    ReconciliationTrigger,
    ResolutionStatus,
    ResolutionType,
    SnapshotCompleteness,
    SnapshotWatermark,
    StateConfidence,
)
from pytradekit.reconciliation.adapters.postgres import (
    PostgresInternalSnapshotPort,
    PostgresReconciliationRepository,
    PostgresResolutionExecutor,
)
from pytradekit.reconciliation.application import (
    ConsistencyRegistry,
    ReconcileAccount,
    RecoveryWorkflowCoordinator,
    StaleRunRecovery,
)
from pytradekit.runtime.faults import FaultPoint
from pytradekit.shared import (
    CorrelationId,
    Currency,
    InstrumentId,
    Money,
    Quantity,
)

NOW = datetime(2026, 10, 22, 18, tzinfo=UTC)
FILL_AT = NOW + timedelta(seconds=1)
USD = Currency("USD")


class StepClock:
    """Deterministic clock that makes every observation strictly newer."""

    def __init__(self, current: datetime) -> None:
        self._current = current

    def now(self) -> datetime:
        value = self._current
        self._current += timedelta(seconds=1)
        return value

    def advance(self, delta: timedelta) -> None:
        self._current += delta


class BrokerTruthPort:
    """Return one stable broker truth at a fresh observation timestamp."""

    def __init__(
        self,
        *,
        account_id: AccountId,
        order: Order,
        clock: StepClock,
    ) -> None:
        self._account_id = account_id
        self._order = order
        self._clock = clock
        self.capture_count = 0

    def capture(
        self,
        *,
        account_id: AccountId,
        scope: ReconciliationScope,
    ) -> BrokerSnapshot:
        assert account_id == self._account_id
        _ = scope
        self.capture_count += 1
        captured_at = self._clock.now()
        return BrokerSnapshot(
            account_id=account_id,
            provider="qualification",
            orders=(
                CanonicalOrder(
                    order_id=self._order.id,
                    client_order_id=self._order.client_order_id,
                    external_order_id=self._order.external_order_id,
                    status="filled",
                    filled_quantity=Decimal("1"),
                ),
            ),
            fills=(
                CanonicalFill(
                    external_fill_id="lot08-provider-fill-1",
                    order_id=self._order.id,
                    external_order_id=self._order.external_order_id,
                    quantity=Decimal("1"),
                    price=Decimal("100"),
                    currency=USD,
                    occurred_at=FILL_AT,
                    origin=ExternalActivityOrigin.INTERNAL,
                ),
            ),
            positions=(
                CanonicalPosition(
                    instrument_id=self._order.instrument_id,
                    quantity=Decimal("1"),
                    average_price=Decimal("100"),
                    currency=USD,
                ),
            ),
            balances=(
                CanonicalBalance(
                    currency=USD,
                    cash=Decimal("900"),
                ),
            ),
            captured_at=captured_at,
            watermark=SnapshotWatermark(
                captured_at=captured_at,
                provider_as_of=captured_at,
            ),
            completeness=SnapshotCompleteness.COMPLETE,
        )


class SimulatedProcessKill(BaseException):
    """Synthetic SIGKILL boundary that bypasses Exception recovery handlers."""


class KillAfterResolution:
    """Kill once after economic repair is durable but before verification."""

    def __init__(self) -> None:
        self._raised = False

    def hit(self, point: FaultPoint) -> None:
        if (
            point is FaultPoint.AFTER_RECONCILIATION_RESOLUTION
            and not self._raised
        ):
            self._raised = True
            raise SimulatedProcessKill("synthetic process kill after resolution")


@pytest.fixture
def reconciliation_session_factory(
    postgres_engine: Engine,
) -> Iterator[sessionmaker[Session]]:
    """Allow commits while rolling back all LOT-08 state after each test."""

    connection = postgres_engine.connect()
    outer = connection.begin()
    factory = sessionmaker(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    try:
        yield factory
    finally:
        outer.rollback()
        connection.close()


def _uow_factory(
    factory: sessionmaker[Session],
) -> Callable[[], PostgresUnitOfWork]:
    return lambda: PostgresUnitOfWork(factory)


def _seed(
    factory: sessionmaker[Session],
) -> tuple[AccountId, Order]:
    account_id = AccountId.new()
    order = Order.create_market(
        order_id=OrderId.new(),
        instrument_id=InstrumentId.new(),
        side=OrderSide.BUY,
        quantity=Quantity(Decimal("1")),
        time_in_force=TimeInForce.DAY,
        correlation_id=CorrelationId.new(),
        occurred_at=NOW,
        client_order_id="lot08-client-order-1",
    )
    order.validate(occurred_at=NOW)
    order.mark_submitted(occurred_at=NOW)
    order.accept(
        external_order_id="lot08-provider-order-1",
        occurred_at=NOW,
    )
    order.pull_domain_events()

    with PostgresUnitOfWork(factory) as uow:
        uow.accounts.save(
            Account(
                id=account_id,
                base_currency=USD,
                name="LOT-08 qualification",
            )
        )
        uow.balances.save(
            Balance(
                account_id=account_id,
                currency=USD,
                cash=Money(Decimal("1000"), USD),
                updated_at=NOW,
            )
        )
        uow.orders.add(order)
        uow.commit()

    return account_id, order


def _service(
    *,
    factory: sessionmaker[Session],
    evidence_session: Session,
    account_id: AccountId,
    order: Order,
    clock: StepClock,
    faults: KillAfterResolution | None = None,
) -> tuple[
    ReconcileAccount,
    PostgresReconciliationRepository,
    ConsistencyRegistry,
]:
    repository = PostgresReconciliationRepository(evidence_session)
    registry = ConsistencyRegistry()
    service = ReconcileAccount(
        repository=repository,
        internal_snapshots=PostgresInternalSnapshotPort(
            session_factory=factory,
            clock=clock,
        ),
        broker_snapshots=BrokerTruthPort(
            account_id=account_id,
            order=order,
            clock=clock,
        ),
        clock=clock,
        executor=PostgresResolutionExecutor(_uow_factory(factory)),
        evidence_sink=registry,
        faults=faults,
    )
    return service, repository, registry


def _assert_one_effect(
    factory: sessionmaker[Session],
    *,
    account_id: AccountId,
    order: Order,
) -> None:
    with PostgresUnitOfWork(factory) as uow:
        durable = uow.orders.get(order.id)
        fills = uow.fills.list_for_order(order.id)
        position = uow.positions.get(account_id, order.instrument_id)
        balance = uow.balances.get(account_id, USD)
        imported = tuple(
            record
            for record in uow.outbox.list_pending(limit=100)
            if record.event_type == "ExternalFillImported"
            and record.payload.get("external_fill_id") == "lot08-provider-fill-1"
        )
        uow.commit()

    assert durable is not None
    assert durable.status.value == "filled"
    assert durable.filled_quantity == Quantity(Decimal("1"))
    assert len(fills) == 1
    assert fills[0].external_fill_id == "lot08-provider-fill-1"
    assert position is not None
    assert position.quantity == Decimal("1")
    assert balance is not None
    assert balance.cash.amount == Decimal("900")
    assert len(imported) == 1


def test_periodic_missing_stream_fill_recovers_and_verifies_convergence(
    reconciliation_session_factory: sessionmaker[Session],
) -> None:
    factory = reconciliation_session_factory
    account_id, order = _seed(factory)
    clock = StepClock(NOW + timedelta(seconds=10))
    evidence_session = factory()
    service, repository, registry = _service(
        factory=factory,
        evidence_session=evidence_session,
        account_id=account_id,
        order=order,
        clock=clock,
    )
    workflows = RecoveryWorkflowCoordinator(
        reconciliation=service,
        containment=registry.clear,
    )

    outcome = workflows.periodic(
        account_id=account_id,
        correlation_id=CorrelationId.new(),
    )

    assert outcome.run.trigger is ReconciliationTrigger.PERIODIC
    assert outcome.run.result_status is ConsistencyStatus.CONSISTENT
    assert outcome.run.confidence is StateConfidence.HIGH
    assert outcome.mismatches == ()
    imported = [
        resolution
        for resolution in outcome.resolutions
        if resolution.type is ResolutionType.IMPORT_MISSING_EXTERNAL_EVENT
    ]
    assert len(imported) == 1
    assert imported[0].status is ResolutionStatus.VERIFIED
    assert all(
        resolution.status in {ResolutionStatus.VERIFIED, ResolutionStatus.REJECTED}
        for resolution in outcome.resolutions
    )
    _assert_one_effect(factory, account_id=account_id, order=order)

    replay = workflows.periodic(
        account_id=account_id,
        correlation_id=CorrelationId.new(),
    )

    assert replay.run.result_status is ConsistencyStatus.CONSISTENT
    assert replay.run.confidence is StateConfidence.HIGH
    assert replay.mismatches == ()
    assert replay.resolutions == ()
    _assert_one_effect(factory, account_id=account_id, order=order)
    assert repository.list_active() == ()
    evidence_session.close()


def test_process_kill_after_repair_is_closed_as_stale_and_not_replayed(
    reconciliation_session_factory: sessionmaker[Session],
) -> None:
    factory = reconciliation_session_factory
    account_id, order = _seed(factory)
    clock = StepClock(NOW + timedelta(seconds=10))

    first_session = factory()
    first_service, first_repository, first_registry = _service(
        factory=factory,
        evidence_session=first_session,
        account_id=account_id,
        order=order,
        clock=clock,
        faults=KillAfterResolution(),
    )
    first_workflows = RecoveryWorkflowCoordinator(
        reconciliation=first_service,
        containment=first_registry.clear,
    )

    with pytest.raises(SimulatedProcessKill, match="after resolution"):
        first_workflows.periodic(
            account_id=account_id,
            correlation_id=CorrelationId.new(),
        )

    active = first_repository.list_active()
    assert len(active) == 1
    stale_run_id = active[0].id
    assert active[0].status is ReconciliationRunStatus.RESOLVING
    _assert_one_effect(factory, account_id=account_id, order=order)
    first_session.close()

    clock.advance(timedelta(hours=1))
    second_session = factory()
    second_service, second_repository, second_registry = _service(
        factory=factory,
        evidence_session=second_session,
        account_id=account_id,
        order=order,
        clock=clock,
    )
    stale_runs = StaleRunRecovery(
        repository=second_repository,
        clock=clock,
        stale_after=timedelta(minutes=15),
    )
    second_workflows = RecoveryWorkflowCoordinator(
        reconciliation=second_service,
        stale_runs=stale_runs,
        containment=second_registry.clear,
    )

    recovered = second_workflows.reconnect(
        account_id=account_id,
        correlation_id=CorrelationId.new(),
    )

    abandoned = second_repository.get_run(stale_run_id)
    assert abandoned is not None
    assert abandoned.status is ReconciliationRunStatus.FAILED
    assert recovered.run.trigger is ReconciliationTrigger.RECONNECT
    assert recovered.run.result_status is ConsistencyStatus.CONSISTENT
    assert recovered.run.confidence is StateConfidence.HIGH
    assert recovered.mismatches == ()
    assert recovered.resolutions == ()
    _assert_one_effect(factory, account_id=account_id, order=order)
    second_session.close()
