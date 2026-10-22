"""Mismatch evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pytradekit.shared import DomainValidationError, require_utc_datetime

from .enums import MismatchSeverity, MismatchType
from .ids import MismatchId, ReconciliationRunId

JsonEvidence = dict[str, str | int | float | bool | None]


@dataclass(frozen=True, slots=True)
class Mismatch:
    """Immutable divergence evidence detected during comparison."""

    id: MismatchId
    run_id: ReconciliationRunId
    type: MismatchType
    severity: MismatchSeverity
    entity_type: str
    entity_id: str | None
    internal_value: JsonEvidence | None
    external_value: JsonEvidence | None
    detected_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.id, MismatchId):
            raise DomainValidationError("Mismatch id must be a MismatchId.")
        if not isinstance(self.run_id, ReconciliationRunId):
            raise DomainValidationError("Mismatch run_id must be a ReconciliationRunId.")
        entity_type = self.entity_type.strip() if isinstance(self.entity_type, str) else ""
        if not entity_type:
            raise DomainValidationError("Mismatch entity_type must be non-empty.")
        object.__setattr__(self, "entity_type", entity_type)
        if self.entity_id is not None and not self.entity_id.strip():
            raise DomainValidationError("Mismatch entity_id must not be empty.")
        require_utc_datetime(self.detected_at, field_name="Mismatch detected_at")
