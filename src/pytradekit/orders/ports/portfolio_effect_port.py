"""Consumer-owned portfolio effect port for execution fills."""

from typing import Protocol

from pytradekit.execution import Fill
from pytradekit.orders.domain import OrderSide
from pytradekit.portfolio.domain.account_id import AccountId
from pytradekit.shared import InstrumentId


class PortfolioEffectPort(Protocol):
    """Boundary used by Orders to forward accepted fill facts to Portfolio."""

    def apply_fill(
        self,
        fill: Fill,
        *,
        account_id: AccountId,
        instrument_id: InstrumentId,
        side: OrderSide,
    ) -> bool:
        ...
