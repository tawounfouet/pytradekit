"""Recovery plans and lifecycle."""

from dataclasses import dataclass
from datetime import datetime

from pytradekit.shared import CorrelationId, DomainValidationError, require_utc_datetime

from .enums import RecoveryAction
from .ids import ReconciliationRunId


@dataclass(frozen=True, slots=True)
class RecoveryPlan:
    """Immutable recovery plan selected from reconciliation evidence."""

    run_id: ReconciliationRunId
    actions: tuple[RecoveryAction, ...]
    blocking: bool
    requires_verification: bool
    created_at: datetime
    correlation_id: CorrelationId

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, ReconciliationRunId):
            raise DomainValidationError("RecoveryPlan run_id must be a ReconciliationRunId.")
        require_utc_datetime(self.created_at, field_name="RecoveryPlan created_at")
        if not self.actions:
            raise DomainValidationError("RecoveryPlan must contain at least one action.")
