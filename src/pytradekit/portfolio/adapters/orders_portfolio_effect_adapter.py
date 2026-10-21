"""Adapter exposing Portfolio through the Orders consumer-owned port."""

from pytradekit.execution import Fill
from pytradekit.orders.domain import OrderSide
from pytradekit.portfolio.application import ApplyFillToPortfolio
from pytradekit.portfolio.domain import AccountId
from pytradekit.shared import InstrumentId


class OrdersPortfolioEffectAdapter:
    """Forward canonical fill facts into Portfolio accounting."""

    def __init__(self, service: ApplyFillToPortfolio) -> None:
        self._service = service

    def apply_fill(
        self,
        fill: Fill,
        *,
        account_id: AccountId,
        instrument_id: InstrumentId,
        side: OrderSide,
    ) -> bool:
        result = self._service.execute(
            fill,
            account_id=account_id,
            instrument_id=instrument_id,
            side=side,
        )
        return result.applied
