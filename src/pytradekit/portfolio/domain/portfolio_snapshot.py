"""Immutable portfolio read model."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from pytradekit.portfolio.domain.account_id import AccountId
from pytradekit.portfolio.domain.balance import Balance
from pytradekit.portfolio.domain.position_side import PositionSide
from pytradekit.shared import Currency, InstrumentId, Money, Price, require_utc_datetime


@dataclass(frozen=True, slots=True)
class PositionView:
    """Read-only valuation of one canonical position."""

    instrument_id: InstrumentId
    quantity: Decimal
    side: PositionSide
    average_price: Price | None
    market_price: Price | None
    market_value: Money
    realized_pnl: Money
    unrealized_pnl: Money


@dataclass(frozen=True, slots=True)
class PortfolioSnapshot:
    """Immutable portfolio state as of one timestamp."""

    account_id: AccountId
    as_of: datetime
    base_currency: Currency
    cash: tuple[Balance, ...]
    positions: tuple[PositionView, ...]
    nav: Money
    gross_exposure: Money
    net_exposure: Money
    realized_pnl: Money
    unrealized_pnl: Money
    leverage: Decimal | None

    def __post_init__(self) -> None:
        require_utc_datetime(self.as_of, field_name="PortfolioSnapshot as_of")
