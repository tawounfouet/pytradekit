"""Alpaca anti-corruption mappers into canonical PyTradeKit semantics."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Never
from uuid import NAMESPACE_URL, uuid5

from alpaca.trading.enums import (
    AssetClass as AlpacaAssetClass,
    PositionSide as AlpacaPositionSide,
    TradeEvent as AlpacaTradeEvent,
)
from alpaca.trading.models import Asset, Order, Position, TradeAccount, TradeUpdate

from pytradekit.brokers import (
    ProviderAccountSnapshot,
    ProviderExecutionContext,
    ProviderInstrumentIdentity,
    ProviderInstrumentSnapshot,
    ProviderOrderIdentity,
    ProviderOrderStateSnapshot,
    ProviderPositionSnapshot,
    ProviderProtocolError,
    ProviderStateReconciliationRequired,
    ProviderUnsupportedStateError,
)
from pytradekit.execution import (
    ExecutionReport,
    ExecutionStatus,
    Fill,
    FillId,
    SubmissionResult,
    SubmissionStatus,
)
from pytradekit.portfolio.domain import Account, AccountId, Balance
from pytradekit.reference.domain import (
    AssetClass,
    ContractSpecification,
    Instrument,
    InstrumentMapping,
)
from pytradekit.shared import (
    Currency,
    InstrumentId,
    Money,
    Price,
    Quantity,
)

from .contract import (
    ALPACA_PROVIDER_KEY,
    AlpacaStateDisposition,
    order_status_rule,
    trade_event_rule,
    validate_client_order_reference,
)
from .identities import (
    map_account_identity,
    map_fill_identity,
    map_instrument_identity,
    map_order_identity,
)


def map_asset_snapshot(
    asset: Asset,
    *,
    instrument_id: InstrumentId,
    observed_at: datetime,
) -> ProviderInstrumentSnapshot:
    """Map a qualified Alpaca US equity asset into canonical reference models."""

    if asset.asset_class is not AlpacaAssetClass.US_EQUITY:
        raise _protocol_error(
            "Alpaca asset is outside the qualified US_EQUITY scope.",
            operation="map_asset",
        )

    timestamp = _utc(observed_at, field_name="asset observed_at")
    identity = map_instrument_identity(asset)
    currency = Currency("USD")
    instrument = Instrument(
        id=instrument_id,
        symbol=identity.external_symbol,
        asset_class=AssetClass.EQUITY,
        quote_currency=currency,
    )
    mapping = InstrumentMapping(
        instrument_id=instrument_id,
        provider=ALPACA_PROVIDER_KEY,
        external_symbol=identity.external_symbol,
        external_id=identity.external_id,
    )
    specification = ContractSpecification(
        tick_size=_optional_positive_decimal(asset.price_increment, field_name="price_increment"),
        quantity_step=_optional_positive_decimal(
            asset.min_trade_increment,
            field_name="min_trade_increment",
        ),
        min_quantity=_optional_non_negative_decimal(
            asset.min_order_size,
            field_name="min_order_size",
        ),
    )
    return ProviderInstrumentSnapshot(
        identity=identity,
        instrument=instrument,
        mapping=mapping,
        specification=specification,
        provider_exchange=asset.exchange.value,
        provider_status=asset.status.value,
        tradable=asset.tradable,
        marginable=asset.marginable,
        shortable=asset.shortable,
        easy_to_borrow=asset.easy_to_borrow,
        fractionable=asset.fractionable,
        observed_at=timestamp,
    )


def map_account_snapshot(
    account: TradeAccount,
    *,
    account_id: AccountId,
    observed_at: datetime,
) -> ProviderAccountSnapshot:
    """Map Alpaca account values without conflating buying power with cash."""

    timestamp = _utc(observed_at, field_name="account observed_at")
    identity = map_account_identity(account)
    currency = _currency(account.currency or "USD")
    canonical_account = Account(
        id=account_id,
        base_currency=currency,
    )
    cash = _optional_money(account.cash, currency=currency, field_name="cash")
    cash_balance = (
        Balance(
            account_id=account_id,
            currency=currency,
            cash=cash,
            updated_at=timestamp,
        )
        if cash is not None
        else None
    )
    return ProviderAccountSnapshot(
        identity=identity,
        account=canonical_account,
        cash_balance=cash_balance,
        equity=_optional_money(account.equity, currency=currency, field_name="equity"),
        buying_power=_optional_money(
            account.buying_power,
            currency=currency,
            field_name="buying_power",
        ),
        portfolio_value=_optional_money(
            account.portfolio_value,
            currency=currency,
            field_name="portfolio_value",
        ),
        trading_blocked=bool(account.trading_blocked),
        account_blocked=bool(account.account_blocked),
        observed_at=timestamp,
    )


def map_position_snapshot(
    position: Position,
    *,
    account_id: AccountId,
    instrument_id: InstrumentId,
    quote_currency: Currency,
    observed_at: datetime,
) -> ProviderPositionSnapshot:
    """Map one Alpaca position without fabricating realized PnL."""

    if position.asset_class is not AlpacaAssetClass.US_EQUITY:
        raise _protocol_error(
            "Alpaca position is outside the qualified US_EQUITY scope.",
            operation="map_position",
        )
    timestamp = _utc(observed_at, field_name="position observed_at")
    raw_quantity = _required_non_negative_decimal(position.qty, field_name="qty")
    signed_quantity = (
        raw_quantity
        if position.side is AlpacaPositionSide.LONG
        else -raw_quantity
        if position.side is AlpacaPositionSide.SHORT
        else _raise_position_side(position.side)
    )
    identity = _position_instrument_identity(position)
    average_price = Price(
        _required_positive_decimal(position.avg_entry_price, field_name="avg_entry_price"),
        quote_currency,
    )
    cost_basis = Money(
        _required_decimal(position.cost_basis, field_name="cost_basis"),
        quote_currency,
    )
    return ProviderPositionSnapshot(
        account_id=account_id,
        instrument_id=instrument_id,
        provider_instrument=identity,
        signed_quantity=signed_quantity,
        average_price=average_price,
        market_value=_optional_money(
            position.market_value,
            currency=quote_currency,
            field_name="market_value",
        ),
        cost_basis=cost_basis,
        unrealized_pnl=_optional_money(
            position.unrealized_pl,
            currency=quote_currency,
            field_name="unrealized_pl",
        ),
        current_price=_optional_price(
            position.current_price,
            currency=quote_currency,
            field_name="current_price",
        ),
        available_quantity=_optional_non_negative_decimal(
            position.qty_available,
            field_name="qty_available",
        ),
        observed_at=timestamp,
    )


def map_order_state_snapshot(
    order: Order,
    *,
    context: ProviderExecutionContext,
    observed_at: datetime | None = None,
) -> ProviderOrderStateSnapshot:
    """Map an Alpaca order query into a safe state snapshot without inventing fills."""

    identity = _validated_order_identity(order, context=context)
    rule = order_status_rule(order.status)
    filled_quantity = _optional_non_negative_decimal(
        order.filled_qty,
        field_name="filled_qty",
    ) or Decimal("0")
    filled_average_price = _optional_positive_decimal(
        order.filled_avg_price,
        field_name="filled_avg_price",
    )
    timestamp = _utc(
        observed_at or order.updated_at,
        field_name="order observed_at",
    )
    return ProviderOrderStateSnapshot(
        order_id=context.order_id,
        identity=identity,
        provider_status=order.status.value,
        canonical_status=rule.canonical_status,
        filled_quantity=filled_quantity,
        filled_average_price=filled_average_price,
        observed_at=timestamp,
    )


def map_order_query_report(
    order: Order,
    *,
    context: ProviderExecutionContext,
) -> ExecutionReport | None:
    """Map a queried order only when it can become a complete canonical fact safely."""

    identity = _validated_order_identity(order, context=context)
    rule = order_status_rule(order.status)

    if rule.disposition is AlpacaStateDisposition.TRANSIENT:
        return None
    if rule.disposition is AlpacaStateDisposition.OUT_OF_SCOPE:
        raise ProviderUnsupportedStateError(
            f"Alpaca order status {order.status.value!r} is outside the 0.5 contract.",
            provider=ALPACA_PROVIDER_KEY,
            operation="query_order",
        )
    if rule.disposition is AlpacaStateDisposition.RECONCILE:
        raise ProviderStateReconciliationRequired(
            f"Alpaca order status {order.status.value!r} requires reconciliation.",
            provider=ALPACA_PROVIDER_KEY,
            operation="query_order",
        )

    status = rule.canonical_status
    if status is None:
        raise _protocol_error(
            "Mapped Alpaca order status is missing canonical status.",
            operation="query_order",
        )
    if status in {ExecutionStatus.PARTIALLY_FILLED, ExecutionStatus.FILLED}:
        raise ProviderStateReconciliationRequired(
            "Alpaca order snapshot reports fills but does not identify individual executions.",
            provider=ALPACA_PROVIDER_KEY,
            operation="query_order",
        )

    return ExecutionReport(
        order_id=context.order_id,
        status=status,
        occurred_at=_order_event_time(order, status=status),
        correlation_id=context.correlation_id,
        external_order_id=identity.external_order_id,
        rejection_reason=(
            "Alpaca reported order rejection."
            if status is ExecutionStatus.REJECTED
            else None
        ),
    )


def map_trade_update_report(
    update: TradeUpdate,
    *,
    context: ProviderExecutionContext,
) -> ExecutionReport | None:
    """Translate a private Alpaca trade_update into one canonical execution fact."""

    identity = _validated_order_identity(update.order, context=context)
    event = _trade_event(update.event)
    rule = trade_event_rule(event)

    if rule.disposition is AlpacaStateDisposition.TRANSIENT:
        return None
    if rule.disposition is AlpacaStateDisposition.OUT_OF_SCOPE:
        raise ProviderUnsupportedStateError(
            f"Alpaca trade event {event.value!r} is outside the 0.5 contract.",
            provider=ALPACA_PROVIDER_KEY,
            operation="trade_update",
        )
    if rule.disposition is AlpacaStateDisposition.RECONCILE:
        raise ProviderStateReconciliationRequired(
            f"Alpaca trade event {event.value!r} requires reconciliation.",
            provider=ALPACA_PROVIDER_KEY,
            operation="trade_update",
        )

    status = rule.canonical_status
    if status is None:
        raise _protocol_error(
            "Mapped Alpaca trade event is missing canonical status.",
            operation="trade_update",
        )

    fill: Fill | None = None
    if status in {ExecutionStatus.PARTIALLY_FILLED, ExecutionStatus.FILLED}:
        fill_identity = map_fill_identity(update)
        quantity = Quantity(
            _required_positive_decimal(update.qty, field_name="trade_update.qty")
        )
        price = Price(
            _required_positive_decimal(update.price, field_name="trade_update.price"),
            context.quote_currency,
        )
        fill = Fill(
            id=_canonical_fill_id(fill_identity.external_fill_id),
            order_id=context.order_id,
            quantity=quantity,
            price=price,
            occurred_at=_utc(update.timestamp, field_name="trade_update timestamp"),
            external_fill_id=fill_identity.external_fill_id,
        )

    return ExecutionReport(
        order_id=context.order_id,
        status=status,
        occurred_at=_utc(update.timestamp, field_name="trade_update timestamp"),
        correlation_id=context.correlation_id,
        external_order_id=identity.external_order_id,
        fill=fill,
        rejection_reason=(
            "Alpaca reported order rejection."
            if status is ExecutionStatus.REJECTED
            else None
        ),
    )


def map_submission_ack(
    order: Order,
    *,
    expected_client_order_reference: str,
) -> SubmissionResult:
    """Map Alpaca submit response into the immediate provider-neutral result."""

    expected = validate_client_order_reference(expected_client_order_reference)
    if order.client_order_id != expected:
        raise _protocol_error(
            "Alpaca submit response client_order_id does not match the submitted order.",
            operation="submit",
        )
    identity = map_order_identity(order)
    if order.status.value == "rejected":
        return SubmissionResult(
            status=SubmissionStatus.REJECTED,
            reason="Alpaca reported order rejection.",
        )
    return SubmissionResult(
        status=SubmissionStatus.ACKNOWLEDGED,
        external_order_id=identity.external_order_id,
    )


def _validated_order_identity(
    order: Order,
    *,
    context: ProviderExecutionContext,
) -> ProviderOrderIdentity:
    identity = map_order_identity(order)
    expected = validate_client_order_reference(context.client_order_reference)
    if identity.client_reference != expected:
        raise _protocol_error(
            "Alpaca order client_order_id does not match canonical order context.",
            operation="map_order",
        )
    return identity


def _position_instrument_identity(position: Position) -> ProviderInstrumentIdentity:
    return ProviderInstrumentIdentity(
        provider=ALPACA_PROVIDER_KEY,
        external_id=str(position.asset_id),
        external_symbol=position.symbol,
    )


def _trade_event(value: AlpacaTradeEvent | str) -> AlpacaTradeEvent:
    if isinstance(value, AlpacaTradeEvent):
        return value
    try:
        return AlpacaTradeEvent(value)
    except ValueError as exc:
        raise ProviderStateReconciliationRequired(
            f"Unknown Alpaca trade event {value!r} requires reconciliation.",
            provider=ALPACA_PROVIDER_KEY,
            operation="trade_update",
        ) from exc


def _canonical_fill_id(external_fill_id: str) -> FillId:
    return FillId(uuid5(NAMESPACE_URL, f"pytradekit:alpaca:fill:{external_fill_id}"))


def _order_event_time(order: Order, *, status: ExecutionStatus) -> datetime:
    candidate: datetime
    if status is ExecutionStatus.CANCELLED and order.canceled_at is not None:
        candidate = order.canceled_at
    elif status is ExecutionStatus.EXPIRED and order.expired_at is not None:
        candidate = order.expired_at
    else:
        candidate = order.updated_at
    return _utc(candidate, field_name="order event timestamp")


def _utc(value: datetime, *, field_name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise _protocol_error(
            f"Alpaca {field_name} must be timezone-aware.",
            operation="map_payload",
        )
    return value.astimezone(UTC)


def _currency(value: str) -> Currency:
    try:
        return Currency(value)
    except Exception as exc:
        raise _protocol_error(
            "Alpaca account currency is invalid.",
            operation="map_account",
        ) from exc


def _decimal(value: object, *, field_name: str) -> Decimal:
    if value is None or isinstance(value, bool):
        raise _protocol_error(
            f"Alpaca {field_name} is missing or invalid.",
            operation="map_payload",
        )
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise _protocol_error(
            f"Alpaca {field_name} is not a valid decimal value.",
            operation="map_payload",
        ) from exc
    if not result.is_finite():
        raise _protocol_error(
            f"Alpaca {field_name} must be finite.",
            operation="map_payload",
        )
    return result


def _required_decimal(value: object, *, field_name: str) -> Decimal:
    return _decimal(value, field_name=field_name)


def _required_positive_decimal(value: object, *, field_name: str) -> Decimal:
    result = _decimal(value, field_name=field_name)
    if result <= 0:
        raise _protocol_error(
            f"Alpaca {field_name} must be greater than zero.",
            operation="map_payload",
        )
    return result


def _required_non_negative_decimal(value: object, *, field_name: str) -> Decimal:
    result = _decimal(value, field_name=field_name)
    if result < 0:
        raise _protocol_error(
            f"Alpaca {field_name} must not be negative.",
            operation="map_payload",
        )
    return result


def _optional_decimal(value: object, *, field_name: str) -> Decimal | None:
    if value is None:
        return None
    return _decimal(value, field_name=field_name)


def _optional_positive_decimal(value: object, *, field_name: str) -> Decimal | None:
    result = _optional_decimal(value, field_name=field_name)
    if result is not None and result <= 0:
        raise _protocol_error(
            f"Alpaca {field_name} must be greater than zero when provided.",
            operation="map_payload",
        )
    return result


def _optional_non_negative_decimal(value: object, *, field_name: str) -> Decimal | None:
    result = _optional_decimal(value, field_name=field_name)
    if result is not None and result < 0:
        raise _protocol_error(
            f"Alpaca {field_name} must not be negative when provided.",
            operation="map_payload",
        )
    return result


def _optional_money(
    value: object,
    *,
    currency: Currency,
    field_name: str,
) -> Money | None:
    result = _optional_decimal(value, field_name=field_name)
    return None if result is None else Money(result, currency)


def _optional_price(
    value: object,
    *,
    currency: Currency,
    field_name: str,
) -> Price | None:
    result = _optional_positive_decimal(value, field_name=field_name)
    return None if result is None else Price(result, currency)


def _raise_position_side(side: object) -> Never:
    raise _protocol_error(
        f"Unsupported Alpaca position side {side!r}.",
        operation="map_position",
    )


def _protocol_error(message: str, *, operation: str) -> ProviderProtocolError:
    return ProviderProtocolError(
        message,
        provider=ALPACA_PROVIDER_KEY,
        operation=operation,
    )
