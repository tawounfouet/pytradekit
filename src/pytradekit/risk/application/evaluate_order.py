"""EvaluateOrderRisk application use case."""

from dataclasses import dataclass

from pytradekit.orders.domain import OrderSide, OrderType
from pytradekit.portfolio.domain import AccountId, PortfolioInvariantError
from pytradekit.risk.domain import (
    ProjectedPortfolio,
    RiskContext,
    RiskDecision,
    RiskEvaluation,
    RiskOrder,
    RiskPolicy,
    RiskScope,
    RiskViolation,
)
from pytradekit.risk.domain.projected_portfolio import project_portfolio
from pytradekit.risk.domain.risk_decision import most_restrictive
from pytradekit.risk.domain.trading_halt import TradingHalt, TradingHaltId
from pytradekit.risk.ports import PortfolioViewPort, RiskPolicyRepository, TradingHaltRepository
from pytradekit.runtime.ports import ClockPort
from pytradekit.shared import InstrumentId, Money, Price, Quantity


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderRiskRequest:
    """Application request for deterministic pre-trade risk evaluation."""

    account_id: AccountId
    instrument_id: InstrumentId
    side: OrderSide
    order_type: OrderType
    quantity: Quantity
    limit_price: Price | None = None
    reference_price: Price | None = None
    strategy_id: str | None = None
    start_of_day_nav: Money | None = None


@dataclass(frozen=True, slots=True)
class OrderRiskResult:
    """Aggregated result across all applicable policies."""

    decision: RiskDecision
    evaluations: tuple[RiskEvaluation, ...]
    violations: tuple[RiskViolation, ...]
    issues: tuple[str, ...]
    projected: ProjectedPortfolio | None
    risk_increasing: bool

    @property
    def allowed(self) -> bool:
        """Return whether submission may continue."""
        return self.decision in {RiskDecision.ALLOW, RiskDecision.WARN}


