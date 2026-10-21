"""Portfolio exposure helpers."""

from pytradekit.portfolio.domain.errors import PortfolioInvariantError
from pytradekit.shared import Currency, Money


def gross_exposure(values: tuple[Money, ...], *, currency: Currency) -> Money:
    """Return sum of absolute signed market values."""
    total = Money.zero(currency)
    for value in values:
        if value.currency != currency:
            raise PortfolioInvariantError("Exposure values must use one currency.")
        total = total + Money(abs(value.amount), currency)
    return total


def net_exposure(values: tuple[Money, ...], *, currency: Currency) -> Money:
    """Return sum of signed market values."""
    total = Money.zero(currency)
    for value in values:
        if value.currency != currency:
            raise PortfolioInvariantError("Exposure values must use one currency.")
        total = total + value
    return total
