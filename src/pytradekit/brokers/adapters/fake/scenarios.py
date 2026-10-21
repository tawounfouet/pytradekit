"""Deterministic fake execution scenarios for OMS qualification."""

from __future__ import annotations

from dataclasses import dataclass

from pytradekit.execution import CancelStatus, ExecutionStatus, SubmissionStatus
from pytradekit.shared import DomainValidationError, Price, Quantity


@dataclass(frozen=True, slots=True)
class FakeExecutionScenario:
    """Configuration describing deterministic fake broker behavior."""

    submission_status: SubmissionStatus = SubmissionStatus.ACKNOWLEDGED
    submission_reason: str | None = None
    fill_price: Price | None = None
    fill_quantities: tuple[Quantity, ...] = ()
    fill_remaining: bool = False
    cancel_status: CancelStatus = CancelStatus.ACKNOWLEDGED
    cancel_reason: str | None = None
    uncertain_query_status: ExecutionStatus | None = None

    def __post_init__(self) -> None:
        """Validate scenario consistency."""
        if (
            self.submission_status is SubmissionStatus.REJECTED
            and (self.submission_reason is None or not self.submission_reason.strip())
        ):
            raise DomainValidationError("Rejected fake submission requires a reason.")
        if (
            self.cancel_status is CancelStatus.REJECTED
            and (self.cancel_reason is None or not self.cancel_reason.strip())
        ):
            raise DomainValidationError("Rejected fake cancellation requires a reason.")
        if (self.fill_quantities or self.fill_remaining) and self.fill_price is None:
            raise DomainValidationError("Fake fill scenario requires fill_price.")
        if any(quantity.value <= 0 for quantity in self.fill_quantities):
            raise DomainValidationError("Fake fill quantities must be greater than zero.")

    @classmethod
    def accept_immediately(cls) -> FakeExecutionScenario:
        """Acknowledge the order and leave it accepted."""
        return cls()

    @classmethod
    def reject_immediately(cls, *, reason: str) -> FakeExecutionScenario:
        """Reject the order immediately."""
        return cls(submission_status=SubmissionStatus.REJECTED, submission_reason=reason)

    @classmethod
    def fill_immediately(cls, *, price: Price) -> FakeExecutionScenario:
        """Acknowledge and fully fill the order."""
        return cls(fill_price=price, fill_remaining=True)

    @classmethod
    def partial_then_fill(
        cls,
        *,
        price: Price,
        partial_quantities: tuple[Quantity, ...],
    ) -> FakeExecutionScenario:
        """Emit configured partial fills and then fill the remaining quantity."""
        if not partial_quantities:
            raise DomainValidationError("Partial fill scenario requires at least one quantity.")
        return cls(
            fill_price=price,
            fill_quantities=partial_quantities,
            fill_remaining=True,
        )

    @classmethod
    def submit_timeout(
        cls,
        *,
        resolve_as: ExecutionStatus | None = ExecutionStatus.ACCEPTED,
    ) -> FakeExecutionScenario:
        """Return an uncertain submission that can later resolve through query_order."""
        return cls(
            submission_status=SubmissionStatus.UNCERTAIN,
            uncertain_query_status=resolve_as,
        )

    @classmethod
    def cancel_rejected(cls, *, reason: str) -> FakeExecutionScenario:
        """Acknowledge submission but reject cancellation."""
        return cls(cancel_status=CancelStatus.REJECTED, cancel_reason=reason)
