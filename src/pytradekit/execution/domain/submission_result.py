"""Immediate result of an execution submission attempt."""

from dataclasses import dataclass
from enum import StrEnum

from pytradekit.shared import DomainValidationError


class SubmissionStatus(StrEnum):
    """Known outcomes of the immediate submit call."""

    ACKNOWLEDGED = "acknowledged"
    REJECTED = "rejected"
    UNCERTAIN = "uncertain"


@dataclass(frozen=True, slots=True)
class SubmissionResult:
    """Provider-neutral immediate submission result."""

    status: SubmissionStatus
    external_order_id: str | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        """Validate submission result consistency."""
        if not isinstance(self.status, SubmissionStatus):
            raise DomainValidationError("SubmissionResult status must be a SubmissionStatus.")
        if self.external_order_id is not None and not self.external_order_id.strip():
            raise DomainValidationError("SubmissionResult external_order_id must not be empty.")
        if self.status is SubmissionStatus.ACKNOWLEDGED and self.external_order_id is None:
            raise DomainValidationError("Acknowledged submission requires external_order_id.")
        if self.status is SubmissionStatus.REJECTED:
            if self.reason is None or not self.reason.strip():
                raise DomainValidationError("Rejected submission requires a reason.")
