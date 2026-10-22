"""Explicit side-effect boundary for reconciliation resolutions."""

from typing import Protocol

from pytradekit.reconciliation.domain import (
    BrokerSnapshot,
    Mismatch,
    Resolution,
    ResolutionType,
)


class ResolutionExecutorPort(Protocol):
    """Apply only resolution types explicitly supported by an adapter."""

    def supports(self, resolution_type: ResolutionType) -> bool: ...

    def apply(
        self,
        *,
        resolution: Resolution,
        mismatch: Mismatch,
        broker_snapshot: BrokerSnapshot,
    ) -> None: ...
