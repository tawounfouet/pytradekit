"""Canonical broker snapshots for the generic reconciliation pipeline."""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol

from alpaca.trading.enums import QueryOrderStatus
from alpaca.trading.models import Order as AlpacaOrder
from alpaca.trading.requests import GetOrdersRequest

from pytradekit.orders.domain import OrderId
from pytradekit.portfolio.domain import AccountId
from pytradekit.reconciliation.domain import (
    BrokerSnapshot,
    CanonicalBalance,
    CanonicalOrder,
    CanonicalPosition,
    ReconciliationScope,
    SnapshotCompleteness,
    SnapshotWatermark,
)
from pytradekit.reconciliation.ports import BrokerSnapshotPort
from pytradekit.runtime.ports import ClockPort

from .contract import ALPACA_PROVIDER_KEY
from .reconciliation import AlpacaExternalActivityReader
from .snapshots import AlpacaMarketDataSnapshots


class AlpacaOrderInventoryClient(Protocol):
    """Read-only order inventory surface required for reconciliation."""

    def get_orders(self, filter: GetOrdersRequest | None = None) -> object: ...


class CanonicalOrderIdentityResolver(Protocol):
    """Map provider order identities to canonical PyTradeKit identities."""

    def resolve_order_id(
        self,
        external_order_id: str,
        client_order_id: str | None = None,
    ) -> OrderId | None: ...


class AlpacaBrokerSnapshotPort(BrokerSnapshotPort):
    """Compose normalized Alpaca account, order, fill, position, and cash facts."""

    def __init__(
        self,
        *,
        snapshots: AlpacaMarketDataSnapshots,
        orders_client: AlpacaOrderInventoryClient,
        fills: AlpacaExternalActivityReader,
        identities: CanonicalOrderIdentityResolver,
        clock: ClockPort,
    ) -> None:
        self._snapshots = snapshots
        self._orders_client = orders_client
        self._fills = fills
        self._identities = identities
        self._clock = clock

    def capture(
        self,
        *,
        account_id: AccountId,
        scope: ReconciliationScope,
    ) -> BrokerSnapshot:
        captured_at = self._clock.now()
        completeness = SnapshotCompleteness.COMPLETE
        orders: tuple[CanonicalOrder, ...] = ()
        fills = ()
        positions: tuple[CanonicalPosition, ...] = ()
        balances: tuple[CanonicalBalance, ...] = ()

        if scope in {ReconciliationScope.ORDERS, ReconciliationScope.FULL}:
            try:
                orders = self._capture_orders()
            except Exception:
                completeness = SnapshotCompleteness.PARTIAL

        if scope in {ReconciliationScope.FILLS, ReconciliationScope.FULL}:
            try:
                fills = self._fills.list_fills()
            except Exception:
                completeness = SnapshotCompleteness.PARTIAL

        if scope in {ReconciliationScope.POSITIONS, ReconciliationScope.FULL}:
            try:
                provider_positions = self._snapshots.get_position_snapshots()
                positions = tuple(
                    CanonicalPosition(
                        instrument_id=item.instrument_id,
                        quantity=item.signed_quantity,
                        average_price=item.average_price.value,
                        currency=item.average_price.currency,
                    )
                    for item in provider_positions
                )
            except Exception:
                completeness = SnapshotCompleteness.PARTIAL

        if scope in {
            ReconciliationScope.ACCOUNT,
            ReconciliationScope.BALANCES,
            ReconciliationScope.FULL,
        }:
            try:
                account = self._snapshots.get_account_snapshot()
                if account.cash_balance is not None:
                    balances = (
                        CanonicalBalance(
                            currency=account.cash_balance.currency,
                            cash=account.cash_balance.cash.amount,
                        ),
                    )
            except Exception:
                completeness = SnapshotCompleteness.PARTIAL

        return BrokerSnapshot(
            account_id=account_id,
            provider=ALPACA_PROVIDER_KEY,
            orders=orders,
            fills=fills,
            positions=positions,
            balances=balances,
            captured_at=captured_at,
            watermark=SnapshotWatermark(
                captured_at=captured_at,
                provider_as_of=captured_at,
            ),
            completeness=completeness,
        )

    def _capture_orders(self) -> tuple[CanonicalOrder, ...]:
        raw = self._orders_client.get_orders(
            GetOrdersRequest(
                status=QueryOrderStatus.ALL,
                limit=500,
                nested=False,
            )
        )
        if not isinstance(raw, list):
            raise TypeError("Alpaca order inventory response must be a list.")

        result: list[CanonicalOrder] = []
        for item in raw:
            if not isinstance(item, AlpacaOrder):
                raise TypeError("Alpaca order inventory contains an invalid order.")
            external_order_id = str(item.id)
            client_order_id = str(item.client_order_id or "").strip() or None
            status = _canonical_status(item)
            result.append(
                CanonicalOrder(
                    order_id=self._identities.resolve_order_id(
                        external_order_id,
                        client_order_id,
                    ),
                    client_order_id=client_order_id,
                    external_order_id=external_order_id,
                    status=status,
                    filled_quantity=Decimal(str(item.filled_qty or "0")),
                    cancel_requested=_cancel_requested(item),
                )
            )

        result.sort(
            key=lambda order: (
                order.client_order_id or "",
                order.external_order_id or "",
            )
        )
        return tuple(result)


def _canonical_status(order: AlpacaOrder) -> str:
    raw = order.status.value
    return {
        "new": "ACCEPTED",
        "accepted": "ACCEPTED",
        "partially_filled": "PARTIALLY_FILLED",
        "filled": "FILLED",
        "canceled": "CANCELLED",
        "rejected": "REJECTED",
    }.get(raw, raw.upper())


def _cancel_requested(order: AlpacaOrder) -> bool:
    return order.status.value in {"pending_cancel", "pending_replace"}
