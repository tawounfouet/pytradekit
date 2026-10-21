"""ExecutionPort adapter backed by deterministic historical bars."""

from copy import deepcopy
from dataclasses import dataclass
from uuid import NAMESPACE_URL, uuid5

from pytradekit.backtesting.domain import (
    CostModel,
    ExecutionModel,
    FillContext,
    LatencyModel,
    SlippageModel,
)
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
from pytradekit.market_data.domain import MarketDataEvent
from pytradekit.orders.domain import Order, OrderId


@dataclass(slots=True)
class _PendingOrder:
    order: Order
    external_order_id: str
    eligible_events_seen: int = 0


class SimulatedExecutionAdapter:
    """Canonical ExecutionPort implementation for deterministic bar backtests."""

    def __init__(
        self,
        *,
        execution_model: ExecutionModel,
        cost_model: CostModel,
        slippage_model: SlippageModel,
        latency_model: LatencyModel,
    ) -> None:
        self._execution_model = execution_model
        self._cost_model = cost_model
        self._slippage_model = slippage_model
        self._latency_model = latency_model
        self._pending: dict[OrderId, _PendingOrder] = {}
        self._latest_reports: dict[OrderId, ExecutionReport] = {}

    def submit(self, order: Order) -> SubmissionResult:
        external_order_id = f"sim-{order.id}"
        self._pending[order.id] = _PendingOrder(
            order=deepcopy(order),
            external_order_id=external_order_id,
        )
        return SubmissionResult(
            status=SubmissionStatus.ACKNOWLEDGED,
            external_order_id=external_order_id,
        )

    def cancel(self, order: Order) -> CancelResult:
        pending = self._pending.pop(order.id, None)
        if pending is None:
            return CancelResult(status=CancelStatus.REJECTED, reason="Order is not pending.")
        report = ExecutionReport(
            order_id=order.id,
            status=ExecutionStatus.CANCELLED,
            occurred_at=order.updated_at,
            correlation_id=order.correlation_id,
            external_order_id=pending.external_order_id,
        )
        self._latest_reports[order.id] = report
        return CancelResult(status=CancelStatus.ACKNOWLEDGED)

    def query_order(self, order: Order) -> ExecutionReport | None:
        report = self._latest_reports.get(order.id)
        return deepcopy(report) if report is not None else None

    def on_market_event(self, event: MarketDataEvent) -> tuple[ExecutionReport, ...]:
        """Evaluate orders submitted before this event against its bar."""
        reports: list[ExecutionReport] = []
        for order_id in tuple(self._pending):
            pending = self._pending[order_id]
            order = pending.order
            if event.instrument_id != order.instrument_id:
                continue
            if event.event_time <= order.updated_at:
                continue
            pending.eligible_events_seen += 1
            if pending.eligible_events_seen < self._latency_model.future_events:
                continue
            base_price = self._execution_model.fill_price(order, event.bar)
            if base_price is None:
                continue
            price = self._slippage_model.apply(base_price, order.side)
            quantity = order.remaining_quantity
            fee = self._cost_model.calculate(
                FillContext(side=order.side, quantity=quantity, price=price)
            )
            fill_uuid = uuid5(
                NAMESPACE_URL,
                f"pytradekit:{order.id}:{event.event_time.isoformat()}:{quantity.value}",
            )
            fill = Fill(
                id=FillId(fill_uuid),
                order_id=order.id,
                quantity=quantity,
                price=price,
                occurred_at=event.bar.start_time,
                external_fill_id=f"sim-fill-{fill_uuid}",
                fee=fee,
            )
            report = ExecutionReport(
                order_id=order.id,
                status=ExecutionStatus.FILLED,
                occurred_at=event.bar.start_time,
                correlation_id=order.correlation_id,
                external_order_id=pending.external_order_id,
                fill=fill,
            )
            reports.append(report)
            self._latest_reports[order.id] = report
            del self._pending[order_id]
        return tuple(reports)
