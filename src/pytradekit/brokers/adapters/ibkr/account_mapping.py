"""IBKR SDK-free account, balance, and position mapping."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pytradekit.brokers import (
    ProviderAccountIdentity,
    ProviderAccountSnapshot,
    ProviderPositionSnapshot,
    ProviderProtocolError,
)
from pytradekit.portfolio.domain import Account, AccountId, Balance
from pytradekit.shared import Currency, Money, Price, require_utc_datetime

from .contract_mapping import IBKRInstrumentMappingResult
from .discovery import IBKR_PROVIDER_KEY
from .identities import IBKRContractId


class IBKRAccountMappingError(ValueError):
    """Raised when IBKR account or position evidence cannot be mapped safely."""


class IBKRAccountMetricTag(StrEnum):
    """IBKR account value tags used by the frozen LOT-05.6 scope."""

    TOTAL_CASH_VALUE = "TotalCashValue"
    NET_LIQUIDATION = "NetLiquidation"
    BUYING_POWER = "BuyingPower"
    AVAILABLE_FUNDS = "AvailableFunds"
    EQUITY_WITH_LOAN_VALUE = "EquityWithLoanValue"
    CASH_BALANCE = "CashBalance"
    EXCESS_LIQUIDITY = "ExcessLiquidity"
    INIT_MARGIN_REQ = "InitMarginReq"
    MAINT_MARGIN_REQ = "MaintMarginReq"


@dataclass(frozen=True, slots=True)
class IBKRAccountMetric:
    """One monetary IBKR account metric with its provider tag and currency."""

    tag: IBKRAccountMetricTag
    value: Decimal
    currency: Currency

    def __post_init__(self) -> None:
        if not isinstance(self.tag, IBKRAccountMetricTag):
            raise IBKRAccountMappingError(
                "tag must be an IBKRAccountMetricTag."
            )
        if (
            not isinstance(self.value, Decimal)
            or not self.value.is_finite()
        ):
            raise IBKRAccountMappingError(
                "IBKR account metric value must be a finite Decimal."
            )
        if not isinstance(self.currency, Currency):
            raise IBKRAccountMappingError(
                "IBKR account metric currency must be a Currency."
            )

    def to_money(self) -> Money:
        """Return the provider metric as canonical Money without changing semantics."""

        return Money(self.value, self.currency)


@dataclass(frozen=True, slots=True)
class IBKRAccountSummaryObservation:
    """SDK-free account summary evidence for one IBKR account."""

    external_account_id: str
    base_currency: Currency
    account_ready: bool
    metrics: tuple[IBKRAccountMetric, ...]
    observed_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "external_account_id",
            _required_text(
                self.external_account_id,
                field_name="external_account_id",
            ),
        )
        if not isinstance(self.base_currency, Currency):
            raise IBKRAccountMappingError(
                "base_currency must be a Currency."
            )
        if type(self.account_ready) is not bool:
            raise IBKRAccountMappingError("account_ready must be a bool.")
        if not isinstance(self.metrics, tuple):
            raise IBKRAccountMappingError("metrics must be a tuple.")
        seen: set[tuple[IBKRAccountMetricTag, Currency]] = set()
        for metric in self.metrics:
            if not isinstance(metric, IBKRAccountMetric):
                raise IBKRAccountMappingError(
                    "metrics must contain IBKRAccountMetric values."
                )
            key = (metric.tag, metric.currency)
            if key in seen:
                raise IBKRAccountMappingError(
                    "IBKR account metric tag/currency pairs must be unique."
                )
            seen.add(key)
        object.__setattr__(
            self,
            "observed_at",
            require_utc_datetime(
                self.observed_at,
                field_name="IBKR account observed_at",
            ),
        )

    def metric(
        self,
        tag: IBKRAccountMetricTag,
        *,
        currency: Currency | None = None,
    ) -> IBKRAccountMetric | None:
        """Return one uniquely identified provider metric."""

        target_currency = currency or self.base_currency
        matches = tuple(
            metric
            for metric in self.metrics
            if metric.tag is tag and metric.currency == target_currency
        )
        if len(matches) > 1:
            raise IBKRAccountMappingError(
                "IBKR account metric lookup is ambiguous."
            )
        return matches[0] if matches else None


@dataclass(frozen=True, slots=True)
class IBKRAccountRestrictionsObservation:
    """Explicit restriction evidence required by ProviderAccountSnapshot."""

    trading_blocked: bool
    account_blocked: bool
    evidence_source: str

    def __post_init__(self) -> None:
        if type(self.trading_blocked) is not bool:
            raise IBKRAccountMappingError("trading_blocked must be a bool.")
        if type(self.account_blocked) is not bool:
            raise IBKRAccountMappingError("account_blocked must be a bool.")
        object.__setattr__(
            self,
            "evidence_source",
            _required_text(
                self.evidence_source,
                field_name="evidence_source",
            ),
        )


@dataclass(frozen=True, slots=True)
class IBKRAccountMappingResult:
    """Canonical account snapshot plus retained IBKR-only financial metrics."""

    snapshot: ProviderAccountSnapshot
    total_cash_value: Money | None
    net_liquidation: Money | None
    buying_power: Money | None
    available_funds: Money | None
    equity_with_loan_value: Money | None
    cash_balance: Money | None
    excess_liquidity: Money | None
    init_margin_requirement: Money | None
    maintenance_margin_requirement: Money | None
    restriction_evidence_source: str

    def __post_init__(self) -> None:
        if not isinstance(self.snapshot, ProviderAccountSnapshot):
            raise IBKRAccountMappingError(
                "snapshot must be a ProviderAccountSnapshot."
            )
        _required_text(
            self.restriction_evidence_source,
            field_name="restriction_evidence_source",
        )


@dataclass(frozen=True, slots=True)
class IBKRPortfolioPositionObservation:
    """SDK-free TWS position/portfolio observation for the frozen STK scope."""

    external_account_id: str
    contract_id: IBKRContractId
    symbol: str
    currency: Currency
    signed_quantity: Decimal
    average_cost: Decimal
    market_price: Decimal | None
    market_value: Decimal | None
    unrealized_pnl: Decimal | None
    realized_pnl: Decimal | None
    observed_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "external_account_id",
            _required_text(
                self.external_account_id,
                field_name="external_account_id",
            ),
        )
        if not isinstance(self.contract_id, IBKRContractId):
            raise IBKRAccountMappingError(
                "contract_id must be an IBKRContractId."
            )
        object.__setattr__(
            self,
            "symbol",
            _required_text(self.symbol, field_name="symbol"),
        )
        if not isinstance(self.currency, Currency):
            raise IBKRAccountMappingError(
                "currency must be a Currency."
            )
        if (
            not isinstance(self.signed_quantity, Decimal)
            or not self.signed_quantity.is_finite()
            or self.signed_quantity == 0
        ):
            raise IBKRAccountMappingError(
                "signed_quantity must be a finite non-zero Decimal."
            )
        object.__setattr__(
            self,
            "average_cost",
            _positive_decimal(
                self.average_cost,
                field_name="average_cost",
            ),
        )
        object.__setattr__(
            self,
            "market_price",
            _optional_positive_decimal(
                self.market_price,
                field_name="market_price",
            ),
        )
        object.__setattr__(
            self,
            "market_value",
            _optional_finite_decimal(
                self.market_value,
                field_name="market_value",
            ),
        )
        object.__setattr__(
            self,
            "unrealized_pnl",
            _optional_finite_decimal(
                self.unrealized_pnl,
                field_name="unrealized_pnl",
            ),
        )
        object.__setattr__(
            self,
            "realized_pnl",
            _optional_finite_decimal(
                self.realized_pnl,
                field_name="realized_pnl",
            ),
        )
        object.__setattr__(
            self,
            "observed_at",
            require_utc_datetime(
                self.observed_at,
                field_name="IBKR position observed_at",
            ),
        )


@dataclass(frozen=True, slots=True)
class IBKRPositionMappingResult:
    """Canonical position snapshot plus retained provider-only position facts."""

    snapshot: ProviderPositionSnapshot
    provider_realized_pnl: Money | None

    def __post_init__(self) -> None:
        if not isinstance(self.snapshot, ProviderPositionSnapshot):
            raise IBKRAccountMappingError(
                "snapshot must be a ProviderPositionSnapshot."
            )


def map_ibkr_account_snapshot(
    observation: IBKRAccountSummaryObservation,
    *,
    account_id: AccountId,
    restrictions: IBKRAccountRestrictionsObservation,
) -> IBKRAccountMappingResult:
    """Map IBKR account metrics without collapsing distinct financial semantics."""

    if not isinstance(observation, IBKRAccountSummaryObservation):
        raise IBKRAccountMappingError(
            "observation must be an IBKRAccountSummaryObservation."
        )
    if not isinstance(account_id, AccountId):
        raise IBKRAccountMappingError("account_id must be an AccountId.")
    if not isinstance(restrictions, IBKRAccountRestrictionsObservation):
        raise IBKRAccountMappingError(
            "restrictions must be an IBKRAccountRestrictionsObservation."
        )
    if not observation.account_ready:
        raise _protocol_error(
            "IBKR account is not ready; account values may be stale or incorrect."
        )

    total_cash_value = _base_money(
        observation,
        IBKRAccountMetricTag.TOTAL_CASH_VALUE,
    )
    net_liquidation = _base_money(
        observation,
        IBKRAccountMetricTag.NET_LIQUIDATION,
    )
    buying_power = _base_money(
        observation,
        IBKRAccountMetricTag.BUYING_POWER,
    )
    available_funds = _base_money(
        observation,
        IBKRAccountMetricTag.AVAILABLE_FUNDS,
    )
    equity_with_loan_value = _base_money(
        observation,
        IBKRAccountMetricTag.EQUITY_WITH_LOAN_VALUE,
    )
    cash_balance = _base_money(
        observation,
        IBKRAccountMetricTag.CASH_BALANCE,
    )
    excess_liquidity = _base_money(
        observation,
        IBKRAccountMetricTag.EXCESS_LIQUIDITY,
    )
    init_margin_requirement = _base_money(
        observation,
        IBKRAccountMetricTag.INIT_MARGIN_REQ,
    )
    maintenance_margin_requirement = _base_money(
        observation,
        IBKRAccountMetricTag.MAINT_MARGIN_REQ,
    )

    canonical_account = Account(
        id=account_id,
        base_currency=observation.base_currency,
    )
    canonical_cash = (
        Balance(
            account_id=account_id,
            currency=observation.base_currency,
            cash=total_cash_value,
            available=None,
            reserved=None,
            updated_at=observation.observed_at,
        )
        if total_cash_value is not None
        else None
    )
    snapshot = ProviderAccountSnapshot(
        identity=ProviderAccountIdentity(
            provider=IBKR_PROVIDER_KEY,
            external_account_id=observation.external_account_id,
        ),
        account=canonical_account,
        cash_balance=canonical_cash,
        equity=net_liquidation,
        buying_power=buying_power,
        portfolio_value=None,
        trading_blocked=restrictions.trading_blocked,
        account_blocked=restrictions.account_blocked,
        observed_at=observation.observed_at,
    )
    return IBKRAccountMappingResult(
        snapshot=snapshot,
        total_cash_value=total_cash_value,
        net_liquidation=net_liquidation,
        buying_power=buying_power,
        available_funds=available_funds,
        equity_with_loan_value=equity_with_loan_value,
        cash_balance=cash_balance,
        excess_liquidity=excess_liquidity,
        init_margin_requirement=init_margin_requirement,
        maintenance_margin_requirement=maintenance_margin_requirement,
        restriction_evidence_source=restrictions.evidence_source,
    )


def map_ibkr_position_snapshot(
    observation: IBKRPortfolioPositionObservation,
    *,
    account_id: AccountId,
    expected_external_account_id: str,
    instrument: IBKRInstrumentMappingResult,
) -> IBKRPositionMappingResult:
    """Map one IBKR STK position without fabricating availability semantics."""

    if not isinstance(observation, IBKRPortfolioPositionObservation):
        raise IBKRAccountMappingError(
            "observation must be an IBKRPortfolioPositionObservation."
        )
    if not isinstance(account_id, AccountId):
        raise IBKRAccountMappingError("account_id must be an AccountId.")
    if not isinstance(instrument, IBKRInstrumentMappingResult):
        raise IBKRAccountMappingError(
            "instrument must be an IBKRInstrumentMappingResult."
        )

    expected_account = _required_text(
        expected_external_account_id,
        field_name="expected_external_account_id",
    )
    if observation.external_account_id != expected_account:
        raise _protocol_error(
            "IBKR position account does not match the canonical account mapping."
        )
    if str(observation.contract_id) != instrument.identity.external_id:
        raise _protocol_error(
            "IBKR position conId does not match the resolved provider instrument."
        )
    if observation.symbol != instrument.identity.external_symbol:
        raise _protocol_error(
            "IBKR position symbol does not match the resolved provider instrument."
        )
    if observation.currency != instrument.instrument.quote_currency:
        raise _protocol_error(
            "IBKR position currency does not match the resolved instrument."
        )

    cost_basis = Money(
        abs(observation.signed_quantity) * observation.average_cost,
        observation.currency,
    )
    snapshot = ProviderPositionSnapshot(
        account_id=account_id,
        instrument_id=instrument.instrument.id,
        provider_instrument=instrument.identity,
        signed_quantity=observation.signed_quantity,
        average_price=Price(
            observation.average_cost,
            observation.currency,
        ),
        market_value=(
            Money(observation.market_value, observation.currency)
            if observation.market_value is not None
            else None
        ),
        cost_basis=cost_basis,
        unrealized_pnl=(
            Money(observation.unrealized_pnl, observation.currency)
            if observation.unrealized_pnl is not None
            else None
        ),
        current_price=(
            Price(observation.market_price, observation.currency)
            if observation.market_price is not None
            else None
        ),
        available_quantity=None,
        observed_at=observation.observed_at,
    )
    return IBKRPositionMappingResult(
        snapshot=snapshot,
        provider_realized_pnl=(
            Money(observation.realized_pnl, observation.currency)
            if observation.realized_pnl is not None
            else None
        ),
    )


def _base_money(
    observation: IBKRAccountSummaryObservation,
    tag: IBKRAccountMetricTag,
) -> Money | None:
    metric = observation.metric(tag, currency=observation.base_currency)
    return None if metric is None else metric.to_money()


def _required_text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise IBKRAccountMappingError(f"{field_name} must be a string.")
    normalized = value.strip()
    if not normalized:
        raise IBKRAccountMappingError(f"{field_name} must be non-empty.")
    return normalized


def _positive_decimal(value: object, *, field_name: str) -> Decimal:
    if (
        not isinstance(value, Decimal)
        or not value.is_finite()
        or value <= 0
    ):
        raise IBKRAccountMappingError(
            f"{field_name} must be a finite positive Decimal."
        )
    return value


def _optional_positive_decimal(
    value: object,
    *,
    field_name: str,
) -> Decimal | None:
    if value is None:
        return None
    return _positive_decimal(value, field_name=field_name)


def _optional_finite_decimal(
    value: object,
    *,
    field_name: str,
) -> Decimal | None:
    if value is None:
        return None
    if not isinstance(value, Decimal) or not value.is_finite():
        raise IBKRAccountMappingError(
            f"{field_name} must be a finite Decimal or None."
        )
    return value


def _protocol_error(message: str) -> ProviderProtocolError:
    return ProviderProtocolError(
        message,
        provider=IBKR_PROVIDER_KEY,
        operation="account_position_mapping",
    )
