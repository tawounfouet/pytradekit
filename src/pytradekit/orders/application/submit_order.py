"""SubmitOrder application use case."""

from pytradekit.execution import SubmissionStatus
from pytradekit.orders.application.models import (
    OrderSnapshot,
    SubmitOrderCommand,
    SubmitOrderResult,
)
from pytradekit.orders.domain import InvalidOrderError, Order, OrderId, OrderType
from pytradekit.orders.ports import (
    ConsistencyGatePort,
    ExecutionPort,
    OrderAuthorizationGatePort,
    OrderRepository,
    RiskEvaluationPort,
)
from pytradekit.runtime.ports import ClockPort


class SubmitOrder:
    """Create, safety-check, risk-check, persist, submit, and apply the result."""

    def __init__(
        self,
        *,
        repository: OrderRepository,
        execution: ExecutionPort,
        clock: ClockPort,
        risk: RiskEvaluationPort | None = None,
        consistency_gate: ConsistencyGatePort | None = None,
        authorization_gate: OrderAuthorizationGatePort,
    ) -> None:
        self._repository = repository
        self._execution = execution
        self._clock = clock
        self._risk = risk
        self._consistency_gate = consistency_gate
        self._authorization_gate = authorization_gate

    def execute(self, command: SubmitOrderCommand) -> SubmitOrderResult:
        """Execute one order submission without blind retry or safety bypass."""
        account_id = command.account_id
        if account_id is None:
            raise InvalidOrderError(
                "Order submission requires account_id for authorization."
            )
        self._authorization_gate.ensure_submit_allowed(account_id)

        order_id = command.order_id or OrderId.new()
        now = self._clock.now()

        if command.order_type is OrderType.MARKET:
            if command.limit_price is not None:
                raise InvalidOrderError(
                    "MARKET order command must not define limit_price."
                )
            order = Order.create_market(
                order_id=order_id,
                instrument_id=command.instrument_id,
                side=command.side,
                quantity=command.quantity,
                time_in_force=command.time_in_force,
                correlation_id=command.correlation_id,
                occurred_at=now,
                client_order_id=command.client_order_id,
            )
        else:
            if command.limit_price is None:
                raise InvalidOrderError("LIMIT order command requires limit_price.")
            order = Order.create_limit(
                order_id=order_id,
                instrument_id=command.instrument_id,
                side=command.side,
                quantity=command.quantity,
                time_in_force=command.time_in_force,
                correlation_id=command.correlation_id,
                occurred_at=now,
                limit_price=command.limit_price,
                client_order_id=command.client_order_id,
            )

        order.validate(occurred_at=self._clock.now())
        if (
            self._risk is not None or self._consistency_gate is not None
        ) and command.account_id is None:
            raise InvalidOrderError(
                "Risk or consistency-gated submission requires account_id."
            )

        if self._consistency_gate is not None:
            account_id = command.account_id
            if account_id is None:
                raise InvalidOrderError(
                    "Consistency-gated submission requires account_id."
                )
            self._consistency_gate.ensure_risk_increase_allowed(account_id)

        self._repository.add(order)
        risk_decision: str | None = None
        risk_violation_codes: tuple[str, ...] = ()
        risk_issues: tuple[str, ...] = ()

        if self._risk is not None:
            account_id = command.account_id
            if account_id is None:
                raise InvalidOrderError("Risk-gated submission requires account_id.")
            gate = self._risk.evaluate(
                order,
                account_id=account_id,
                reference_price=command.reference_price,
                strategy_id=command.strategy_id,
                start_of_day_nav=command.start_of_day_nav,
            )
            risk_decision = gate.decision
            risk_violation_codes = gate.violation_codes
            risk_issues = gate.issues
            if not gate.allowed:
                return SubmitOrderResult(
                    order=OrderSnapshot.from_order(order),
                    submission_status=None,
                    risk_decision=risk_decision,
                    risk_violation_codes=risk_violation_codes,
                    risk_issues=risk_issues,
                )

        order.mark_submitted(occurred_at=self._clock.now())
        self._repository.save(order)

        submission = self._execution.submit(order)
        if submission.status is SubmissionStatus.ACKNOWLEDGED:
            external_order_id = submission.external_order_id
            if external_order_id is None:
                raise InvalidOrderError(
                    "Acknowledged submission requires external_order_id."
                )
            order.accept(
                external_order_id=external_order_id,
                occurred_at=self._clock.now(),
            )
        elif submission.status is SubmissionStatus.REJECTED:
            reason = submission.reason
            if reason is None:
                raise InvalidOrderError("Rejected submission requires a reason.")
            order.reject(reason=reason, occurred_at=self._clock.now())
        else:
            order.mark_submission_uncertain(occurred_at=self._clock.now())

        self._repository.save(order)
        return SubmitOrderResult(
            order=OrderSnapshot.from_order(order),
            submission_status=submission.status,
            risk_decision=risk_decision,
            risk_violation_codes=risk_violation_codes,
            risk_issues=risk_issues,
        )
