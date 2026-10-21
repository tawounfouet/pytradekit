"""Provider-neutral execution report."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pytradekit.execution.domain.execution_status import ExecutionStatus
from pytradekit.execution.domain.fill import Fill
from pytradekit.orders.domain import OrderId
from pytradekit.shared import CorrelationId, DomainValidationError, require_utc_datetime


@dataclass(frozen=True, slots=True)
class ExecutionReport:
    """External execution fact translated into canonical PyTradeKit semantics."""

    order_id: OrderId
    status: ExecutionStatus
    occurred_at: datetime
    correlation_id: CorrelationId
    external_order_id: str | None = None
    fill: Fill | None = None
    rejection_reason: str | None = None

    def __post_init__(self) -> None:
        """Validate report consistency."""
        if not isinstance(self.order_id, OrderId):
            raise DomainValidationError("ExecutionReport order_id must be an OrderId.")
        if not isinstance(self.status, ExecutionStatus):
            raise DomainValidationError("ExecutionReport status must be an ExecutionStatus.")
        require_utc_datetime(self.occurred_at, field_name="ExecutionReport occurred_at")
        if not isinstance(self.correlation_id, CorrelationId):
            raise DomainValidationError(
                "ExecutionReport correlation_id must be a CorrelationId."
            )
        if self.external_order_id is not None and not self.external_order_id.strip():
            raise DomainValidationError("ExecutionReport external_order_id must not be empty.")
        if self.fill is not None and self.fill.order_id != self.order_id:
            raise DomainValidationError("ExecutionReport fill must belong to the same order.")
        if (
            self.status in {ExecutionStatus.PARTIALLY_FILLED, ExecutionStatus.FILLED}
            and self.fill is None
        ):
            raise DomainValidationError("Fill execution report requires a Fill.")
        if (
            self.status is ExecutionStatus.REJECTED
            and (self.rejection_reason is None or not self.rejection_reason.strip())
        ):
            raise DomainValidationError("Rejected execution report requires a reason.")
