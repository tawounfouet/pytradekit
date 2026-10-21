"""Hypothetical portfolio state used for pre-trade risk."""

from dataclasses import dataclass
from decimal import Decimal

from pytradekit.orders.domain import OrderSide
from pytradekit.portfolio.domain import PortfolioSnapshot, PortfolioInvariantError
from pytradekit.portfolio.domain.valuation import safe_leverage
from pytradekit.shared import InstrumentId, Money, Price, Quantity


@dataclass(frozen=True, slots=True)
class ProjectedPortfolio:
    """Portfolio metrics if a requested order were fully filled."""

    instrument_id: InstrumentId
    current_position_quantity: Decimal
    projected_position_quantity: Decimal
    order_notional: Money
    projected_cash: Money
    nav: Money
    gross_exposure: Money
    net_exposure: Money
    leverage: Decimal | None
    risk_increasing: bool


def project_portfolio(
    current: PortfolioSnapshot,
    *,
    instrument_id: InstrumentId,
    side: OrderSide,
    quantity: Quantity,
    reference_price: Price,
) -> ProjectedPortfolio:
    """Project a deterministic full-fill outcome without mutating current state."""
    if reference_price.currency != current.base_currency:
        raise PortfolioInvariantError(
            "Risk projection price must use the portfolio base currency."
        )

    current_quantity = Decimal("0")
    current_value = Money.zero(current.base_currency)
    for position in current.positions:
        if position.instrument_id == instrument_id:
            current_quantity = position.quantity
            current_value = position.market_value
            break

    signed_delta = quantity.value if side is OrderSide.BUY else -quantity.value
    projected_quantity = current_quantity + signed_delta
    order_notional = Money(
        abs(quantity.value * reference_price.value),
        current.base_currency,
    )
    projected_value = Money(
        projected_quantity * reference_price.value,
        current.base_currency,
    )

    cash_total = Money.zero(current.base_currency)
    for balance in current.cash:
        cash_total = cash_total + balance.cash
    if side is OrderSide.BUY:
        projected_cash = cash_total - order_notional
    else:
        projected_cash = cash_total + order_notional

    gross_amount = (
        current.gross_exposure.amount
        - abs(current_value.amount)
        + abs(projected_value.amount)
    )
    net_amount = (
        current.net_exposure.amount
        - current_value.amount
        + projected_value.amount
    )
    gross = Money(gross_amount, current.base_currency)
    net = Money(net_amount, current.base_currency)

    projected_nav = Money(
        current.nav.amount
        - current_value.amount
        + projected_value.amount
        + projected_cash.amount
        - cash_total.amount,
        current.base_currency,
    )
    leverage = safe_leverage(gross_exposure=gross, portfolio_nav=projected_nav)
    risk_increasing = (
        abs(projected_quantity) > abs(current_quantity)
        or gross.amount > current.gross_exposure.amount
    )

    return ProjectedPortfolio(
        instrument_id=instrument_id,
        current_position_quantity=current_quantity,
        projected_position_quantity=projected_quantity,
        order_notional=order_notional,
        projected_cash=projected_cash,
        nav=projected_nav,
        gross_exposure=gross,
        net_exposure=net,
        leverage=leverage,
        risk_increasing=risk_increasing,
    )
