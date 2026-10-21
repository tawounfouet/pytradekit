"""Inputs supplied to pure risk rules."""

from dataclasses import dataclass
from datetime import datetime

from pytradekit.orders.domain import OrderSide, OrderType
from pytradekit.portfolio.domain import PortfolioSnapshot
from pytradekit.risk.domain.projected_portfolio import ProjectedPortfolio
from pytradekit.risk.domain.risk_scope import RiskScope
from pytradekit.shared import InstrumentId, Money, Price, Quantity, require_utc_datetime


@dataclass(frozen=True, slots=True)
class RiskOrder:
    """Broker-neutral order facts needed by pre-trade risk."""

    instrument_id: InstrumentId
    side: OrderSide
    order_type: OrderType
    quantity: Quantity
    reference_price: Price


@dataclass(frozen=True, slots=True)
class RiskContext:
    """Deterministic context consumed by risk limits."""

    current: PortfolioSnapshot
    projected: ProjectedPortfolio
    order: RiskOrder
    evaluated_at: datetime
    scope: RiskScope
    start_of_day_nav: Money | None = None

    def __post_init__(self) -> None:
        require_utc_datetime(self.evaluated_at, field_name="RiskContext evaluated_at")
