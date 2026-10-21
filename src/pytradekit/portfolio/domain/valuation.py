"""Portfolio valuation helpers."""

from decimal import Decimal

from pytradekit.portfolio.domain.errors import PortfolioInvariantError
from pytradekit.portfolio.domain.position import Position
from pytradekit.shared import Currency, Money, Price


def market_value(position: Position, price: Price) -> Money:
    """Return signed market value for one position."""
    if price.currency != position.realized_pnl.currency:
        raise PortfolioInvariantError("Market price currency must match position currency.")
    return Money(position.quantity * price.value, price.currency)


def nav(*, cash: Money, position_values: tuple[Money, ...]) -> Money:
    """Return same-currency net asset value."""
    total = cash
    for value in position_values:
        total = total + value
    return total


def safe_leverage(*, gross_exposure: Money, portfolio_nav: Money) -> Decimal | None:
    """Return gross leverage, or None when NAV is not positive."""
    if gross_exposure.currency != portfolio_nav.currency:
        raise PortfolioInvariantError("Exposure and NAV currencies must match.")
    if portfolio_nav.amount <= 0:
        return None
    return gross_exposure.amount / portfolio_nav.amount


def zero_value(currency: Currency) -> Money:
    """Return zero money for valuation code."""
    return Money.zero(currency)
