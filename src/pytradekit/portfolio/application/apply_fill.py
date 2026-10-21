"""ApplyFillToPortfolio application use case."""

from dataclasses import dataclass

from pytradekit.execution import Fill
from pytradekit.orders.domain import OrderSide
from pytradekit.portfolio.domain import (
    AccountId,
    Balance,
    BalanceNotFoundError,
    PortfolioInvariantError,
    Position,
)
from pytradekit.portfolio.ports import BalanceRepository, PositionRepository, ProcessedFillRegistry
from pytradekit.shared import InstrumentId


@dataclass(frozen=True, slots=True)
class ApplyFillResult:
    """Result of one portfolio fill application."""

    applied: bool
    position: Position
    balance: Balance


class ApplyFillToPortfolio:
    """Turn one immutable Fill into exactly one portfolio economic effect."""

    def __init__(
        self,
        *,
        positions: PositionRepository,
        balances: BalanceRepository,
        processed_fills: ProcessedFillRegistry,
    ) -> None:
        self._positions = positions
        self._balances = balances
        self._processed_fills = processed_fills

    def execute(
        self,
        fill: Fill,
        *,
        account_id: AccountId,
        instrument_id: InstrumentId,
        side: OrderSide,
    ) -> ApplyFillResult:
        balance = self._balances.get(account_id, fill.price.currency)
        if balance is None:
            message = (
                f"Balance for account {account_id} and currency "
                f"{fill.price.currency} was not found."
            )
            raise BalanceNotFoundError(message)

        position = self._positions.get(account_id, instrument_id)
        if position is None:
            position = Position.flat(
                account_id=account_id,
                instrument_id=instrument_id,
                currency=fill.price.currency,
                occurred_at=fill.occurred_at,
            )

        if self._processed_fills.contains(fill.deduplication_key):
            return ApplyFillResult(applied=False, position=position, balance=balance)

        if fill.fee is not None and fill.fee.currency != balance.currency:
            raise PortfolioInvariantError(
                "Fill fee currency must match accounting balance currency."
            )

        position.apply_fill(
            side=side,
            quantity=fill.quantity,
            price=fill.price,
            occurred_at=fill.occurred_at,
        )

        notional = fill.price * fill.quantity
        if side is OrderSide.BUY:
            balance = balance.debit(notional, updated_at=fill.occurred_at)
        else:
            balance = balance.credit(notional, updated_at=fill.occurred_at)

        if fill.fee is not None:
            balance = balance.debit(fill.fee, updated_at=fill.occurred_at)

        self._positions.save(position)
        self._balances.save(balance)
        self._processed_fills.mark(fill.deduplication_key)
        return ApplyFillResult(applied=True, position=position, balance=balance)
