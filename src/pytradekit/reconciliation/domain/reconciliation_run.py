"""Reconciliation run aggregate."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pytradekit.portfolio.domain import AccountId
from pytradekit.shared import CorrelationId, DomainValidationError, require_utc_datetime

from .enums import (
    ConsistencyStatus,
    ReconciliationRunStatus,
    ReconciliationScope,
    ReconciliationTrigger,
    StateConfidence,
)
from .ids import ReconciliationRunId
from .snapshot import SnapshotWatermark

_ALLOWED: dict[ReconciliationRunStatus, set[ReconciliationRunStatus]] = {
    ReconciliationRunStatus.CREATED: {
        ReconciliationRunStatus.CAPTURING,
        ReconciliationRunStatus.CANCELLED,
        ReconciliationRunStatus.FAILED,
    },
    ReconciliationRunStatus.CAPTURING: {
        ReconciliationRunStatus.COMPARING,
        ReconciliationRunStatus.FAILED,
    },
    ReconciliationRunStatus.COMPARING: {
        ReconciliationRunStatus.RESOLVING,
        ReconciliationRunStatus.VERIFYING,
        ReconciliationRunStatus.COMPLETED,
        ReconciliationRunStatus.FAILED,
    },
    ReconciliationRunStatus.RESOLVING: {
        ReconciliationRunStatus.VERIFYING,
        ReconciliationRunStatus.FAILED,
    },
    ReconciliationRunStatus.VERIFYING: {
        ReconciliationRunStatus.COMPLETED,
        ReconciliationRunStatus.FAILED,
    },
    ReconciliationRunStatus.COMPLETED: set(),
    ReconciliationRunStatus.FAILED: set(),
    ReconciliationRunStatus.CANCELLED: set(),
}


@dataclass(slots=True)
class ReconciliationRun:
    """Aggregate tracking one auditable reconciliation attempt."""

    id: ReconciliationRunId
    account_id: AccountId
    scope: ReconciliationScope
    trigger: ReconciliationTrigger
    status: ReconciliationRunStatus
    started_at: datetime
    completed_at: datetime | None
    internal_watermark: SnapshotWatermark | None
    broker_watermark: SnapshotWatermark | None
    mismatch_count: int
    critical_mismatch_count: int
    result_status: ConsistencyStatus | None
    confidence: StateConfidence | None
    correlation_id: CorrelationId
    version: int = 0

    def __post_init__(self) -> None:
        require_utc_datetime(self.started_at, field_name="ReconciliationRun started_at")
        if self.completed_at is not None:
            require_utc_datetime(self.completed_at, field_name="ReconciliationRun completed_at")
        if self.mismatch_count < 0 or self.critical_mismatch_count < 0:
            raise DomainValidationError("Mismatch counts must be non-negative.")
        if self.critical_mismatch_count > self.mismatch_count:
            raise DomainValidationError("Critical mismatch count cannot exceed mismatch count.")

    @classmethod
    def create(
        cls,
        *,
        account_id: AccountId,
        scope: ReconciliationScope,
        trigger: ReconciliationTrigger,
        started_at: datetime,
        correlation_id: CorrelationId,
    ) -> ReconciliationRun:
        """Create a new reconciliation run."""

        return cls(
            id=ReconciliationRunId.new(),
            account_id=account_id,
            scope=scope,
            trigger=trigger,
            status=ReconciliationRunStatus.CREATED,
            started_at=started_at,
            completed_at=None,
            internal_watermark=None,
            broker_watermark=None,
            mismatch_count=0,
            critical_mismatch_count=0,
            result_status=None,
            confidence=None,
            correlation_id=correlation_id,
        )

    def transition_to(self, status: ReconciliationRunStatus) -> None:
        """Apply one valid lifecycle transition."""

        if status not in _ALLOWED[self.status]:
            raise DomainValidationError(
                f"Invalid reconciliation transition {self.status.value} -> {status.value}."
            )
        self.status = status
        self.version += 1

    def complete(
        self,
        *,
        completed_at: datetime,
        result_status: ConsistencyStatus,
        confidence: StateConfidence,
        mismatch_count: int,
        critical_mismatch_count: int,
    ) -> None:
        """Complete the run without implying CONSISTENT."""

        require_utc_datetime(completed_at, field_name="ReconciliationRun completed_at")
        if ReconciliationRunStatus.COMPLETED not in _ALLOWED[self.status]:
            raise DomainValidationError("Reconciliation run cannot complete from current status.")
        if mismatch_count < 0 or critical_mismatch_count < 0:
            raise DomainValidationError("Mismatch counts must be non-negative.")
        self.status = ReconciliationRunStatus.COMPLETED
        self.completed_at = completed_at
        self.result_status = result_status
        self.confidence = confidence
        self.mismatch_count = mismatch_count
        self.critical_mismatch_count = critical_mismatch_count
        self.version += 1
