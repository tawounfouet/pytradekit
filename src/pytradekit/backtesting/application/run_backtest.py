"""RunBacktest application orchestration."""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from pytradekit import __version__
from pytradekit.backtesting.adapters import HistoricalMarketDataAdapter, SimulatedExecutionAdapter
from pytradekit.backtesting.clock import BacktestClock
from pytradekit.backtesting.domain import (
    BacktestMetrics,
    BacktestReport,
    BacktestRun,
    BacktestRunId,
    BacktestRunStatus,
    CostModel,
    EquityPoint,
    ExecutionModel,
    LatencyModel,
    RunManifest,
    SlippageModel,
    calculate_max_drawdown,
    deterministic_config_hash,
)
from pytradekit.market_data.domain import HistoricalDataset, MarketDataEvent
from pytradekit.orders.adapters import InMemoryOrderRepository
from pytradekit.orders.application import HandleExecutionReport, SubmitOrder, SubmitOrderCommand
from pytradekit.orders.domain import OrderId
from pytradekit.portfolio.adapters import (
    InMemoryBalanceRepository,
    InMemoryPositionRepository,
    InMemoryProcessedFillRegistry,
    OrdersPortfolioEffectAdapter,
)
from pytradekit.portfolio.application import ApplyFillToPortfolio, BuildPortfolioSnapshot
from pytradekit.portfolio.domain import Account, Balance, PortfolioSnapshot
from pytradekit.reference import ContractSpecification
from pytradekit.risk.adapters import (
    InMemoryPortfolioView,
    InMemoryRiskPolicyRepository,
    InMemoryTradingHaltRepository,
    OrdersRiskEvaluationAdapter,
)
from pytradekit.risk.application import EvaluateOrderRisk
from pytradekit.risk.domain import RiskPolicy
from pytradekit.shared import CorrelationId, DomainValidationError, InstrumentId, Money, Price
from pytradekit.strategy.adapters import InMemoryStrategyStateStore
from pytradekit.strategy.application import StrategyRuntime
from pytradekit.strategy.domain import (
    Strategy,
    StrategyProtocol,
    StrategyRun,
    StrategyRunId,
    StrategyRunStatus,
)
from pytradekit.strategy.portfolio_construction import RebalanceService


@dataclass(frozen=True, slots=True, kw_only=True)
class RunBacktestCommand:
    """All explicit inputs required for one reproducible backtest."""

    strategy: Strategy
    implementation: StrategyProtocol
    strategy_config: Mapping[str, object]
    dataset: HistoricalDataset
    events: tuple[MarketDataEvent, ...]
    account: Account
    initial_cash: Money
    risk_policy: RiskPolicy
    contract_specs: Mapping[InstrumentId, ContractSpecification]
    execution_model: ExecutionModel
    cost_model: CostModel
    slippage_model: SlippageModel
    latency_model: LatencyModel
    seed: int = 0


