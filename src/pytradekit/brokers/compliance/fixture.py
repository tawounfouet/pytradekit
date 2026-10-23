"""Provider fixture protocol consumed by the future compliance harness."""

from typing import Protocol

from pytradekit.brokers.models import ProviderAccountIdentity
from pytradekit.orders.ports import ExecutionPort
from pytradekit.reconciliation.ports import BrokerSnapshotPort

from .manifest import ProviderCapabilityManifest


class ProviderFixture(Protocol):
    """Factory surface shared by provider-specific compliance fixtures."""

    def provider_manifest(self) -> ProviderCapabilityManifest:
        """Return the provider declaration under qualification."""

        ...

    def build_runtime(self) -> object:
        """Build the provider-specific runtime composition for qualification."""

        ...

    def build_execution_adapter(self) -> ExecutionPort:
        """Build the canonical execution port implementation."""

        ...

    def build_snapshot_adapter(self) -> BrokerSnapshotPort:
        """Build the canonical broker snapshot port implementation."""

        ...

    def paper_account_fixture(self) -> ProviderAccountIdentity:
        """Return external PAPER account evidence for the qualification fixture."""

        ...

    def cleanup(self) -> None:
        """Restore the provider fixture to its controlled baseline."""

        ...
