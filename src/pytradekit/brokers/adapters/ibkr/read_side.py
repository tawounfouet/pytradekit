"""IBKR read-side normalization for startup and recovery reconciliation."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Protocol, cast

from pytradekit.brokers import ProviderProtocolError
from pytradekit.orders.domain import OrderId
from pytradekit.portfolio.domain import AccountId
from pytradekit.reconciliation.domain import (
    BrokerSnapshot,
    CanonicalBalance,
    CanonicalFill,
    CanonicalOrder,
    CanonicalPosition,
    ExternalActivityOrigin,
    ReconciliationScope,
    SnapshotCompleteness,
    SnapshotWatermark,
)
from pytradekit.reconciliation.ports import BrokerSnapshotPort
from pytradekit.runtime.ports import ClockPort
from pytradekit.shared import Currency

from .account_mapping import (
    IBKRAccountMetric,
    IBKRAccountMetricTag,
    IBKRAccountRestrictionsObservation,
    IBKRAccountSummaryObservation,
    IBKRPortfolioPositionObservation,
    map_ibkr_account_snapshot,
    map_ibkr_position_snapshot,
)
from .contract_mapping import IBKRInstrumentMappingResult
from .discovery import IBKR_PROVIDER_KEY
from .execution_mapping import (
    IBKRExecutionDetailsObservation,
    IBKRExecutionSide,
)
from .identities import (
    IBKRClientId,
    IBKRContractId,
    IBKRExecutionId,
    IBKROrderReference,
    IBKRPermanentOrderId,
    IBKRSessionOrderId,
)
from .order_callbacks import (
    IBKROrderStateDisposition,
    ibkr_order_status_rule,
)

IBKR_READ_SIDE_VERSION = "0.8.0b3-lot06.2"


class IBKRReadSideError(ValueError):
    """Raised when cached IBKR read-side state cannot be normalized safely."""


class IBKRReadSideClient(Protocol):
    """High-level synchronized state required from the selected IBKR transport."""

    def isConnected(self) -> bool:
        """Return whether the provider session is connected."""

        ...

    def accountValues(self, account: str = "") -> list[object]:
        """Return synchronized account values."""

        ...

    def portfolio(self, account: str = "") -> list[object]:
        """Return synchronized portfolio rows."""

        ...

    def trades(self) -> list[object]:
        """Return synchronized open and completed trades from the session."""

        ...

    def fills(self) -> list[object]:
        """Return synchronized fills from the session."""

        ...


class IBKRInstrumentResolver(Protocol):
    """Resolve a qualified IBKR contract to the frozen canonical mapping."""

    def resolve(
        self,
        *,
        contract_id: IBKRContractId,
        symbol: str,
    ) -> IBKRInstrumentMappingResult | None:
        """Return a qualified mapping or None when reference data is unresolved."""

        ...


class IBKROrderIdentityResolver(Protocol):
    """Resolve provider order identity back to canonical OrderId when known."""

    def resolve_order_id(
        self,
        external_order_id: str,
        client_order_id: str | None = None,
    ) -> OrderId | None:
        """Resolve by durable permId first, then optional orderRef."""

        ...


class IBKRAccountRestrictionsProvider(Protocol):
    """Provide explicit restriction evidence without inferring missing semantics."""

    def get(
        self,
        external_account_id: str,
    ) -> IBKRAccountRestrictionsObservation | None:
        """Return explicit account restriction evidence or None."""

        ...


class StaticIBKRInstrumentResolver:
    """Resolve only pre-qualified LOT-05.2 instrument mappings."""

    def __init__(
        self,
        mappings: Iterable[IBKRInstrumentMappingResult],
    ) -> None:
        self._mappings: dict[
            tuple[int, str],
            IBKRInstrumentMappingResult,
        ] = {}
        for mapping in mappings:
            if not isinstance(mapping, IBKRInstrumentMappingResult):
                raise IBKRReadSideError(
                    "mappings must contain IBKRInstrumentMappingResult values."
                )
            key = (
                int(mapping.identity.external_id),
                mapping.identity.external_symbol,
            )
            if key in self._mappings:
                raise IBKRReadSideError(
                    "IBKR instrument mappings must be unique by conId and symbol."
                )
            self._mappings[key] = mapping

    def resolve(
        self,
        *,
        contract_id: IBKRContractId,
        symbol: str,
    ) -> IBKRInstrumentMappingResult | None:
        return self._mappings.get((contract_id.value, symbol.strip()))


class StaticIBKRAccountRestrictionsProvider:
    """Return only explicit restriction evidence supplied by the caller."""

    def __init__(
        self,
        evidence: Mapping[str, IBKRAccountRestrictionsObservation],
    ) -> None:
        self._evidence: dict[str, IBKRAccountRestrictionsObservation] = {}
        for account, observation in evidence.items():
            normalized = account.strip()
            if not normalized:
                raise IBKRReadSideError(
                    "restriction evidence account IDs must be non-empty."
                )
            if not isinstance(
                observation,
                IBKRAccountRestrictionsObservation,
            ):
                raise IBKRReadSideError(
                    "restriction evidence values must be "
                    "IBKRAccountRestrictionsObservation."
                )
            self._evidence[normalized] = observation

    def get(
        self,
        external_account_id: str,
    ) -> IBKRAccountRestrictionsObservation | None:
        return self._evidence.get(external_account_id.strip())


class _AccountValueLike(Protocol):
    account: str
    tag: str
    value: str
    currency: str


class _ContractLike(Protocol):
    conId: int
    symbol: str
    secType: str
    currency: str


class _PortfolioItemLike(Protocol):
    account: str
    contract: _ContractLike
    position: object
    marketPrice: object
    marketValue: object
    averageCost: object
    unrealizedPNL: object
    realizedPNL: object


class _OrderLike(Protocol):
    orderId: int
    clientId: int
    permId: int
    orderRef: str


class _OrderStatusLike(Protocol):
    status: str
    filled: object
    remaining: object
    avgFillPrice: object
    permId: int
    clientId: int
    orderId: int
    lastFillPrice: object
    whyHeld: str


class _TradeLike(Protocol):
    order: _OrderLike
    orderStatus: _OrderStatusLike
    contract: _ContractLike


class _ExecutionLike(Protocol):
    execId: str
    acctNumber: str
    exchange: str
    side: str
    shares: object
    price: object
    permId: int
    clientId: int
    orderId: int
    cumQty: object
    avgPrice: object
    orderRef: str
    pendingPriceRevision: bool
    time: datetime


class _FillLike(Protocol):
    contract: _ContractLike
    execution: _ExecutionLike
    time: datetime


@dataclass(frozen=True, slots=True)
class IBKRReadSideCaptureStats:
    """Diagnostic counts for one provider snapshot capture."""

    orders: int
    fills: int
    positions: int
    balances: int
    partial_reasons: tuple[str, ...] = ()

    @property
    def complete(self) -> bool:
        return not self.partial_reasons


class IBKRBrokerSnapshotPort(BrokerSnapshotPort):
    """Normalize synchronized IBKR state into the generic BrokerSnapshot model."""

    def __init__(
        self,
        *,
        client: IBKRReadSideClient,
        expected_external_account_id: str,
        instruments: IBKRInstrumentResolver,
        identities: IBKROrderIdentityResolver,
        restrictions: IBKRAccountRestrictionsProvider,
        clock: ClockPort,
    ) -> None:
        account = expected_external_account_id.strip()
        if not account:
            raise IBKRReadSideError(
                "expected_external_account_id must be non-empty."
            )
        self._client = client
        self._external_account_id = account
        self._instruments = instruments
        self._identities = identities
        self._restrictions = restrictions
        self._clock = clock
        self._last_stats: IBKRReadSideCaptureStats | None = None

    @property
    def last_stats(self) -> IBKRReadSideCaptureStats | None:
        return self._last_stats

    def capture(
        self,
        *,
        account_id: AccountId,
        scope: ReconciliationScope,
    ) -> BrokerSnapshot:
        if not self._client.isConnected():
            raise ProviderProtocolError(
                "IBKR read-side capture requires an active synchronized session.",
                provider=IBKR_PROVIDER_KEY,
                operation="broker_snapshot",
            )

        captured_at = self._clock.now()
        partial: list[str] = []
        orders: tuple[CanonicalOrder, ...] = ()
        fills: tuple[CanonicalFill, ...] = ()
        positions: tuple[CanonicalPosition, ...] = ()
        balances: tuple[CanonicalBalance, ...] = ()

        if scope in {ReconciliationScope.ORDERS, ReconciliationScope.FULL}:
            orders, reasons = self._capture_orders()
            partial.extend(reasons)

        if scope in {ReconciliationScope.FILLS, ReconciliationScope.FULL}:
            fills, reasons = self._capture_fills()
            partial.extend(reasons)

        if scope in {ReconciliationScope.POSITIONS, ReconciliationScope.FULL}:
            positions, reasons = self._capture_positions(account_id)
            partial.extend(reasons)

        if scope in {
            ReconciliationScope.ACCOUNT,
            ReconciliationScope.BALANCES,
            ReconciliationScope.FULL,
        }:
            balances, reasons = self._capture_balances(account_id, captured_at)
            partial.extend(reasons)

        deduplicated_reasons = tuple(dict.fromkeys(partial))
        completeness = (
            SnapshotCompleteness.COMPLETE
            if not deduplicated_reasons
            else SnapshotCompleteness.PARTIAL
        )
        self._last_stats = IBKRReadSideCaptureStats(
            orders=len(orders),
            fills=len(fills),
            positions=len(positions),
            balances=len(balances),
            partial_reasons=deduplicated_reasons,
        )

        return BrokerSnapshot(
            account_id=account_id,
            provider=IBKR_PROVIDER_KEY,
            orders=orders,
            fills=fills,
            positions=positions,
            balances=balances,
            captured_at=captured_at,
            watermark=SnapshotWatermark(
                captured_at=captured_at,
                provider_as_of=captured_at,
            ),
            completeness=completeness,
        )

    def _capture_balances(
        self,
        account_id: AccountId,
        captured_at: datetime,
    ) -> tuple[tuple[CanonicalBalance, ...], tuple[str, ...]]:
        raw = self._client.accountValues(self._external_account_id)
        try:
            normalized_values = tuple(_account_value(item) for item in raw)
            account_values = tuple(
                item
                for item in normalized_values
                if item.account == self._external_account_id
            )
            observation = _account_observation(
                account_values,
                external_account_id=self._external_account_id,
                observed_at=captured_at,
            )
        except Exception:
            return (), ("account values could not be normalized",)

        restriction_evidence = self._restrictions.get(self._external_account_id)
        if restriction_evidence is None:
            return (), ("explicit account restriction evidence is unavailable",)

        try:
            mapped = map_ibkr_account_snapshot(
                observation,
                account_id=account_id,
                restrictions=restriction_evidence,
            )
        except Exception:
            return (), ("account snapshot mapping failed",)

        cash = mapped.snapshot.cash_balance
        if cash is None:
            return (), ("TotalCashValue is unavailable in base currency",)

        return (
            (
                CanonicalBalance(
                    currency=cash.currency,
                    cash=cash.cash.amount,
                ),
            ),
            (),
        )

    def _capture_positions(
        self,
        account_id: AccountId,
    ) -> tuple[tuple[CanonicalPosition, ...], tuple[str, ...]]:
        result: list[CanonicalPosition] = []
        partial: list[str] = []

        for raw in self._client.portfolio(self._external_account_id):
            item = _portfolio_item(raw)
            if item.account != self._external_account_id:
                continue
            quantity = _decimal(item.position, field_name="portfolio position")
            if quantity == 0:
                continue
            contract = item.contract
            try:
                contract_id = IBKRContractId(contract.conId)
            except Exception:
                partial.append("position has no qualified conId")
                continue
            mapping = self._instruments.resolve(
                contract_id=contract_id,
                symbol=contract.symbol,
            )
            if mapping is None:
                partial.append("position instrument mapping is unresolved")
                continue

            try:
                observation = IBKRPortfolioPositionObservation(
                    external_account_id=item.account,
                    contract_id=contract_id,
                    symbol=contract.symbol,
                    currency=Currency(contract.currency),
                    signed_quantity=quantity,
                    average_cost=_decimal(
                        item.averageCost,
                        field_name="portfolio averageCost",
                    ),
                    market_price=_optional_positive_decimal(
                        item.marketPrice,
                    ),
                    market_value=_optional_decimal(item.marketValue),
                    unrealized_pnl=_optional_decimal(item.unrealizedPNL),
                    realized_pnl=_optional_decimal(item.realizedPNL),
                    observed_at=self._clock.now(),
                )
                mapped = map_ibkr_position_snapshot(
                    observation,
                    account_id=account_id,
                    expected_external_account_id=self._external_account_id,
                    instrument=mapping,
                )
            except Exception:
                partial.append("position mapping failed")
                continue

            snapshot = mapped.snapshot
            result.append(
                CanonicalPosition(
                    instrument_id=snapshot.instrument_id,
                    quantity=snapshot.signed_quantity,
                    average_price=snapshot.average_price.value,
                    currency=snapshot.average_price.currency,
                )
            )

        result.sort(key=lambda item: item.instrument_id.value)
        return tuple(result), tuple(partial)

    def _capture_orders(
        self,
    ) -> tuple[tuple[CanonicalOrder, ...], tuple[str, ...]]:
        result: list[CanonicalOrder] = []
        partial: list[str] = []

        for raw in self._client.trades():
            trade = _trade(raw)
            order = trade.order
            status = trade.orderStatus
            permanent_id = status.permId or order.permId
            if permanent_id <= 0:
                partial.append("order has no stable permId")
                continue

            external_order_id = str(IBKRPermanentOrderId(permanent_id))
            client_order_id = order.orderRef.strip() or None
            order_id = self._identities.resolve_order_id(
                external_order_id,
                client_order_id,
            )
            provider_status = status.status.strip()
            if not provider_status:
                partial.append("order has no provider status")
                continue

            rule = ibkr_order_status_rule(provider_status)
            cancel_requested = provider_status == "PendingCancel"
            if rule.disposition is IBKROrderStateDisposition.MAP:
                assert rule.canonical_status is not None
                canonical_status = rule.canonical_status.value
            elif provider_status == "PendingCancel":
                canonical_status = "CANCEL_REQUESTED"
            elif provider_status == "PendingSubmit":
                canonical_status = "SUBMITTED"
            else:
                canonical_status = provider_status.upper()
                partial.append(
                    "order status requires reconciliation-specific handling"
                )

            result.append(
                CanonicalOrder(
                    order_id=order_id,
                    client_order_id=client_order_id,
                    external_order_id=external_order_id,
                    status=canonical_status,
                    filled_quantity=_non_negative_decimal(
                        status.filled,
                        field_name="order filled",
                    ),
                    cancel_requested=cancel_requested,
                )
            )

        result.sort(
            key=lambda item: (
                item.client_order_id or "",
                item.external_order_id or "",
            )
        )
        return tuple(result), tuple(partial)

    def _capture_fills(
        self,
    ) -> tuple[tuple[CanonicalFill, ...], tuple[str, ...]]:
        result: list[CanonicalFill] = []
        partial: list[str] = []

        for raw in self._client.fills():
            fill = _fill(raw)
            execution = fill.execution
            if execution.acctNumber.strip() != self._external_account_id:
                continue
            if execution.permId <= 0:
                partial.append("fill has no stable permId")
                continue

            external_order_id = str(IBKRPermanentOrderId(execution.permId))
            client_order_id = execution.orderRef.strip() or None
            order_id = self._identities.resolve_order_id(
                external_order_id,
                client_order_id,
            )
            try:
                execution_id = IBKRExecutionId(execution.execId)
                contract_id = IBKRContractId(fill.contract.conId)
                occurred_at = _aware_datetime(fill.time)
                if client_order_id is not None:
                    IBKRExecutionDetailsObservation(
                        contract_id=contract_id,
                        symbol=fill.contract.symbol,
                        execution_id=execution_id,
                        client_id=IBKRClientId(execution.clientId),
                        session_order_id=IBKRSessionOrderId(execution.orderId),
                        permanent_order_id=IBKRPermanentOrderId(execution.permId),
                        order_reference=IBKROrderReference(client_order_id),
                        side=IBKRExecutionSide(execution.side),
                        shares=_positive_decimal(
                            execution.shares,
                            field_name="execution shares",
                        ),
                        price=_positive_decimal(
                            execution.price,
                            field_name="execution price",
                        ),
                        cumulative_quantity=_positive_decimal(
                            execution.cumQty,
                            field_name="execution cumulative quantity",
                        ),
                        average_price=_positive_decimal(
                            execution.avgPrice,
                            field_name="execution average price",
                        ),
                        exchange=execution.exchange,
                        account=execution.acctNumber,
                        occurred_at=occurred_at,
                        pending_price_revision=execution.pendingPriceRevision,
                    )
            except Exception:
                partial.append("fill execution observation is invalid")
                continue

            if execution.pendingPriceRevision:
                partial.append("fill has pending price revision")
                continue

            if order_id is None and not external_order_id:
                partial.append("fill cannot be correlated to an order")
                continue

            result.append(
                CanonicalFill(
                    external_fill_id=execution_id.value,
                    order_id=order_id,
                    external_order_id=external_order_id,
                    quantity=_positive_decimal(
                        execution.shares,
                        field_name="execution shares",
                    ),
                    price=_positive_decimal(
                        execution.price,
                        field_name="execution price",
                    ),
                    currency=Currency(fill.contract.currency),
                    occurred_at=occurred_at,
                    origin=(
                        ExternalActivityOrigin.INTERNAL
                        if order_id is not None
                        else ExternalActivityOrigin.UNKNOWN_EXTERNAL
                    ),
                )
            )

        result.sort(key=lambda item: (item.occurred_at, item.external_fill_id))
        return tuple(result), tuple(partial)


def _account_observation(
    values: Iterable[_AccountValueLike],
    *,
    external_account_id: str,
    observed_at: datetime,
) -> IBKRAccountSummaryObservation:
    rows = tuple(values)
    account_ready: bool | None = None
    metric_rows: list[tuple[IBKRAccountMetricTag, Decimal, str]] = []

    for row in rows:
        tag = row.tag.strip()
        if tag.lower() == "accountready":
            normalized = row.value.strip().lower()
            if normalized in {"true", "1"}:
                account_ready = True
            elif normalized in {"false", "0"}:
                account_ready = False
            else:
                raise IBKRReadSideError("AccountReady value is invalid.")
            continue

        try:
            metric_tag = IBKRAccountMetricTag(tag)
        except ValueError:
            continue
        currency = row.currency.strip().upper()
        if not currency:
            continue
        metric_rows.append(
            (
                metric_tag,
                _decimal(row.value, field_name=tag),
                currency,
            )
        )

    if account_ready is None:
        raise IBKRReadSideError("AccountReady value is unavailable.")
    base_currency = _resolve_base_currency(metric_rows)
    metrics = tuple(
        IBKRAccountMetric(
            tag=tag,
            value=value,
            currency=Currency(currency),
        )
        for tag, value, currency in metric_rows
    )
    return IBKRAccountSummaryObservation(
        external_account_id=external_account_id,
        base_currency=Currency(base_currency),
        account_ready=account_ready,
        metrics=metrics,
        observed_at=observed_at,
    )


def _resolve_base_currency(
    rows: Iterable[tuple[IBKRAccountMetricTag, Decimal, str]],
) -> str:
    priority = (
        IBKRAccountMetricTag.TOTAL_CASH_VALUE,
        IBKRAccountMetricTag.NET_LIQUIDATION,
        IBKRAccountMetricTag.BUYING_POWER,
    )
    materialized = tuple(rows)
    for tag in priority:
        currencies = {
            currency
            for candidate, _value, currency in materialized
            if candidate is tag
        }
        if len(currencies) == 1:
            return next(iter(currencies))
        if len(currencies) > 1:
            raise IBKRReadSideError(
                f"{tag.value} exposes multiple currencies."
            )
    raise IBKRReadSideError(
        "IBKR base currency cannot be established from account metrics."
    )


def _account_value(value: object) -> _AccountValueLike:
    required = ("account", "tag", "value", "currency")
    if any(not hasattr(value, name) for name in required):
        raise IBKRReadSideError("IBKR account value has an invalid shape.")
    return cast(_AccountValueLike, value)


def _portfolio_item(value: object) -> _PortfolioItemLike:
    required = (
        "account",
        "contract",
        "position",
        "marketPrice",
        "marketValue",
        "averageCost",
        "unrealizedPNL",
        "realizedPNL",
    )
    if any(not hasattr(value, name) for name in required):
        raise IBKRReadSideError("IBKR portfolio item has an invalid shape.")
    return cast(_PortfolioItemLike, value)


def _trade(value: object) -> _TradeLike:
    if not all(hasattr(value, name) for name in ("order", "orderStatus", "contract")):
        raise IBKRReadSideError("IBKR trade has an invalid shape.")
    return cast(_TradeLike, value)


def _fill(value: object) -> _FillLike:
    if not all(hasattr(value, name) for name in ("contract", "execution", "time")):
        raise IBKRReadSideError("IBKR fill has an invalid shape.")
    return cast(_FillLike, value)


def _decimal(value: object, *, field_name: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise IBKRReadSideError(f"{field_name} is not a Decimal.") from exc
    if not parsed.is_finite():
        raise IBKRReadSideError(f"{field_name} must be finite.")
    return parsed


def _positive_decimal(value: object, *, field_name: str) -> Decimal:
    parsed = _decimal(value, field_name=field_name)
    if parsed <= 0:
        raise IBKRReadSideError(f"{field_name} must be positive.")
    return parsed


def _non_negative_decimal(value: object, *, field_name: str) -> Decimal:
    parsed = _decimal(value, field_name=field_name)
    if parsed < 0:
        raise IBKRReadSideError(f"{field_name} must be non-negative.")
    return parsed


def _optional_decimal(value: object) -> Decimal | None:
    parsed = _decimal(value, field_name="optional provider decimal")
    return parsed


def _optional_positive_decimal(value: object) -> Decimal | None:
    parsed = _decimal(value, field_name="optional provider price")
    if parsed <= 0:
        return None
    return parsed


def _aware_datetime(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise IBKRReadSideError("provider datetime has an invalid type.")
    if value.tzinfo is None or value.utcoffset() is None:
        raise IBKRReadSideError("provider datetime must be timezone-aware.")
    return value