class RunBacktest:
    """Execute Strategy -> Risk -> OMS -> simulated execution -> Portfolio."""

    def execute(self, command: RunBacktestCommand) -> BacktestReport:
        self._validate_command(command)
        manifest = self._manifest(command)
        strategy_run_id = StrategyRunId(
            uuid5(NAMESPACE_URL, f"pytradekit:strategy-run:{manifest.fingerprint}")
        )
        backtest_run_id = BacktestRunId(
            uuid5(NAMESPACE_URL, f"pytradekit:backtest-run:{manifest.fingerprint}")
        )
        clock = BacktestClock(command.dataset.start_time)
        historical = HistoricalMarketDataAdapter(
            dataset=command.dataset,
            events=command.events,
            clock=clock,
        )
        strategy_run = StrategyRun(
            id=strategy_run_id,
            strategy_id=command.strategy.id,
            strategy_version=command.strategy.version,
        )
        strategy_run.start(at=clock.now())
        backtest_run = BacktestRun(
            id=backtest_run_id,
            strategy_run_id=strategy_run_id,
            manifest=manifest,
        )
        backtest_run.start(clock.now())

        orders = InMemoryOrderRepository()
        positions = InMemoryPositionRepository()
        balances = InMemoryBalanceRepository()
        processed_fills = InMemoryProcessedFillRegistry()
        balances.save(
            Balance(
                account_id=command.account.id,
                currency=command.initial_cash.currency,
                cash=command.initial_cash,
                updated_at=clock.now(),
            )
        )
        apply_fill = ApplyFillToPortfolio(
            positions=positions,
            balances=balances,
            processed_fills=processed_fills,
        )
        portfolio_effects = OrdersPortfolioEffectAdapter(apply_fill)
        snapshot_builder = BuildPortfolioSnapshot(
            positions=positions,
            balances=balances,
            clock=clock,
        )

        risk_portfolio = InMemoryPortfolioView()
        policies = InMemoryRiskPolicyRepository()
        policies.save(command.risk_policy)
        risk_service = EvaluateOrderRisk(
            policies=policies,
            halts=InMemoryTradingHaltRepository(),
            portfolio=risk_portfolio,
            clock=clock,
        )
        risk_adapter = OrdersRiskEvaluationAdapter(risk_service)
        simulated = SimulatedExecutionAdapter(
            execution_model=command.execution_model,
            cost_model=command.cost_model,
            slippage_model=command.slippage_model,
            latency_model=command.latency_model,
        )
        submit_order = SubmitOrder(
            repository=orders,
            execution=simulated,
            clock=clock,
            risk=risk_adapter,
        )
        handle_report = HandleExecutionReport(
            repository=orders,
            portfolio_effects=portfolio_effects,
        )
        state_store = InMemoryStrategyStateStore()
        strategy_runtime = StrategyRuntime(
            implementation=command.implementation,
            run=strategy_run,
            state_store=state_store,
            clock=clock,
        )
        rebalance = RebalanceService()

        latest_prices: dict[InstrumentId, Price] = {}
        initial_snapshot = snapshot_builder.execute(command.account, prices=latest_prices)
        initial_nav = initial_snapshot.nav
        equity: list[EquityPoint] = []
        order_count = 0
        fill_count = 0
        risk_rejections = 0
        warmup_counts: dict[InstrumentId, int] = {
            instrument_id: 0 for instrument_id in command.strategy.requirements.instruments
        }

        try:
            for event in historical.iter_events(
                instruments=command.strategy.requirements.instruments
            ):
                latest_prices[event.instrument_id] = event.bar.close
                if event.instrument_id in warmup_counts:
                    warmup_counts[event.instrument_id] += 1

                for report in simulated.on_market_event(event):
                    handle_report.execute(report, account_id=command.account.id)
                    fill_count += 1

                snapshot = snapshot_builder.execute(command.account, prices=latest_prices)
                risk_portfolio.set_snapshot(snapshot)
                trading_enabled = all(
                    count > command.strategy.requirements.warmup_bars
                    for count in warmup_counts.values()
                )
                decision = strategy_runtime.process_market_event(
                    event,
                    portfolio=snapshot,
                    trading_enabled=trading_enabled,
                )

                for target in decision.targets:
                    try:
                        reference_price = latest_prices[target.instrument_id]
                        contract = command.contract_specs[target.instrument_id]
                    except KeyError as exc:
                        raise DomainValidationError(
                            "Target requires an available reference price "
                            "and ContractSpecification."
                        ) from exc
                    intents = rebalance.build(
                        target,
                        portfolio=snapshot,
                        reference_price=reference_price,
                        contract=contract,
                    )
                    for intent in intents:
                        order_count += 1
                        order_uuid = uuid5(
                            NAMESPACE_URL,
                            f"pytradekit:{manifest.fingerprint}:order:{order_count}",
                        )
                        correlation_uuid = uuid5(
                            NAMESPACE_URL,
                            f"pytradekit:{manifest.fingerprint}:correlation:{order_count}",
                        )
                        result = submit_order.execute(
                            SubmitOrderCommand(
                                order_id=OrderId(order_uuid),
                                instrument_id=intent.instrument_id,
                                side=intent.side,
                                order_type=intent.order_type,
                                quantity=intent.quantity,
                                time_in_force=intent.time_in_force,
                                limit_price=intent.limit_price,
                                correlation_id=CorrelationId(correlation_uuid),
                                account_id=command.account.id,
                                reference_price=reference_price,
                                strategy_id=str(command.strategy.id),
                                start_of_day_nav=initial_nav,
                            )
                        )
                        if result.submission_status is None:
                            risk_rejections += 1

                snapshot = snapshot_builder.execute(command.account, prices=latest_prices)
                risk_portfolio.set_snapshot(snapshot)
                equity.append(
                    EquityPoint(
                        timestamp=clock.now(),
                        nav=snapshot.nav,
                        gross_exposure=snapshot.gross_exposure,
                        net_exposure=snapshot.net_exposure,
                    )
                )

            strategy_run.stop(at=clock.now())
            final_snapshot = snapshot_builder.execute(command.account, prices=latest_prices)
            absolute_pnl = final_snapshot.nav - initial_nav
            total_return = (
                absolute_pnl.amount / initial_nav.amount
                if initial_nav.amount != Decimal("0")
                else Decimal("0")
            )
            metrics = BacktestMetrics(
                total_return=total_return,
                absolute_pnl=absolute_pnl,
                max_drawdown=calculate_max_drawdown(tuple(equity)),
                number_of_orders=order_count,
                number_of_fills=fill_count,
                risk_rejections=risk_rejections,
            )
            backtest_run.complete(clock.now(), metrics)
            return BacktestReport(
                run_id=backtest_run.id,
                manifest=manifest,
                started_at=manifest.started_at,
                completed_at=clock.now(),
                initial_nav=initial_nav,
                final_snapshot=final_snapshot,
                metrics=metrics,
                equity_curve=tuple(equity),
            )
        except Exception:
            if strategy_run.status not in {
                StrategyRunStatus.STOPPED,
                StrategyRunStatus.CANCELLED,
                StrategyRunStatus.FAILED,
            }:
                strategy_run.fail(at=clock.now())
            if backtest_run.status is BacktestRunStatus.RUNNING:
                backtest_run.fail(clock.now())
            raise

    @staticmethod
    def _validate_command(command: RunBacktestCommand) -> None:
        if command.initial_cash.amount <= 0:
            raise DomainValidationError("Backtest initial_cash must be greater than zero.")
        if command.initial_cash.currency != command.account.base_currency:
            raise DomainValidationError("Backtest initial_cash must use account base currency.")
        required = set(command.strategy.requirements.instruments)
        if not required.issubset(set(command.dataset.instruments)):
            raise DomainValidationError(
                "Dataset does not contain every required strategy instrument."
            )
        if command.strategy.requirements.bar_intervals and command.dataset.interval not in set(
            command.strategy.requirements.bar_intervals
        ):
            raise DomainValidationError("Dataset interval does not satisfy strategy requirements.")
        supported = {"market", "limit"}
        if any(
            item.value not in supported
            for item in command.strategy.requirements.required_order_types
        ):
            raise DomainValidationError("Strategy requires an unsupported simulated order type.")
        if any(item not in command.contract_specs for item in required):
            raise DomainValidationError("Missing ContractSpecification for required instrument.")

    @staticmethod
    def _manifest(command: RunBacktestCommand) -> RunManifest:
        return RunManifest(
            pytradekit_version=__version__,
            strategy_id=str(command.strategy.id),
            strategy_version=str(command.strategy.version),
            strategy_config_hash=deterministic_config_hash(command.strategy_config),
            dataset_id=command.dataset.dataset_id,
            dataset_version=command.dataset.version,
            dataset_checksum=command.dataset.checksum,
            risk_policy_id=str(command.risk_policy.id),
            risk_policy_version=command.risk_policy.version,
            execution_model=f"{command.execution_model.name}:{command.execution_model.version}",
            cost_model=f"{command.cost_model.name}:{command.cost_model.version}",
            slippage_model=f"{command.slippage_model.name}:{command.slippage_model.version}",
            latency_model=f"{command.latency_model.name}:{command.latency_model.version}",
            random_seed=command.seed,
            runtime_profile="BACKTEST",
            started_at=command.dataset.start_time,
        )
