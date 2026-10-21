"""BuildPortfolioSnapshot application use case."""

from collections.abc import Mapping

from pytradekit.portfolio.domain import Account, PortfolioInvariantError
from pytradekit.portfolio.domain.exposure import gross_exposure, net_exposure
from pytradekit.portfolio.domain.pnl import unrealized_pnl
from pytradekit.portfolio.domain.portfolio_snapshot import PortfolioSnapshot, PositionView
from pytradekit.portfolio.domain.valuation import market_value, nav, safe_leverage
from pytradekit.portfolio.ports import BalanceRepository, PositionRepository
from pytradekit.runtime.ports import ClockPort
from pytradekit.shared import InstrumentId, Money, Price


class BuildPortfolioSnapshot:
    """Build an immutable same-currency portfolio valuation on demand."""

    def __init__(
        self,
        *,
        positions: PositionRepository,
        balances: BalanceRepository,
        clock: ClockPort,
    ) -> None:
        self._positions = positions
        self._balances = balances
        self._clock = clock

    def execute(
        self,
        account: Account,
        *,
        prices: Mapping[InstrumentId, Price],
    ) -> PortfolioSnapshot:
        as_of = self._clock.now()
        balances = self._balances.list_for_account(account.id)
        cash_total = Money.zero(account.base_currency)
        for balance in balances:
            if balance.currency != account.base_currency:
                raise PortfolioInvariantError(
                    "Milestone 0.3 snapshot requires balances in the account base currency."
                )
            cash_total = cash_total + balance.cash

        position_views: list[PositionView] = []
        market_values: list[Money] = []
        realized_total = Money.zero(account.base_currency)
        unrealized_total = Money.zero(account.base_currency)

        for position in self._positions.list_for_account(account.id):
            if position.realized_pnl.currency != account.base_currency:
                raise PortfolioInvariantError(
                    "Milestone 0.3 snapshot requires positions in the account base currency."
                )

            realized_total = realized_total + position.realized_pnl
            if position.quantity == 0:
                value = Money.zero(account.base_currency)
                unrealized = Money.zero(account.base_currency)
                market_price = None
            else:
                try:
                    market_price = prices[position.instrument_id]
                except KeyError as exc:
                    raise PortfolioInvariantError(
                        f"Missing market price for instrument {position.instrument_id}."
                    ) from exc
                if market_price.currency != account.base_currency:
                    raise PortfolioInvariantError(
                        "Market price currency must match the account base currency."
                    )
                value = market_value(position, market_price)
                unrealized = unrealized_pnl(position, market_price)

            market_values.append(value)
            unrealized_total = unrealized_total + unrealized
            position_views.append(
                PositionView(
                    instrument_id=position.instrument_id,
                    quantity=position.quantity,
                    side=position.side,
                    average_price=position.average_price,
                    market_price=market_price,
                    market_value=value,
                    realized_pnl=position.realized_pnl,
                    unrealized_pnl=unrealized,
                )
            )

        values = tuple(market_values)
        gross = gross_exposure(values, currency=account.base_currency)
        net = net_exposure(values, currency=account.base_currency)
        portfolio_nav = nav(cash=cash_total, position_values=values)

        return PortfolioSnapshot(
            account_id=account.id,
            as_of=as_of,
            base_currency=account.base_currency,
            cash=balances,
            positions=tuple(position_views),
            nav=portfolio_nav,
            gross_exposure=gross,
            net_exposure=net,
            realized_pnl=realized_total,
            unrealized_pnl=unrealized_total,
            leverage=safe_leverage(gross_exposure=gross, portfolio_nav=portfolio_nav),
        )
