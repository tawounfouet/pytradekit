"""PostgreSQL ReconciliationRepository implementation."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pytradekit.persistence import ConcurrentWriteError
from pytradekit.reconciliation.domain import (
    Mismatch,
    ReconciliationRun,
    ReconciliationRunId,
    ReconciliationRunStatus,
    Resolution,
)
from pytradekit.reconciliation.ports import ReconciliationRepository

from .mapper import (
    mismatch_from_model,
    mismatch_to_values,
    resolution_from_model,
    resolution_to_values,
    run_from_model,
    run_to_values,
)
from .models import (
    ReconciliationMismatchModel,
    ReconciliationResolutionModel,
    ReconciliationRunModel,
)

_ACTIVE_STATUSES = tuple(
    status.value
    for status in (
        ReconciliationRunStatus.CREATED,
        ReconciliationRunStatus.CAPTURING,
        ReconciliationRunStatus.COMPARING,
        ReconciliationRunStatus.RESOLVING,
        ReconciliationRunStatus.VERIFYING,
    )
)


class ConcurrentReconciliationError(RuntimeError):
    """Raised when active reconciliation ownership conflicts."""


class ReconciliationRecordExistsError(RuntimeError):
    """Raised when immutable reconciliation evidence is duplicated."""


class PostgresReconciliationRepository(ReconciliationRepository):
    """Durable evidence repository with optimistic run concurrency."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._seen_versions: dict[ReconciliationRunId, int] = {}

    def add_run(self, run: ReconciliationRun) -> None:
        self._session.add(ReconciliationRunModel(**run_to_values(run)))
        try:
            self._session.flush()
        except IntegrityError as exc:
            raise ConcurrentReconciliationError(
                "An active reconciliation run already owns this account and scope."
            ) from exc
        self._seen_versions[run.id] = run.version

    def get_run(self, run_id: ReconciliationRunId) -> ReconciliationRun | None:
        row = self._session.get(ReconciliationRunModel, run_id.value)
        if row is None:
            return None
        return self._remember(row)

    def save_run(self, run: ReconciliationRun) -> None:
        row = self._session.execute(
            select(ReconciliationRunModel)
            .where(ReconciliationRunModel.id == run.id.value)
            .with_for_update()
        ).scalar_one_or_none()
        if row is None:
            raise LookupError(f"Reconciliation run {run.id} was not found.")
        expected = self._seen_versions.get(run.id, row.version)
        if row.version != expected:
            raise ConcurrentWriteError(
                f"Reconciliation run {run.id} changed concurrently: "
                f"expected {expected}, found {row.version}."
            )
        if run.version < expected:
            raise ConcurrentWriteError(
                f"Reconciliation run {run.id} cannot regress version "
                f"{expected} to {run.version}."
            )
        for key, value in run_to_values(run).items():
            if key != "id":
                setattr(row, key, value)
        self._session.flush()
        self._seen_versions[run.id] = run.version

    def list_active(self) -> tuple[ReconciliationRun, ...]:
        rows = self._session.execute(
            select(ReconciliationRunModel)
            .where(ReconciliationRunModel.status.in_(_ACTIVE_STATUSES))
            .order_by(ReconciliationRunModel.started_at, ReconciliationRunModel.id)
        ).scalars().all()
        return tuple(self._remember(row) for row in rows)

    def list_stale(self, *, stale_before: datetime) -> tuple[ReconciliationRun, ...]:
        rows = self._session.execute(
            select(ReconciliationRunModel)
            .where(
                ReconciliationRunModel.status.in_(_ACTIVE_STATUSES),
                ReconciliationRunModel.started_at < stale_before,
            )
            .order_by(ReconciliationRunModel.started_at, ReconciliationRunModel.id)
        ).scalars().all()
        return tuple(self._remember(row) for row in rows)

    def add_mismatch(self, mismatch: Mismatch) -> None:
        self._session.add(ReconciliationMismatchModel(**mismatch_to_values(mismatch)))
        try:
            self._session.flush()
        except IntegrityError as exc:
            raise ReconciliationRecordExistsError(
                f"Mismatch {mismatch.id} already exists."
            ) from exc

    def list_mismatches(self, run_id: ReconciliationRunId) -> tuple[Mismatch, ...]:
        rows = self._session.execute(
            select(ReconciliationMismatchModel)
            .where(ReconciliationMismatchModel.run_id == run_id.value)
            .order_by(
                ReconciliationMismatchModel.detected_at,
                ReconciliationMismatchModel.id,
            )
        ).scalars().all()
        return tuple(mismatch_from_model(row) for row in rows)

    def add_resolution(self, resolution: Resolution) -> None:
        self._session.add(ReconciliationResolutionModel(**resolution_to_values(resolution)))
        try:
            self._session.flush()
        except IntegrityError as exc:
            raise ReconciliationRecordExistsError(
                f"Resolution {resolution.id} already exists."
            ) from exc

    def save_resolution(self, resolution: Resolution) -> None:
        row = self._session.execute(
            select(ReconciliationResolutionModel)
            .where(ReconciliationResolutionModel.id == resolution.id.value)
            .with_for_update()
        ).scalar_one_or_none()
        if row is None:
            raise LookupError(f"Resolution {resolution.id} was not found.")
        for key, value in resolution_to_values(resolution).items():
            if key != "id":
                setattr(row, key, value)
        self._session.flush()

    def list_resolutions(self, run_id: ReconciliationRunId) -> tuple[Resolution, ...]:
        rows = self._session.execute(
            select(ReconciliationResolutionModel)
            .where(ReconciliationResolutionModel.run_id == run_id.value)
            .order_by(
                ReconciliationResolutionModel.started_at,
                ReconciliationResolutionModel.id,
            )
        ).scalars().all()
        return tuple(resolution_from_model(row) for row in rows)

    def _remember(self, row: ReconciliationRunModel) -> ReconciliationRun:
        run = run_from_model(row)
        self._seen_versions[run.id] = run.version
        return run
