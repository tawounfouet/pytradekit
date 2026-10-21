"""Portfolio profit and loss helpers."""

from decimal import Decimal

from pytradekit.portfolio.domain.errors import PortfolioInvariantError
from pytradekit.portfolio.domain.position import Position
from pytradekit.shared import Money, Price


def unrealized_pnl(position: Position, market_price: Price) -> Money:
    """Return unrealized PnL for a position at the supplied market price."""
    if market_price.currency != position.realized_pnl.currency:
        raise PortfolioInvariantError("Market price currency must match position currency.")
    if position.quantity == 0:
        return Money.zero(market_price.currency)

    average = position.average_price
    if average is None:
        raise PortfolioInvariantError("Open position requires an average price.")

    quantity = abs(position.quantity)
    if position.quantity > 0:
        amount = (market_price.value - average.value) * quantity
    else:
        amount = (average.value - market_price.value) * quantity
    return Money(amount, market_price.currency)


def daily_pnl(*, start_of_day_nav: Money, current_nav: Money) -> Money:
    """Return mark-to-market daily PnL from a deterministic NAV baseline."""
    if start_of_day_nav.currency != current_nav.currency:
        raise PortfolioInvariantError("Daily PnL NAV currencies must match.")
    return current_nav - start_of_day_nav


def daily_return(*, start_of_day_nav: Money, current_nav: Money) -> Decimal:
    """Return daily PnL as a fraction of start-of-day NAV."""
    if start_of_day_nav.amount <= 0:
        raise PortfolioInvariantError("Start-of-day NAV must be positive.")
    return daily_pnl(
        start_of_day_nav=start_of_day_nav,
        current_nav=current_nav,
    ).amount / start_of_day_nav.amount
