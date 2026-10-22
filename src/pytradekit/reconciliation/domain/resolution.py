"""Auditable mismatch resolutions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pytradekit.shared import CorrelationId, DomainValidationError, require_utc_datetime

from .enums import ResolutionStatus, ResolutionType
from .ids import MismatchId, ReconciliationRunId, ResolutionId


@dataclass(slots=True)
class Resolution:
    """Explicit recovery decision and its verification lifecycle."""

    id: ResolutionId
    run_id: ReconciliationRunId
    mismatch_id: MismatchId
    type: ResolutionType
    reason: str
    actor: str
    started_at: datetime
    correlation_id: CorrelationId
    status: ResolutionStatus = ResolutionStatus.PLANNED
    completed_at: datetime | None = None
    verification_status: str | None = None

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise DomainValidationError("Resolution reason must be non-empty.")
        if not self.actor.strip():
            raise DomainValidationError("Resolution actor must be non-empty.")
        require_utc_datetime(self.started_at, field_name="Resolution started_at")
        if self.completed_at is not None:
            require_utc_datetime(self.completed_at, field_name="Resolution completed_at")

    def mark_applying(self) -> None:
        """Mark side-effect execution as started."""

        if self.status is not ResolutionStatus.PLANNED:
            raise DomainValidationError("Only a planned resolution can start applying.")
        self.status = ResolutionStatus.APPLYING

    def mark_applied(self, *, completed_at: datetime) -> None:
        """Record successful application without claiming convergence."""

        if self.status is not ResolutionStatus.APPLYING:
            raise DomainValidationError("Only an applying resolution can be applied.")
        require_utc_datetime(completed_at, field_name="Resolution completed_at")
        self.status = ResolutionStatus.APPLIED
        self.completed_at = completed_at

    def mark_verified(self, *, verification_status: str) -> None:
        """Record verification separately from application."""

        if self.status is not ResolutionStatus.APPLIED:
            raise DomainValidationError("Only an applied resolution can be verified.")
        if not verification_status.strip():
            raise DomainValidationError("Verification status must be non-empty.")
        self.status = ResolutionStatus.VERIFIED
        self.verification_status = verification_status.strip()

    def mark_rejected(
        self,
        *,
        completed_at: datetime,
        verification_status: str,
    ) -> None:
        """Close a planned action that fresh convergence proves unnecessary."""

        if self.status is not ResolutionStatus.PLANNED:
            raise DomainValidationError("Only a planned resolution can be rejected.")
        require_utc_datetime(completed_at, field_name="Resolution completed_at")
        if not verification_status.strip():
            raise DomainValidationError("Rejection status must be non-empty.")
        self.status = ResolutionStatus.REJECTED
        self.completed_at = completed_at
        self.verification_status = verification_status.strip()

    def mark_failed(self, *, completed_at: datetime, verification_status: str) -> None:
        """Record a failed application or verification."""

        require_utc_datetime(completed_at, field_name="Resolution completed_at")
        if not verification_status.strip():
            raise DomainValidationError("Failure status must be non-empty.")
        self.status = ResolutionStatus.FAILED
        self.completed_at = completed_at
        self.verification_status = verification_status.strip()