class EvaluateOrderRisk:
    """Evaluate projected state, active halts, and all applicable policies."""

    def __init__(
        self,
        *,
        policies: RiskPolicyRepository,
        halts: TradingHaltRepository,
        portfolio: PortfolioViewPort,
        clock: ClockPort,
    ) -> None:
        self._policies = policies
        self._halts = halts
        self._portfolio = portfolio
        self._clock = clock

    def execute(self, request: OrderRiskRequest) -> OrderRiskResult:
        """Evaluate one order against projected portfolio state."""
        current = self._portfolio.get_snapshot(request.account_id)
        if current is None:
            return self._input_reject("PORTFOLIO_STATE_UNAVAILABLE")

        reference_price = self._resolve_price(request)
        if reference_price is None:
            return self._input_reject("REFERENCE_PRICE_UNAVAILABLE")

        try:
            projected = project_portfolio(
                current,
                instrument_id=request.instrument_id,
                side=request.side,
                quantity=request.quantity,
                reference_price=reference_price,
            )
        except PortfolioInvariantError:
            return self._input_reject("PORTFOLIO_PROJECTION_UNAVAILABLE")

        policies = self._applicable_policies(request)
        active_halts = self._applicable_halts(request)
        if active_halts:
            if projected.risk_increasing:
                return OrderRiskResult(
                    decision=RiskDecision.REJECT,
                    evaluations=(),
                    violations=(),
                    issues=("TRADING_HALTED",),
                    projected=projected,
                    risk_increasing=True,
                )
            if not policies or not all(
                policy.allow_reduce_only_when_halted for policy in policies
            ):
                return OrderRiskResult(
                    decision=RiskDecision.REJECT,
                    evaluations=(),
                    violations=(),
                    issues=("TRADING_HALTED_REDUCE_ONLY_NOT_ALLOWED",),
                    projected=projected,
                    risk_increasing=False,
                )

        if not policies and projected.risk_increasing:
            return OrderRiskResult(
                decision=RiskDecision.REJECT,
                evaluations=(),
                violations=(),
                issues=("NO_ACTIVE_RISK_POLICY",),
                projected=projected,
                risk_increasing=True,
            )

        risk_order = RiskOrder(
            instrument_id=request.instrument_id,
            side=request.side,
            order_type=request.order_type,
            quantity=request.quantity,
            reference_price=reference_price,
        )
        evaluated_at = self._clock.now()
        evaluations: list[RiskEvaluation] = []
        all_violations: list[RiskViolation] = []

        for policy in policies:
            context = RiskContext(
                current=current,
                projected=projected,
                order=risk_order,
                evaluated_at=evaluated_at,
                scope=policy.scope,
                start_of_day_nav=request.start_of_day_nav,
            )
            violations: list[RiskViolation] = []
            decisions: list[RiskDecision] = []
            for limit in policy.limits:
                violation = limit.evaluate(context)
                if violation is not None:
                    violations.append(violation)
                    decisions.append(limit.decision)

            decision = most_restrictive(*decisions)
            evaluations.append(
                RiskEvaluation(
                    decision=decision,
                    violations=tuple(violations),
                    evaluated_at=evaluated_at,
                    policy_id=policy.id,
                    policy_version=policy.version,
                )
            )
            all_violations.extend(violations)

        final_decision = most_restrictive(*(item.decision for item in evaluations))
        if final_decision is RiskDecision.HALT:
            self._persist_automatic_halt(request)

        return OrderRiskResult(
            decision=final_decision,
            evaluations=tuple(evaluations),
            violations=tuple(all_violations),
            issues=(),
            projected=projected,
            risk_increasing=projected.risk_increasing,
        )

    @staticmethod
    def _resolve_price(request: OrderRiskRequest) -> Price | None:
        if request.order_type is OrderType.LIMIT:
            return request.limit_price
        return request.reference_price

    def _applicable_policies(self, request: OrderRiskRequest) -> tuple[RiskPolicy, ...]:
        result: list[RiskPolicy] = []
        for policy in self._policies.list_active():
            global_match = policy.scope is RiskScope.GLOBAL
            account_match = (
                policy.scope is RiskScope.ACCOUNT
                and policy.scope_id == str(request.account_id)
            )
            strategy_match = (
                policy.scope is RiskScope.STRATEGY
                and request.strategy_id is not None
                and policy.scope_id == request.strategy_id
            )
            instrument_match = (
                policy.scope is RiskScope.INSTRUMENT
                and policy.scope_id == str(request.instrument_id)
            )
            if global_match or account_match or strategy_match or instrument_match:
                result.append(policy)
        return tuple(result)

    def _applicable_halts(self, request: OrderRiskRequest) -> tuple[TradingHalt, ...]:
        result: list[TradingHalt] = []
        for halt in self._halts.list_active():
            global_match = halt.scope is RiskScope.GLOBAL
            account_match = (
                halt.scope is RiskScope.ACCOUNT
                and halt.scope_id == str(request.account_id)
            )
            strategy_match = (
                halt.scope is RiskScope.STRATEGY
                and request.strategy_id is not None
                and halt.scope_id == request.strategy_id
            )
            if global_match or account_match or strategy_match:
                result.append(halt)
        return tuple(result)

    def _persist_automatic_halt(self, request: OrderRiskRequest) -> None:
        scope = RiskScope.ACCOUNT
        scope_id = str(request.account_id)
        if self._halts.get_active(scope, scope_id) is not None:
            return
        self._halts.save(
            TradingHalt(
                id=TradingHaltId.new(),
                scope=scope,
                scope_id=scope_id,
                reason="Risk policy produced HALT.",
                triggered_at=self._clock.now(),
            )
        )

    @staticmethod
    def _input_reject(issue: str) -> OrderRiskResult:
        return OrderRiskResult(
            decision=RiskDecision.REJECT,
            evaluations=(),
            violations=(),
            issues=(issue,),
            projected=None,
            risk_increasing=True,
        )
