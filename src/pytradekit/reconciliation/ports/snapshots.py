"""Snapshot capture ports owned by reconciliation."""

from typing import Protocol

from pytradekit.portfolio.domain import AccountId
from pytradekit.reconciliation.domain import (
    BrokerSnapshot,
    InternalSnapshot,
    ReconciliationScope,
)


class InternalSnapshotPort(Protocol):
    """Capture durable canonical PyTradeKit state."""

    def capture(
        self,
        *,
        account_id: AccountId,
        scope: ReconciliationScope,
    ) -> InternalSnapshot: ...


class BrokerSnapshotPort(Protocol):
    """Capture normalized external broker truth."""

    def capture(
        self,
        *,
        account_id: AccountId,
        scope: ReconciliationScope,
    ) -> BrokerSnapshot: ...
