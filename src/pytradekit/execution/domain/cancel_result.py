"""Immediate result of an execution cancellation attempt."""

from dataclasses import dataclass
from enum import StrEnum

from pytradekit.shared import DomainValidationError


class CancelStatus(StrEnum):
    """Known outcomes of the immediate cancel call."""

    ACKNOWLEDGED = "acknowledged"
    REJECTED = "rejected"
    UNCERTAIN = "uncertain"


@dataclass(frozen=True, slots=True)
class CancelResult:
    """Provider-neutral immediate cancellation result."""

    status: CancelStatus
    reason: str | None = None

    def __post_init__(self) -> None:
        """Validate cancellation result consistency."""
        if not isinstance(self.status, CancelStatus):
            raise DomainValidationError("CancelResult status must be a CancelStatus.")
        if self.status is CancelStatus.REJECTED:
            if self.reason is None or not self.reason.strip():
                raise DomainValidationError("Rejected cancellation requires a reason.")
