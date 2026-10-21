"""Deterministic fake implementation of the execution port."""

from __future__ import annotations

from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from pytradekit.brokers.adapters.fake.scenarios import FakeExecutionScenario
from pytradekit.execution import (
    CancelResult,
    CancelStatus,
    ExecutionReport,
    ExecutionStatus,
    Fill,
    FillId,
    SubmissionResult,
    SubmissionStatus,
)
from pytradekit.orders.domain import Order, OrderId
from pytradekit.runtime.ports import ClockPort
from pytradekit.shared import InvariantViolationError, Quantity


class FakeExecutionAdapter:
    """Broker fake with deterministic submission, reports, fills, and cancellation."""

    def __init__(self, *, scenario: FakeExecutionScenario, clock: ClockPort) -> None:
        self._scenario = scenario
        self._clock = clock
        self._submission_results: dict[OrderId, SubmissionResult] = {}
        self._cancel_results: dict[OrderId, CancelResult] = {}
        self._pending_reports: dict[OrderId, list[ExecutionReport]] = {}
        self._latest_reports: dict[OrderId, ExecutionReport] = {}
        self._query_resolution_created: set[OrderId] = set()

    def submit(self, order: Order) -> SubmissionResult:
        """Submit once and return the same result for repeated calls."""
        existing = self._submission_results.get(order.id)
        if existing is not None:
            return existing

        if self._scenario.submission_status is SubmissionStatus.REJECTED:
            result = SubmissionResult(
                status=SubmissionStatus.REJECTED,
                reason=self._scenario.submission_reason,
            )
            self._submission_results[order.id] = result
            return result

        if self._scenario.submission_status is SubmissionStatus.UNCERTAIN:
            result = SubmissionResult(status=SubmissionStatus.UNCERTAIN)
            self._submission_results[order.id] = result
            return result

        external_order_id = self._external_order_id(order.id)
        result = SubmissionResult(
            status=SubmissionStatus.ACKNOWLEDGED,
            external_order_id=external_order_id,
        )
        self._submission_results[order.id] = result
        self._queue_report(
            ExecutionReport(
                order_id=order.id,
                status=ExecutionStatus.ACCEPTED,
                occurred_at=self._clock.now(),
                correlation_id=order.correlation_id,
                external_order_id=external_order_id,
            )
        )
        self._queue_configured_fills(order, external_order_id=external_order_id)
        return result

    def cancel(self, order: Order) -> CancelResult:
        """Request cancellation once and deterministically queue confirmation when acknowledged."""
        existing = self._cancel_results.get(order.id)
        if existing is not None:
            return existing

        if self._scenario.cancel_status is CancelStatus.REJECTED:
            result = CancelResult(
                status=CancelStatus.REJECTED,
                reason=self._scenario.cancel_reason,
            )
            self._cancel_results[order.id] = result
            return result

        if self._scenario.cancel_status is CancelStatus.UNCERTAIN:
            result = CancelResult(status=CancelStatus.UNCERTAIN)
            self._cancel_results[order.id] = result
            return result

        result = CancelResult(status=CancelStatus.ACKNOWLEDGED)
        self._cancel_results[order.id] = result
        self._queue_report(
            ExecutionReport(
                order_id=order.id,
                status=ExecutionStatus.CANCELLED,
                occurred_at=self._clock.now(),
                correlation_id=order.correlation_id,
                external_order_id=order.external_order_id,
            )
        )
        return result

    def query_order(self, order: Order) -> ExecutionReport | None:
        """Return a configured uncertainty resolution or the latest known report."""
        if (
            self._scenario.submission_status is SubmissionStatus.UNCERTAIN
            and self._scenario.uncertain_query_status is not None
            and order.id not in self._query_resolution_created
        ):
            status = self._scenario.uncertain_query_status
            if status not in {ExecutionStatus.ACCEPTED, ExecutionStatus.REJECTED}:
                raise InvariantViolationError(
                    "Fake uncertain query resolution currently supports ACCEPTED or REJECTED."
                )

            external_order_id = self._external_order_id(order.id)
            report = ExecutionReport(
                order_id=order.id,
                status=status,
                occurred_at=self._clock.now(),
                correlation_id=order.correlation_id,
                external_order_id=external_order_id if status is ExecutionStatus.ACCEPTED else None,
                rejection_reason=(
                    "fake query rejection" if status is ExecutionStatus.REJECTED else None
                ),
            )
            self._query_resolution_created.add(order.id)
            self._latest_reports[order.id] = report
            return report

        return self._latest_reports.get(order.id)

    def drain_reports(self, order_id: OrderId | None = None) -> tuple[ExecutionReport, ...]:
        """Return and remove pending fake reports for deterministic delivery in tests."""
        if order_id is not None:
            reports = tuple(self._pending_reports.pop(order_id, []))
            return reports

        reports: list[ExecutionReport] = []
        for current_order_id in sorted(self._pending_reports, key=str):
            reports.extend(self._pending_reports[current_order_id])
        self._pending_reports.clear()
        return tuple(reports)

    def inject_report(self, report: ExecutionReport) -> None:
        """Inject a duplicate, late, or out-of-order report explicitly."""
        self._queue_report(report)

    def _queue_configured_fills(self, order: Order, *, external_order_id: str) -> None:
        if self._scenario.fill_price is None:
            return

        cumulative = Decimal("0")
        fill_index = 0
        for quantity in self._scenario.fill_quantities:
            cumulative += quantity.value
            if cumulative > order.quantity.value:
                raise InvariantViolationError(
                    "Fake scenario fill quantities exceed order quantity."
                )
            fill_index += 1
            self._queue_fill(
                order,
                quantity=quantity,
                index=fill_index,
                external_order_id=external_order_id,
                final=cumulative == order.quantity.value,
            )

        if self._scenario.fill_remaining and cumulative < order.quantity.value:
            fill_index += 1
            remaining = Quantity(order.quantity.value - cumulative)
            self._queue_fill(
                order,
                quantity=remaining,
                index=fill_index,
                external_order_id=external_order_id,
                final=True,
            )

    def _queue_fill(
        self,
        order: Order,
        *,
        quantity: Quantity,
        index: int,
        external_order_id: str,
        final: bool,
    ) -> None:
        fill_price = self._scenario.fill_price
        if fill_price is None:
            raise InvariantViolationError("Fake fill scenario requires fill_price.")

        fill_identity = f"fake-fill-{order.id}-{index}"
        fill = Fill(
            id=FillId(uuid5(NAMESPACE_URL, fill_identity)),
            order_id=order.id,
            quantity=quantity,
            price=fill_price,
            occurred_at=self._clock.now(),
            external_fill_id=fill_identity,
        )
        self._queue_report(
            ExecutionReport(
                order_id=order.id,
                status=ExecutionStatus.FILLED if final else ExecutionStatus.PARTIALLY_FILLED,
                occurred_at=self._clock.now(),
                correlation_id=order.correlation_id,
                external_order_id=external_order_id,
                fill=fill,
            )
        )

    def _queue_report(self, report: ExecutionReport) -> None:
        self._pending_reports.setdefault(report.order_id, []).append(report)
        self._latest_reports[report.order_id] = report

    @staticmethod
    def _external_order_id(order_id: OrderId) -> str:
        return f"fake-order-{order_id}"
