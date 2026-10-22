"""PostgreSQL reconciliation repository contract."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from pytradekit.portfolio.domain import AccountId
from pytradekit.reconciliation.adapters.postgres import PostgresReconciliationRepository
from pytradekit.reconciliation.domain import (
    Mismatch,
    MismatchId,
    MismatchSeverity,
    MismatchType,
    ReconciliationRun,
    ReconciliationRunStatus,
    ReconciliationScope,
    ReconciliationTrigger,
    Resolution,
    ResolutionId,
    ResolutionType,
)
from pytradekit.shared import CorrelationId


def test_reconciliation_evidence_round_trip(postgres_session: Session) -> None:
    now = datetime(2026, 10, 22, 12, tzinfo=UTC)
    repository = PostgresReconciliationRepository(postgres_session)
    run = ReconciliationRun.create(
        account_id=AccountId.new(),
        scope=ReconciliationScope.FULL,
        trigger=ReconciliationTrigger.MANUAL,
        started_at=now,
        correlation_id=CorrelationId.new(),
    )
    repository.add_run(run)
    mismatch = Mismatch(
        id=MismatchId.new(),
        run_id=run.id,
        type=MismatchType.MISSING_INTERNAL_FILL,
        severity=MismatchSeverity.CRITICAL,
        entity_type="fill",
        entity_id="fill-1",
        internal_value=None,
        external_value={"external_fill_id": "fill-1"},
        detected_at=now,
    )
    repository.add_mismatch(mismatch)
    resolution = Resolution(
        id=ResolutionId.new(),
        run_id=run.id,
        mismatch_id=mismatch.id,
        type=ResolutionType.IMPORT_MISSING_EXTERNAL_EVENT,
        reason="Provider execution is proven.",
        actor="system",
        started_at=now,
        correlation_id=run.correlation_id,
    )
    repository.add_resolution(resolution)

    restored = repository.get_run(run.id)

    assert restored is not None
    assert repository.list_mismatches(run.id) == (mismatch,)
    assert repository.list_resolutions(run.id)[0].type is resolution.type


def test_stale_active_run_query(postgres_session: Session) -> None:
    now = datetime(2026, 10, 22, 12, tzinfo=UTC)
    repository = PostgresReconciliationRepository(postgres_session)
    run = ReconciliationRun.create(
        account_id=AccountId.new(),
        scope=ReconciliationScope.ORDERS,
        trigger=ReconciliationTrigger.PERIODIC,
        started_at=now - timedelta(hours=2),
        correlation_id=CorrelationId.new(),
    )
    repository.add_run(run)
    run.transition_to(ReconciliationRunStatus.CAPTURING)
    repository.save_run(run)

    stale = repository.list_stale(stale_before=now - timedelta(hours=1))

    assert [item.id for item in stale] == [run.id]
