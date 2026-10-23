"""Run a controlled real IBKR PAPER qualification probe.

This command can create simulated PAPER orders when --with-orders is supplied.
There is no LIVE mode. The explicit acknowledgement environment variable is
required before any economic write.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from importlib import import_module
from pathlib import Path
from typing import Protocol, cast
from uuid import uuid4

from pytradekit.brokers.adapters.ibkr import (
    IBKRContractDetailsRecord,
    IBKRMarketRuleClient,
    IBKRMarketRuleResolver,
    IBKRPaperEvidenceBundle,
    IBKRPaperRuntimeProfile,
    IBKRPriceIncrementMode,
    build_ibkr_paper_connection_runtime,
    canonical_ibkr_evidence_sha256,
    map_ibkr_stock_contract,
    normalize_ibkr_contract_details,
)
from pytradekit.brokers.compliance import BrokerCapability
from pytradekit.shared import InstrumentId

_ACK_ENV = "PYTRADEKIT_IBKR_ORDER_PROBE_ACK"
_ACK_VALUE = "I_UNDERSTAND_IBKR_PAPER_ORDERS_WILL_BE_CREATED"

_TERMINAL_STATUSES = {
    "Filled",
    "Cancelled",
    "ApiCancelled",
    "Inactive",
}


class _Constructor(Protocol):
    def __call__(self, **kwargs: object) -> object:
        ...


class _LowLevelClient(Protocol):
    def getReqId(self) -> int:
        ...


class _ProbeClient(Protocol):
    client: _LowLevelClient

    def reqContractDetails(self, contract: object) -> list[object]:
        ...

    def reqMarketRule(self, marketRuleId: int) -> object:
        ...

    def accountValues(self, account: str = "") -> list[object]:
        ...

    def portfolio(self, account: str = "") -> list[object]:
        ...

    def trades(self) -> list[object]:
        ...

    def fills(self) -> list[object]:
        ...

    def placeOrder(self, contract: object, order: object) -> object:
        ...

    def cancelOrder(
        self,
        order: object,
        manualCancelOrderTime: str = "",
    ) -> object | None:
        ...

    def sleep(self, secs: float) -> bool:
        ...


class _ContractDetailsLike(Protocol):
    contract: object


class _TradeLike(Protocol):
    order: object
    orderStatus: object
    fills: list[object]

    def isDone(self) -> bool:
        ...


class _OrderLike(Protocol):
    orderId: int
    clientId: int
    permId: int
    orderRef: str
    account: str


class _OrderStatusLike(Protocol):
    status: str
    filled: object
    remaining: object
    permId: int
    clientId: int


class _PortfolioLike(Protocol):
    contract: object
    position: object


class _ContractLike(Protocol):
    conId: int
    symbol: str


class _AccountValueLike(Protocol):
    account: str
    tag: str
    value: str
    currency: str


class _FillLike(Protocol):
    execution: object


class _ExecutionLike(Protocol):
    execId: str
    permId: int
    orderId: int
    clientId: int
    orderRef: str
    shares: object
    price: object
    cumQty: object


@dataclass(frozen=True, slots=True)
class ProbeConfig:
    commit_sha: str
    contract_id: int
    symbol: str
    market_qty: Decimal
    limit_qty: Decimal
    limit_price: Decimal | None
    timeout_seconds: float
    poll_seconds: float
    with_orders: bool
    ci_qualified: bool

    def __post_init__(self) -> None:
        if not self.commit_sha.strip():
            raise ValueError("commit_sha must be non-empty.")
        if type(self.contract_id) is not int or self.contract_id <= 0:
            raise ValueError("contract_id must be a positive int.")
        if not self.symbol.strip():
            raise ValueError("symbol must be non-empty.")
        for field_name in ("market_qty", "limit_qty"):
            value = getattr(self, field_name)
            if (
                not isinstance(value, Decimal)
                or not value.is_finite()
                or value <= 0
                or value != value.to_integral_value()
            ):
                raise ValueError(
                    f"{field_name} must be a positive whole-share Decimal."
                )
        if self.with_orders:
            if self.limit_price is None:
                raise ValueError("--limit-price is required with --with-orders.")
            if (
                not self.limit_price.is_finite()
                or self.limit_price <= 0
            ):
                raise ValueError("limit_price must be a positive Decimal.")
        if self.timeout_seconds <= 0 or self.poll_seconds <= 0:
            raise ValueError("Timeout and poll values must be positive.")
        if self.with_orders and os.environ.get(_ACK_ENV, "").strip() != _ACK_VALUE:
            raise ValueError(
                f"{_ACK_ENV} must equal {_ACK_VALUE!r} before PAPER orders are created."
            )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Controlled IBKR PAPER qualification probe. "
            "Economic writes require --with-orders plus explicit acknowledgement."
        )
    )
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--contract-id", type=int, default=265598)
    parser.add_argument("--symbol", default="AAPL")
    parser.add_argument("--market-qty", type=Decimal, default=Decimal("1"))
    parser.add_argument("--limit-qty", type=Decimal, default=Decimal("1"))
    parser.add_argument("--limit-price", type=Decimal)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--poll-seconds", type=float, default=0.25)
    parser.add_argument("--with-orders", action="store_true")
    parser.add_argument("--ci-qualified", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        config = ProbeConfig(
            commit_sha=args.commit_sha,
            contract_id=args.contract_id,
            symbol=args.symbol.strip().upper(),
            market_qty=args.market_qty,
            limit_qty=args.limit_qty,
            limit_price=args.limit_price,
            timeout_seconds=args.timeout_seconds,
            poll_seconds=args.poll_seconds,
            with_orders=args.with_orders,
            ci_qualified=args.ci_qualified,
        )
        bundle = _run_probe(config)
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover - real provider boundary
        print(
            "IBKR controlled PAPER probe failed "
            f"({type(exc).__name__}). Inspect the PAPER account before retrying.",
            file=sys.stderr,
        )
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(bundle.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote sanitized IBKR PAPER evidence to {args.output}")
    print(
        "C3 candidates: "
        + ", ".join(capability.value for capability in bundle.c3_capabilities)
    )
    return 0 if bundle.controlled_probe_passed else 1


def _run_probe(config: ProbeConfig) -> IBKRPaperEvidenceBundle:
    profile = IBKRPaperRuntimeProfile.from_environment()
    connection = build_ibkr_paper_connection_runtime(profile)
    startup = connection.start()
    if not startup.ready_for_startup:
        connection.stop()
        raise RuntimeError("IBKR PAPER startup did not reach read readiness.")

    try:
        client = _probe_client(connection.read_client())
        contract, mapping = _resolve_contract(
            client,
            contract_id=config.contract_id,
            symbol=config.symbol,
        )
        account_rows = _account_values(
            client.accountValues(profile.expected_account_id),
            expected_account=profile.expected_account_id,
        )
        baseline_position = _position_quantity(
            client.portfolio(profile.expected_account_id),
            contract_id=config.contract_id,
        )

        gates: dict[str, str] = {
            "ci_quality_gate": "PASS" if config.ci_qualified else "PENDING",
            "paper_startup": "PASS",
            "paper_account_snapshot": (
                "PASS" if account_rows["cash_present"] else "FAIL"
            ),
            "paper_order_callbacks": "PENDING",
            "paper_market_order": "PENDING",
            "paper_limit_order": "PENDING",
            "paper_cancel_order": "PENDING",
            "paper_partial_fill": "PENDING",
            "paper_order_identity": "PENDING",
            "paper_execution_details": "PENDING",
            "paper_cleanup": "PENDING",
            "paper_reconnect_recovery": "PENDING",
        }
        proofs: dict[str, dict[str, object]] = {
            "BALANCE_QUERY": account_rows,
        }
        observations: dict[str, object] = {
            "startup": {
                "ready_for_startup": startup.ready_for_startup,
                "account": profile.masked_account_id,
            },
            "baseline_position": str(baseline_position),
            "orders_executed": False,
        }

        if config.with_orders:
            observations["orders_executed"] = True
            _run_order_scenarios(
                client=client,
                contract=contract,
                mapping=mapping,
                profile=profile,
                config=config,
                baseline_position=baseline_position,
                gates=gates,
                proofs=proofs,
                observations=observations,
            )

        controlled_passed = (
            config.with_orders
            and gates["paper_market_order"] == "PASS"
            and gates["paper_limit_order"] == "PASS"
            and gates["paper_cancel_order"] == "PASS"
            and gates["paper_order_identity"] == "PASS"
            and gates["paper_execution_details"] == "PASS"
            and gates["paper_cleanup"] == "PASS"
        )
        release_ready = config.ci_qualified and controlled_passed

        c3 = _c3_capabilities(gates, proofs) if release_ready else ()
        source_payload = {
            "commit": config.commit_sha,
            "account": profile.masked_account_id,
            "contract_id": config.contract_id,
            "symbol": config.symbol,
            "gates": gates,
            "proofs": proofs,
            "observations": observations,
        }
        source_hash = canonical_ibkr_evidence_sha256(source_payload)

        payload = {
            "schema_version": "1",
            "provider": "ibkr",
            "environment": "PAPER",
            "provenance": {
                "qualified_commit": config.commit_sha,
                "artifact_name": "ibkr-paper-controlled-probe.json",
                "artifact_json_sha256": source_hash,
                "source_ref": (
                    "manual:ibkr-paper-controlled-probe:"
                    f"{config.commit_sha[:12]}"
                ),
                "workflow_run_id": None,
                "artifact_id": None,
            },
            "captured_at": _captured_at(),
            "sdk": {"name": "ib_async", "version": "2.1.0"},
            "account": profile.masked_account_id,
            "release_ready": release_ready,
            "controlled_probe_passed": controlled_passed,
            "gates": gates,
            "c3_capabilities": [capability.value for capability in c3],
            "proofs": proofs,
        }
        return IBKRPaperEvidenceBundle.from_dict(payload)
    finally:
        connection.stop()


def _run_order_scenarios(
    *,
    client: _ProbeClient,
    contract: object,
    mapping: object,
    profile: IBKRPaperRuntimeProfile,
    config: ProbeConfig,
    baseline_position: Decimal,
    gates: dict[str, str],
    proofs: dict[str, dict[str, object]],
    observations: dict[str, object],
) -> None:
    market_ref = _order_ref("MKT")
    market_trade = _place_once(
        client,
        contract=contract,
        account=profile.expected_account_id,
        action="BUY",
        quantity=config.market_qty,
        order_type="MKT",
        order_ref=market_ref,
        limit_price=None,
    )
    market_status = _wait_for_done(
        client,
        market_trade,
        timeout=config.timeout_seconds,
        poll=config.poll_seconds,
    )
    market_fills = _fill_rows(market_trade)
    market_perm_id = _trade_perm_id(market_trade)
    market_query = _find_trade_by_ref(client.trades(), market_ref)
    market_proof = {
        "submit_attempts": 1,
        "perm_id_present": market_perm_id > 0,
        "terminal_status": market_status,
        "exec_id_present": any(row["exec_id"] for row in market_fills),
    }
    proofs["MARKET_ORDER"] = market_proof
    gates["paper_market_order"] = (
        "PASS"
        if (
            market_status == "Filled"
            and bool(market_proof["perm_id_present"])
            and bool(market_proof["exec_id_present"])
        )
        else "FAIL"
    )
    proofs["ORDER_QUERY"] = {
        "query_observed": market_query is not None,
        "perm_id_present": market_perm_id > 0,
        "order_status_observed": market_status != "",
    }
    gates["paper_order_callbacks"] = (
        "PASS" if market_query is not None and market_status else "FAIL"
    )
    proofs["CLIENT_ORDER_REFERENCE"] = {
        "order_ref_round_trip": _trade_order_ref(market_trade) == market_ref,
        "submit_attempts": 1,
        "resubmitted": False,
    }
    gates["paper_order_identity"] = (
        "PASS"
        if proofs["CLIENT_ORDER_REFERENCE"]["order_ref_round_trip"] is True
        else "FAIL"
    )
    exec_ids = [
        str(row["exec_id"])
        for row in market_fills
        if row["exec_id"]
    ]
    proofs["EXECUTION_FACTS"] = {
        "exec_details_count": len(market_fills),
        "exec_ids_present": bool(exec_ids),
        "fill_mapping_observed": bool(exec_ids),
    }
    gates["paper_execution_details"] = (
        "PASS" if bool(exec_ids) else "FAIL"
    )

    partial_count = sum(
        1
        for row in market_fills
        if Decimal(str(row["cum_qty"])) < config.market_qty
    )
    proofs["PARTIAL_FILL"] = {
        "partial_fill_observed": partial_count > 0,
        "partial_exec_count": partial_count,
        "distinct_exec_ids": len(exec_ids) == len(set(exec_ids)),
    }
    if partial_count > 0 and len(exec_ids) == len(set(exec_ids)):
        gates["paper_partial_fill"] = "PASS"

    limit_price = cast(Decimal, config.limit_price)
    price_rule_validated = _validate_limit_price(
        client,
        mapping=mapping,
        price=limit_price,
    )
    limit_ref = _order_ref("LMT")
    limit_trade = _place_once(
        client,
        contract=contract,
        account=profile.expected_account_id,
        action="BUY",
        quantity=config.limit_qty,
        order_type="LMT",
        order_ref=limit_ref,
        limit_price=limit_price,
    )
    accepted = _wait_for_accepted(
        client,
        limit_trade,
        timeout=config.timeout_seconds,
        poll=config.poll_seconds,
    )
    proofs["LIMIT_ORDER"] = {
        "submit_attempts": 1,
        "accepted": accepted,
        "limit_price_present": True,
        "price_rule_validated": price_rule_validated,
    }
    gates["paper_limit_order"] = (
        "PASS" if accepted and price_rule_validated else "FAIL"
    )

    cancel_attempts = 0
    if accepted and not _trade_done(limit_trade):
        cancel_attempts = 1
        provider_order = _trade_order(limit_trade)
        client.cancelOrder(provider_order)
    cancel_status = _wait_for_done(
        client,
        limit_trade,
        timeout=config.timeout_seconds,
        poll=config.poll_seconds,
    )
    proofs["CANCEL_ORDER"] = {
        "cancel_attempts": cancel_attempts,
        "requested": cancel_attempts == 1,
        "final_status": cancel_status,
    }
    gates["paper_cancel_order"] = (
        "PASS"
        if cancel_attempts == 1
        and cancel_status in {"Cancelled", "ApiCancelled"}
        else "FAIL"
    )

    current_position = _position_quantity(
        client.portfolio(profile.expected_account_id),
        contract_id=config.contract_id,
    )
    delta = current_position - baseline_position
    cleanup_status = "NOT_REQUIRED"
    if delta != 0:
        cleanup_trade = _place_once(
            client,
            contract=contract,
            account=profile.expected_account_id,
            action="SELL" if delta > 0 else "BUY",
            quantity=abs(delta),
            order_type="MKT",
            order_ref=_order_ref("CLEAN"),
            limit_price=None,
        )
        cleanup_status = _wait_for_done(
            client,
            cleanup_trade,
            timeout=config.timeout_seconds,
            poll=config.poll_seconds,
        )

    final_position = _position_quantity(
        client.portfolio(profile.expected_account_id),
        contract_id=config.contract_id,
    )
    baseline_restored = final_position == baseline_position
    gates["paper_cleanup"] = "PASS" if baseline_restored else "FAIL"
    proofs["POSITION_QUERY"] = {
        "position_query_observed": True,
        "baseline_restored": baseline_restored,
    }
    observations["final_position"] = str(final_position)
    observations["cleanup_status"] = cleanup_status


def _resolve_contract(
    client: _ProbeClient,
    *,
    contract_id: int,
    symbol: str,
) -> tuple[object, object]:
    contract_constructor, _ = _sdk_constructors()
    request = contract_constructor(
        conId=contract_id,
        exchange="SMART",
    )
    raw_details = client.reqContractDetails(request)
    exact: list[tuple[object, IBKRContractDetailsRecord]] = []
    for raw in raw_details:
        normalized = normalize_ibkr_contract_details(raw)
        if (
            normalized.contract.contract_id.value == contract_id
            and normalized.contract.symbol == symbol
        ):
            details = cast(_ContractDetailsLike, raw)
            exact.append((details.contract, normalized))
    if len(exact) != 1:
        raise RuntimeError(
            "IBKR controlled probe requires exactly one conId plus symbol match."
        )
    raw_contract, qualified_details = exact[0]
    mapping = map_ibkr_stock_contract(
        qualified_details,
        instrument_id=InstrumentId.new(),
    )
    return raw_contract, mapping


def _validate_limit_price(
    client: _ProbeClient,
    *,
    mapping: object,
    price: Decimal,
) -> bool:
    from pytradekit.brokers.adapters.ibkr import IBKRInstrumentMappingResult

    qualified = cast(IBKRInstrumentMappingResult, mapping)
    if qualified.price_increment_mode is IBKRPriceIncrementMode.MARKET_RULE:
        resolver = IBKRMarketRuleResolver(
            cast(IBKRMarketRuleClient, client)
        )
        return resolver.validate_limit_price(
            instrument=qualified,
            price=price,
        ).valid
    if qualified.price_increment_mode is IBKRPriceIncrementMode.STATIC:
        tick = qualified.specification.tick_size
        return tick is not None and price % tick == 0
    return False


def _place_once(
    client: _ProbeClient,
    *,
    contract: object,
    account: str,
    action: str,
    quantity: Decimal,
    order_type: str,
    order_ref: str,
    limit_price: Decimal | None,
) -> object:
    _, order_constructor = _sdk_constructors()
    kwargs: dict[str, object] = {
        "orderId": client.client.getReqId(),
        "action": action,
        "totalQuantity": quantity,
        "orderType": order_type,
        "tif": "DAY",
        "orderRef": order_ref,
        "transmit": True,
        "outsideRth": False,
        "whatIf": False,
        "overridePercentageConstraints": False,
        "account": account,
    }
    if limit_price is not None:
        kwargs["lmtPrice"] = limit_price
    order = order_constructor(**kwargs)
    return client.placeOrder(contract, order)


def _wait_for_done(
    client: _ProbeClient,
    trade: object,
    *,
    timeout: float,
    poll: float,
) -> str:
    elapsed = 0.0
    candidate = cast(_TradeLike, trade)
    while elapsed < timeout:
        status = _trade_status(trade)
        if candidate.isDone() or status in _TERMINAL_STATUSES:
            return status
        client.sleep(poll)
        elapsed += poll
    return _trade_status(trade)


def _wait_for_accepted(
    client: _ProbeClient,
    trade: object,
    *,
    timeout: float,
    poll: float,
) -> bool:
    elapsed = 0.0
    while elapsed < timeout:
        status = _trade_status(trade)
        if status in {"PreSubmitted", "Submitted"}:
            return True
        if status in _TERMINAL_STATUSES:
            return status == "Filled"
        client.sleep(poll)
        elapsed += poll
    return False


def _probe_client(value: object) -> _ProbeClient:
    required = (
        "client",
        "reqContractDetails",
        "reqMarketRule",
        "accountValues",
        "portfolio",
        "trades",
        "fills",
        "placeOrder",
        "cancelOrder",
        "sleep",
    )
    if any(not hasattr(value, name) for name in required):
        raise RuntimeError(
            "Connected ib_async client lacks the controlled probe surface."
        )
    return cast(_ProbeClient, value)


def _sdk_constructors() -> tuple[_Constructor, _Constructor]:
    module = import_module("ib_async")
    if not hasattr(module, "Contract") or not hasattr(module, "Order"):
        raise RuntimeError("ib_async Contract or Order is unavailable.")
    return (
        cast(_Constructor, module.Contract),
        cast(_Constructor, module.Order),
    )


def _account_values(
    values: list[object],
    *,
    expected_account: str,
) -> dict[str, object]:
    cash_present = False
    equity_present = False
    currency = ""
    for raw in values:
        if not all(
            hasattr(raw, field)
            for field in ("account", "tag", "value", "currency")
        ):
            continue
        item = cast(_AccountValueLike, raw)
        if item.account != expected_account:
            continue
        if item.tag == "TotalCashValue" and item.currency == "USD":
            cash_present = bool(item.value.strip())
            currency = "USD"
        if item.tag == "NetLiquidation" and item.currency == "USD":
            equity_present = bool(item.value.strip())
            currency = "USD"
    return {
        "cash_present": cash_present,
        "equity_present": equity_present,
        "currency": currency,
    }


def _position_quantity(
    values: list[object],
    *,
    contract_id: int,
) -> Decimal:
    total = Decimal("0")
    for raw in values:
        if not hasattr(raw, "contract") or not hasattr(raw, "position"):
            continue
        item = cast(_PortfolioLike, raw)
        contract = item.contract
        if not hasattr(contract, "conId"):
            continue
        qualified = cast(_ContractLike, contract)
        if qualified.conId != contract_id:
            continue
        total += _decimal(item.position, "portfolio.position")
    return total


def _find_trade_by_ref(
    trades: list[object],
    order_ref: str,
) -> object | None:
    matches = [
        trade
        for trade in trades
        if _trade_order_ref(trade) == order_ref
    ]
    if len(matches) > 1:
        raise RuntimeError("IBKR synchronized trades contain duplicate orderRef.")
    return matches[0] if matches else None


def _trade_order(trade: object) -> object:
    if not hasattr(trade, "order"):
        raise RuntimeError("IBKR Trade is missing order.")
    return cast(_TradeLike, trade).order


def _trade_status(trade: object) -> str:
    if not hasattr(trade, "orderStatus"):
        return ""
    status = cast(_TradeLike, trade).orderStatus
    if not hasattr(status, "status"):
        return ""
    value = cast(_OrderStatusLike, status).status
    return value.strip() if isinstance(value, str) else ""


def _trade_order_ref(trade: object) -> str:
    order = _trade_order(trade)
    if not hasattr(order, "orderRef"):
        return ""
    value = cast(_OrderLike, order).orderRef
    return value.strip() if isinstance(value, str) else ""


def _trade_perm_id(trade: object) -> int:
    order = _trade_order(trade)
    if not hasattr(order, "permId"):
        return 0
    value = cast(_OrderLike, order).permId
    return value if type(value) is int and value > 0 else 0


def _trade_done(trade: object) -> bool:
    if not hasattr(trade, "isDone"):
        return False
    return bool(cast(_TradeLike, trade).isDone())


def _fill_rows(trade: object) -> list[dict[str, object]]:
    if not hasattr(trade, "fills"):
        return []
    rows: list[dict[str, object]] = []
    for raw in cast(_TradeLike, trade).fills:
        if not hasattr(raw, "execution"):
            continue
        execution = cast(_FillLike, raw).execution
        required = (
            "execId",
            "permId",
            "orderId",
            "clientId",
            "orderRef",
            "shares",
            "price",
            "cumQty",
        )
        if any(not hasattr(execution, name) for name in required):
            continue
        item = cast(_ExecutionLike, execution)
        rows.append(
            {
                "exec_id": item.execId,
                "perm_id": item.permId,
                "order_id": item.orderId,
                "client_id": item.clientId,
                "order_ref": item.orderRef,
                "shares": str(item.shares),
                "price": str(item.price),
                "cum_qty": str(item.cumQty),
            }
        )
    return rows


def _c3_capabilities(
    gates: dict[str, str],
    proofs: dict[str, dict[str, object]],
) -> tuple[BrokerCapability, ...]:
    candidates: list[BrokerCapability] = []
    for capability in (
        BrokerCapability.ORDER_QUERY,
        BrokerCapability.MARKET_ORDER,
        BrokerCapability.LIMIT_ORDER,
        BrokerCapability.CANCEL_ORDER,
        BrokerCapability.POSITION_QUERY,
        BrokerCapability.BALANCE_QUERY,
        BrokerCapability.CLIENT_ORDER_REFERENCE,
        BrokerCapability.EXECUTION_FACTS,
        BrokerCapability.PARTIAL_FILL,
    ):
        if capability.value not in proofs:
            continue
        gate = {
            BrokerCapability.ORDER_QUERY: "paper_order_callbacks",
            BrokerCapability.MARKET_ORDER: "paper_market_order",
            BrokerCapability.LIMIT_ORDER: "paper_limit_order",
            BrokerCapability.CANCEL_ORDER: "paper_cancel_order",
            BrokerCapability.POSITION_QUERY: "paper_cleanup",
            BrokerCapability.BALANCE_QUERY: "paper_account_snapshot",
            BrokerCapability.CLIENT_ORDER_REFERENCE: "paper_order_identity",
            BrokerCapability.EXECUTION_FACTS: "paper_execution_details",
            BrokerCapability.PARTIAL_FILL: "paper_partial_fill",
        }[capability]
        if gates.get(gate) == "PASS":
            candidates.append(capability)
    return tuple(candidates)


def _captured_at() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()


def _order_ref(kind: str) -> str:
    return f"PTK067-{kind}-{uuid4().hex[:18]}"


def _decimal(value: object, field_name: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise RuntimeError(f"{field_name} is not numeric.") from exc
    if not parsed.is_finite():
        raise RuntimeError(f"{field_name} must be finite.")
    return parsed


if __name__ == "__main__":
    raise SystemExit(main())
