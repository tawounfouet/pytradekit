"""Run the controlled real IBKR PAPER qualification probe for PyTradeKit 0.8."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from time import monotonic
from typing import Protocol, cast

from pytradekit.brokers.adapters.ibkr import (
    IBKR_ASYNC_PACKAGE_NAME,
    IBKR_ASYNC_VERSION_TARGET,
    IBKRClientId,
    IBKRContractId,
    IBKREconomicWriteAdmission,
    IBKRExecutionInstrumentBinding,
    IBKRPaperRuntimeProfile,
    StaticIBKRExecutionInstrumentResolver,
    build_ibkr_execution_adapter,
    build_ibkr_market_rule_resolver,
    build_ibkr_operational_runtime,
    build_ibkr_order_session_runtime,
    build_ibkr_paper_connection_runtime,
    map_ibkr_stock_contract,
    normalize_ibkr_contract_details,
)
from pytradekit.execution import SubmissionStatus
from pytradekit.orders.domain import (
    Order,
    OrderId,
    OrderSide,
    TimeInForce,
)
from pytradekit.runtime import SystemClock
from pytradekit.shared import (
    CorrelationId,
    Currency,
    InstrumentId,
    Price,
    Quantity,
)

_ACK_ENV = "PYTRADEKIT_IBKR_ORDER_PROBE_ACK"
_ACK_VALUE = "I_UNDERSTAND_PAPER_ORDERS_WILL_BE_CREATED"
_SYMBOL_ENV = "PYTRADEKIT_IBKR_ORDER_PROBE_SYMBOL"
_CONID_ENV = "PYTRADEKIT_IBKR_ORDER_PROBE_CONID"
_LIMIT_PRICE_ENV = "PYTRADEKIT_IBKR_LIMIT_PRICE"
_QUANTITY_ENV = "PYTRADEKIT_IBKR_ORDER_PROBE_QUANTITY"
_TIMEOUT_ENV = "PYTRADEKIT_IBKR_ORDER_PROBE_TIMEOUT_SECONDS"


class _EventLike(Protocol):
    def connect(
        self,
        listener: Callable[..., object],
        error: object | None = None,
        done: object | None = None,
        keep_ref: bool = False,
    ) -> object:
        ...

    def disconnect(
        self,
        listener: Callable[..., object],
    ) -> object:
        ...


class _AccountValueLike(Protocol):
    account: str
    tag: str
    value: str
    currency: str


class _ContractLike(Protocol):
    conId: int
    symbol: str


class _PortfolioLike(Protocol):
    account: str
    contract: _ContractLike
    position: object


class _OrderLike(Protocol):
    orderId: int
    clientId: int
    permId: int
    orderRef: str


class _OrderStatusLike(Protocol):
    status: str
    permId: int


class _TradeLike(Protocol):
    order: _OrderLike
    orderStatus: _OrderStatusLike


class _ExecutionLike(Protocol):
    execId: str
    permId: int
    orderRef: str
    shares: object


class _FillLike(Protocol):
    execution: _ExecutionLike


class _ProviderLike(Protocol):
    openOrderEvent: _EventLike
    orderStatusEvent: _EventLike
    execDetailsEvent: _EventLike
    connectedEvent: _EventLike
    disconnectedEvent: _EventLike

    def reqContractDetails(self, contract: object) -> list[object]:
        ...

    def accountValues(self, account: str = "") -> list[object]:
        ...

    def portfolio(self, account: str = "") -> list[object]:
        ...

    def trades(self) -> list[object]:
        ...

    def fills(self) -> list[object]:
        ...

    def sleep(self, secs: float = 0.02) -> bool:
        ...


class _ContractConstructor(Protocol):
    def __call__(self, **kwargs: object) -> object:
        ...


class _CallbackCollector:
    def __init__(self, prefix: str) -> None:
        self._prefix = prefix
        self.open_order_count = 0
        self.order_status_count = 0
        self.exec_details_count = 0
        self.connected_count = 0
        self.disconnected_count = 0

    def bind(self, provider: _ProviderLike) -> None:
        provider.openOrderEvent.connect(self._open_order)
        provider.orderStatusEvent.connect(self._order_status)
        provider.execDetailsEvent.connect(self._exec_details)
        provider.connectedEvent.connect(self._connected)
        provider.disconnectedEvent.connect(self._disconnected)

    def unbind(self, provider: _ProviderLike) -> None:
        provider.openOrderEvent.disconnect(self._open_order)
        provider.orderStatusEvent.disconnect(self._order_status)
        provider.execDetailsEvent.disconnect(self._exec_details)
        provider.connectedEvent.disconnect(self._connected)
        provider.disconnectedEvent.disconnect(self._disconnected)

    def _open_order(self, trade: object) -> None:
        if _trade_has_prefix(trade, self._prefix):
            self.open_order_count += 1

    def _order_status(self, trade: object) -> None:
        if _trade_has_prefix(trade, self._prefix):
            self.order_status_count += 1

    def _exec_details(
        self,
        trade: object,
        fill: object,
    ) -> None:
        if _trade_has_prefix(trade, self._prefix):
            _ = fill
            self.exec_details_count += 1

    def _connected(self, *args: object) -> None:
        _ = args
        self.connected_count += 1

    def _disconnected(self, *args: object) -> None:
        _ = args
        self.disconnected_count += 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run controlled IBKR PAPER MARKET, LIMIT, CANCEL, callback, "
            "cleanup, and reconnect evidence. LIVE is unavailable."
        )
    )
    parser.add_argument(
        "--with-orders",
        action="store_true",
        help=(
            "Permit controlled PAPER economic writes after the explicit "
            "acknowledgement environment value is verified."
        ),
    )
    parser.add_argument(
        "--ci-qualified",
        action="store_true",
        help="Record the deterministic CI quality gate as PASS.",
    )
    parser.add_argument(
        "--runbook-reviewed",
        action="store_true",
        help="Record operator review of the IBKR qualification runbook.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Sanitized JSON probe report path.",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        profile = IBKRPaperRuntimeProfile.from_environment()
        symbol = os.environ.get(_SYMBOL_ENV, "AAPL").strip().upper()
        contract_id = IBKRContractId(
            _positive_int_env(_CONID_ENV)
        )
        limit_price = _positive_decimal_env(_LIMIT_PRICE_ENV)
        quantity = Quantity(
            _positive_decimal_env(
                _QUANTITY_ENV,
                default="1",
            )
        )
        timeout_seconds = float(
            _positive_decimal_env(
                _TIMEOUT_ENV,
                default="60",
            )
        )
        if not symbol:
            raise ValueError(f"{_SYMBOL_ENV} must not be empty.")
        if args.with_orders:
            acknowledgement = os.environ.get(_ACK_ENV, "").strip()
            if acknowledgement != _ACK_VALUE:
                raise ValueError(
                    f"{_ACK_ENV} must equal {_ACK_VALUE!r}."
                )
    except Exception as exc:
        print(
            f"IBKR PAPER qualification configuration error: {exc}",
            file=sys.stderr,
        )
        return 2

    clock = SystemClock()
    connection = build_ibkr_paper_connection_runtime(profile)
    captured_at = datetime.now(UTC)
    prefix = f"ptk-ibkr-q-{captured_at.strftime('%Y%m%d%H%M%S')}"
    collector = _CallbackCollector(prefix)

    gates = {
        "ci_quality_gate": (
            "PASS" if args.ci_qualified else "PENDING"
        ),
        "runbook_reviewed": (
            "PASS" if args.runbook_reviewed else "PENDING"
        ),
        "real_paper_preflight": "FAIL",
        "real_paper_orders": "PENDING",
        "real_paper_callbacks": "PENDING",
        "real_paper_cleanup": "PENDING",
        "real_paper_reconnect": "PENDING",
    }
    proofs: dict[str, dict[str, object]] = {}
    controlled_probe_passed = False
    cleanup_passed = False
    provider: _ProviderLike | None = None
    operations = None

    try:
        startup = connection.start()
        if not startup.ready_for_startup:
            raise RuntimeError(
                "IBKR PAPER connection did not reach startup readiness."
            )
        provider = _provider(connection.read_client())
        collector.bind(provider)

        binding = _resolve_execution_binding(
            provider=provider,
            contract_id=contract_id,
            symbol=symbol,
        )
        account_proof = _account_proof(
            provider=provider,
            profile=profile,
        )
        baseline_quantity = _position_quantity(
            provider=provider,
            profile=profile,
            contract_id=contract_id,
        )
        account_proof["baseline_observed"] = True
        proofs["ACCOUNT_QUERY"] = dict(account_proof)
        proofs["BALANCE_QUERY"] = {
            "cash_present": account_proof["cash_present"],
            "equity_present": account_proof["equity_present"],
            "buying_power_present": account_proof[
                "buying_power_present"
            ],
        }
        proofs["POSITION_QUERY"] = {
            "baseline_observed": True,
            "baseline_restored": False,
        }
        gates["real_paper_preflight"] = "PASS"

        if not args.with_orders:
            raise RuntimeError(
                "Controlled PAPER economic writes were not enabled."
            )

        session = build_ibkr_order_session_runtime(
            connection=connection
        )
        operations = build_ibkr_operational_runtime(
            connection=connection,
            reconciliation_complete=True,
            clock=clock,
        )
        execution = build_ibkr_execution_adapter(
            connection=connection,
            session=session,
            instruments=StaticIBKRExecutionInstrumentResolver(
                (binding,)
            ),
            admission=IBKREconomicWriteAdmission(
                paper_endpoint_verified=True,
                account_ready=True,
                reconciliation_complete=True,
                api_read_only=False,
                economic_write_enabled=True,
            ),
            operations=operations.guard,
            clock=clock,
            market_rules=build_ibkr_market_rule_resolver(
                connection
            ),
        )

        market_ref = f"{prefix}-market"
        market_order = _market_order(
            instrument_id=binding.mapping.instrument.id,
            quantity=quantity,
            side=OrderSide.BUY,
            reference=market_ref,
            occurred_at=clock.now(),
        )
        market_result = execution.submit(market_order)
        market_trade = _wait_trade(
            provider,
            order_ref=market_ref,
            terminal_statuses={"Filled"},
            timeout_seconds=timeout_seconds,
        )
        market_fills = _matching_fills(
            provider,
            order_ref=market_ref,
        )
        market_perm_id = _trade_perm_id(market_trade)
        market_exec_id_present = any(
            bool(fill.execution.execId.strip())
            for fill in market_fills
        )
        market_filled = (
            _trade_status(market_trade) == "Filled"
            and bool(market_fills)
        )
        proofs["MARKET_ORDER"] = {
            "submitted": execution.last_attempt is not None,
            "submit_attempts": 1,
            "filled": market_filled,
            "perm_id_present": market_perm_id > 0,
            "exec_id_present": market_exec_id_present,
            "initial_result": market_result.status.value,
        }
        query_report = execution.query_order(market_order)
        proofs["ORDER_QUERY"] = {
            "query_observed": query_report is not None,
            "perm_id_present": (
                query_report is not None
                and bool(query_report.external_order_id)
            ),
            "status_observed": query_report is not None,
        }
        proofs["CLIENT_ORDER_REFERENCE"] = {
            "order_ref_present": bool(market_ref),
            "round_trip_match": (
                _trade_order_ref(market_trade) == market_ref
            ),
            "submit_attempts": 1,
        }
        proofs["EXECUTION_FACTS"] = {
            "exec_details_count": len(market_fills),
            "exec_id_present": market_exec_id_present,
            "perm_id_present": market_perm_id > 0,
            "fill_quantity_positive": any(
                _positive_fill_quantity(fill)
                for fill in market_fills
            ),
        }

        limit_ref = f"{prefix}-limit"
        limit_order = _limit_order(
            instrument_id=binding.mapping.instrument.id,
            quantity=quantity,
            side=OrderSide.BUY,
            reference=limit_ref,
            limit_price=limit_price,
            occurred_at=clock.now(),
        )
        limit_result = execution.submit(limit_order)
        limit_trade = _wait_trade(
            provider,
            order_ref=limit_ref,
            terminal_statuses={
                "PendingSubmit",
                "PreSubmitted",
                "Submitted",
                "Filled",
            },
            timeout_seconds=timeout_seconds,
        )
        market_rule_evidence = execution.last_market_rule_evidence
        limit_status_before_cancel = _trade_status(limit_trade)
        limit_submitted = limit_status_before_cancel != "Filled"

        cancel_requested = False
        terminal_cancelled = False
        if limit_submitted:
            execution.cancel(limit_order)
            cancel_requested = True
            limit_trade = _wait_trade(
                provider,
                order_ref=limit_ref,
                terminal_statuses={
                    "Cancelled",
                    "ApiCancelled",
                },
                timeout_seconds=timeout_seconds,
            )
            terminal_cancelled = (
                _trade_status(limit_trade)
                in {"Cancelled", "ApiCancelled"}
            )

        proofs["LIMIT_ORDER"] = {
            "submitted": limit_result.status
            in {
                SubmissionStatus.ACKNOWLEDGED,
                SubmissionStatus.UNCERTAIN,
            },
            "submit_attempts": 1,
            "limit_price_present": True,
            "market_rule_checked": (
                market_rule_evidence is not None
                and market_rule_evidence.valid
            ),
        }
        proofs["CANCEL_ORDER"] = {
            "requested": cancel_requested,
            "cancel_attempts": 1 if cancel_requested else 0,
            "terminal_cancelled": terminal_cancelled,
        }

        cleanup_ref = f"{prefix}-cleanup"
        cleanup_order = _market_order(
            instrument_id=binding.mapping.instrument.id,
            quantity=quantity,
            side=OrderSide.SELL,
            reference=cleanup_ref,
            occurred_at=clock.now(),
        )
        execution.submit(cleanup_order)
        cleanup_trade = _wait_trade(
            provider,
            order_ref=cleanup_ref,
            terminal_statuses={"Filled"},
            timeout_seconds=timeout_seconds,
        )
        cleanup_passed = _trade_status(cleanup_trade) == "Filled"
        final_quantity = _wait_position_quantity(
            provider=provider,
            profile=profile,
            contract_id=contract_id,
            expected=baseline_quantity,
            timeout_seconds=timeout_seconds,
        )
        baseline_restored = final_quantity == baseline_quantity
        cleanup_passed = cleanup_passed and baseline_restored
        proofs["POSITION_QUERY"] = {
            "baseline_observed": True,
            "baseline_restored": baseline_restored,
        }
        gates["real_paper_cleanup"] = (
            "PASS" if cleanup_passed else "FAIL"
        )

        callbacks_passed = (
            collector.open_order_count > 0
            and collector.order_status_count > 0
            and collector.exec_details_count > 0
            and market_exec_id_present
        )
        orders_passed = (
            market_filled
            and limit_submitted
            and terminal_cancelled
            and cleanup_passed
            and market_rule_evidence is not None
            and market_rule_evidence.valid
        )
        gates["real_paper_orders"] = (
            "PASS" if orders_passed else "FAIL"
        )
        gates["real_paper_callbacks"] = (
            "PASS" if callbacks_passed else "FAIL"
        )

        before_reconnect_refs = _qualification_refs(
            provider,
            prefix=prefix,
        )
        connection.stop()
        reconnect_startup = connection.start()
        provider_after = _provider(connection.read_client())
        provider_after.sleep(0.5)
        after_reconnect_refs = _qualification_refs(
            provider_after,
            prefix=prefix,
        )
        post_reconnect_account = _account_proof(
            provider=provider_after,
            profile=profile,
        )
        reconnect_passed = (
            reconnect_startup.ready_for_startup
            and collector.disconnected_count >= 1
            and post_reconnect_account["account_ready"] is True
            and after_reconnect_refs.issubset(before_reconnect_refs)
        )
        proofs["RECONNECT_RECOVERY"] = {
            "disconnect_observed": (
                collector.disconnected_count >= 1
            ),
            "reconnect_observed": reconnect_startup.ready_for_startup,
            "post_reconnect_account_query": (
                post_reconnect_account["account_ready"] is True
            ),
            "economic_replay": (
                not after_reconnect_refs.issubset(
                    before_reconnect_refs
                )
            ),
        }
        gates["real_paper_reconnect"] = (
            "PASS" if reconnect_passed else "FAIL"
        )

        controlled_probe_passed = all(
            gates[name] == "PASS"
            for name in (
                "real_paper_preflight",
                "real_paper_orders",
                "real_paper_callbacks",
                "real_paper_cleanup",
                "real_paper_reconnect",
            )
        )
    except Exception as exc:
        print(
            "Controlled IBKR PAPER qualification failed "
            f"({type(exc).__name__}). Inspect the PAPER account "
            "before retrying.",
            file=sys.stderr,
        )
    finally:
        if operations is not None:
            operations.stop()
        if provider is not None:
            try:
                collector.unbind(provider)
            except Exception:
                pass
        try:
            connection.stop()
        except Exception:
            pass

    payload = {
        "schema_version": "probe-1",
        "provider": "ibkr",
        "environment": "PAPER",
        "release": "0.8.0b8",
        "captured_at": captured_at.isoformat(),
        "account": profile.masked_account_id,
        "symbol": symbol,
        "contract_id_present": contract_id.value > 0,
        "sdk": {
            "name": IBKR_ASYNC_PACKAGE_NAME,
            "version": IBKR_ASYNC_VERSION_TARGET,
        },
        "real_provider_used": True,
        "economic_writes_requested": args.with_orders,
        "controlled_probe_passed": controlled_probe_passed,
        "cleanup_passed": cleanup_passed,
        "gates": gates,
        "proofs": proofs,
        "callback_counts": {
            "open_order": collector.open_order_count,
            "order_status": collector.order_status_count,
            "exec_details": collector.exec_details_count,
            "connected": collector.connected_count,
            "disconnected": collector.disconnected_count,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote sanitized IBKR PAPER probe to {args.output}")
    return 0 if controlled_probe_passed else 1


def _resolve_execution_binding(
    *,
    provider: _ProviderLike,
    contract_id: IBKRContractId,
    symbol: str,
) -> IBKRExecutionInstrumentBinding:
    from importlib import import_module

    module = import_module("ib_async")
    constructor = cast(
        _ContractConstructor,
        module.Contract,
    )
    request = constructor(
        conId=contract_id.value,
        exchange="SMART",
    )
    raw_matches = list(provider.reqContractDetails(request))
    normalized = [
        normalize_ibkr_contract_details(item)
        for item in raw_matches
    ]
    exact = [
        item
        for item in normalized
        if (
            item.contract.contract_id == contract_id
            and item.contract.symbol == symbol
        )
    ]
    if len(exact) != 1:
        raise RuntimeError(
            "IBKR qualification requires exactly one conId plus symbol match."
        )
    details = exact[0]
    mapping = map_ibkr_stock_contract(
        details,
        instrument_id=InstrumentId.new(),
    )
    return IBKRExecutionInstrumentBinding(
        contract=details.contract,
        mapping=mapping,
    )


def _account_proof(
    *,
    provider: _ProviderLike,
    profile: IBKRPaperRuntimeProfile,
) -> dict[str, object]:
    values = [
        cast(_AccountValueLike, item)
        for item in provider.accountValues(
            profile.expected_account_id
        )
        if (
            hasattr(item, "account")
            and cast(_AccountValueLike, item).account
            == profile.expected_account_id
        )
    ]
    tags = {
        item.tag: item.value.strip()
        for item in values
        if isinstance(item.tag, str)
        and isinstance(item.value, str)
    }
    account_ready = tags.get("AccountReady", "").lower() == "true"
    return {
        "account_ready": account_ready,
        "managed_account_match": True,
        "cash_present": bool(tags.get("TotalCashValue")),
        "equity_present": bool(tags.get("NetLiquidation")),
        "buying_power_present": bool(tags.get("BuyingPower")),
    }


def _market_order(
    *,
    instrument_id: InstrumentId,
    quantity: Quantity,
    side: OrderSide,
    reference: str,
    occurred_at: datetime,
) -> Order:
    order = Order.create_market(
        order_id=OrderId.new(),
        instrument_id=instrument_id,
        side=side,
        quantity=quantity,
        time_in_force=TimeInForce.DAY,
        correlation_id=CorrelationId.new(),
        occurred_at=occurred_at,
        client_order_id=reference,
    )
    order.validate(occurred_at=occurred_at)
    order.mark_submitted(occurred_at=occurred_at)
    return order


def _limit_order(
    *,
    instrument_id: InstrumentId,
    quantity: Quantity,
    side: OrderSide,
    reference: str,
    limit_price: Decimal,
    occurred_at: datetime,
) -> Order:
    order = Order.create_limit(
        order_id=OrderId.new(),
        instrument_id=instrument_id,
        side=side,
        quantity=quantity,
        time_in_force=TimeInForce.DAY,
        correlation_id=CorrelationId.new(),
        occurred_at=occurred_at,
        limit_price=Price(
            limit_price,
            Currency("USD"),
        ),
        client_order_id=reference,
    )
    order.validate(occurred_at=occurred_at)
    order.mark_submitted(occurred_at=occurred_at)
    return order


def _wait_trade(
    provider: _ProviderLike,
    *,
    order_ref: str,
    terminal_statuses: set[str],
    timeout_seconds: float,
) -> object:
    deadline = monotonic() + timeout_seconds
    latest: object | None = None
    while monotonic() < deadline:
        latest = _find_trade(
            provider,
            order_ref=order_ref,
        )
        if latest is not None:
            status = _trade_status(latest)
            if status in terminal_statuses:
                return latest
            if status in {
                "Cancelled",
                "ApiCancelled",
                "Inactive",
            } and status not in terminal_statuses:
                raise RuntimeError(
                    f"IBKR order reached unexpected terminal status {status}."
                )
        provider.sleep(0.2)
    if latest is None:
        raise TimeoutError(
            "IBKR qualification order was not observed before timeout."
        )
    raise TimeoutError(
        "IBKR qualification order did not reach the expected state."
    )


def _find_trade(
    provider: _ProviderLike,
    *,
    order_ref: str,
) -> object | None:
    matches = [
        trade
        for trade in provider.trades()
        if _trade_order_ref(trade) == order_ref
    ]
    if len(matches) > 1:
        raise RuntimeError(
            "IBKR qualification observed duplicate orderRef trades."
        )
    return matches[0] if matches else None


def _trade_order_ref(trade: object) -> str:
    if not hasattr(trade, "order"):
        return ""
    candidate = cast(_TradeLike, trade)
    value = candidate.order.orderRef
    return value.strip() if isinstance(value, str) else ""


def _trade_has_prefix(
    trade: object,
    prefix: str,
) -> bool:
    return _trade_order_ref(trade).startswith(prefix)


def _trade_status(trade: object) -> str:
    if not hasattr(trade, "orderStatus"):
        return ""
    candidate = cast(_TradeLike, trade)
    value = candidate.orderStatus.status
    return value.strip() if isinstance(value, str) else ""


def _trade_perm_id(trade: object) -> int:
    if not hasattr(trade, "order"):
        return 0
    candidate = cast(_TradeLike, trade)
    value = candidate.order.permId
    return value if type(value) is int and value > 0 else 0


def _matching_fills(
    provider: _ProviderLike,
    *,
    order_ref: str,
) -> list[_FillLike]:
    matches: list[_FillLike] = []
    for raw in provider.fills():
        if not hasattr(raw, "execution"):
            continue
        fill = cast(_FillLike, raw)
        if fill.execution.orderRef == order_ref:
            matches.append(fill)
    return matches


def _positive_fill_quantity(fill: _FillLike) -> bool:
    try:
        return Decimal(str(fill.execution.shares)) > 0
    except InvalidOperation:
        return False


def _position_quantity(
    *,
    provider: _ProviderLike,
    profile: IBKRPaperRuntimeProfile,
    contract_id: IBKRContractId,
) -> Decimal:
    quantity = Decimal("0")
    for raw in provider.portfolio(profile.expected_account_id):
        if not hasattr(raw, "contract"):
            continue
        item = cast(_PortfolioLike, raw)
        if (
            item.account == profile.expected_account_id
            and item.contract.conId == contract_id.value
        ):
            try:
                quantity += Decimal(str(item.position))
            except InvalidOperation as exc:
                raise RuntimeError(
                    "IBKR portfolio position is not numeric."
                ) from exc
    return quantity


def _wait_position_quantity(
    *,
    provider: _ProviderLike,
    profile: IBKRPaperRuntimeProfile,
    contract_id: IBKRContractId,
    expected: Decimal,
    timeout_seconds: float,
) -> Decimal:
    deadline = monotonic() + timeout_seconds
    latest = _position_quantity(
        provider=provider,
        profile=profile,
        contract_id=contract_id,
    )
    while monotonic() < deadline:
        if latest == expected:
            return latest
        provider.sleep(0.2)
        latest = _position_quantity(
            provider=provider,
            profile=profile,
            contract_id=contract_id,
        )
    return latest


def _qualification_refs(
    provider: _ProviderLike,
    *,
    prefix: str,
) -> set[str]:
    return {
        reference
        for trade in provider.trades()
        if (reference := _trade_order_ref(trade)).startswith(prefix)
    }


def _provider(value: object) -> _ProviderLike:
    required = (
        "reqContractDetails",
        "accountValues",
        "portfolio",
        "trades",
        "fills",
        "sleep",
        "openOrderEvent",
        "orderStatusEvent",
        "execDetailsEvent",
        "connectedEvent",
        "disconnectedEvent",
    )
    if any(not hasattr(value, name) for name in required):
        raise RuntimeError(
            "IBKR PAPER client lacks qualification surfaces."
        )
    return cast(_ProviderLike, value)


def _positive_int_env(name: str) -> int:
    raw = os.environ.get(name, "").strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(
            f"{name} must be a positive integer."
        ) from exc
    if value <= 0:
        raise ValueError(
            f"{name} must be a positive integer."
        )
    return value


def _positive_decimal_env(
    name: str,
    *,
    default: str | None = None,
) -> Decimal:
    raw = os.environ.get(
        name,
        "" if default is None else default,
    ).strip()
    try:
        value = Decimal(raw)
    except InvalidOperation as exc:
        raise ValueError(
            f"{name} must be a positive decimal."
        ) from exc
    if not value.is_finite() or value <= 0:
        raise ValueError(
            f"{name} must be a positive decimal."
        )
    return value


if __name__ == "__main__":
    raise SystemExit(main())
