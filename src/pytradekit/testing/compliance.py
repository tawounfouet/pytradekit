"""Deterministic broker compliance fixtures for tests and qualification suites."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from pytradekit.brokers import ProviderAccountIdentity
from pytradekit.brokers.compliance import (
    BrokerCapability,
    CapabilityConstraint,
    CapabilitySupport,
    ComplianceObservation,
    ComplianceScenario,
    ComplianceStatus,
    ProviderCapabilityManifest,
    ProviderFixture,
)
from pytradekit.orders.domain import OrderType, TimeInForce
from pytradekit.orders.ports import ExecutionPort
from pytradekit.reconciliation.ports import BrokerSnapshotPort
from pytradekit.reference import AssetClass
from pytradekit.runtime import RuntimeEnvironment


def compliance_manifest(
    provider: str = "provider-a",
    *,
    adapter_version: str = "0.8.0a2",
) -> ProviderCapabilityManifest:
    """Build a minimal PAPER manifest for common harness tests."""

    return ProviderCapabilityManifest(
        provider=provider,
        environment=RuntimeEnvironment.PAPER,
        adapter_version=adapter_version,
        account_mode="cash",
        asset_classes=frozenset({AssetClass.EQUITY}),
        supported_order_types=frozenset({OrderType.MARKET}),
        supported_time_in_force=frozenset({TimeInForce.DAY}),
        capabilities=(
            CapabilitySupport(
                capability=BrokerCapability.MARKET_ORDER,
                constraints=CapabilityConstraint(
                    asset_classes=frozenset({AssetClass.EQUITY}),
                    order_types=frozenset({OrderType.MARKET}),
                    time_in_force=frozenset({TimeInForce.DAY}),
                    environments=frozenset({RuntimeEnvironment.PAPER}),
                    account_modes=frozenset({"cash"}),
                ),
            ),
        ),
        stream_model="push",
        session_model="request-response",
        sdk_name="provider-sdk",
        sdk_version="1.0.0",
        known_limitations=("PAPER only",),
    )


@dataclass(slots=True)
class FakeProviderFixture:
    """Minimal structural ProviderFixture with observable cleanup behavior."""

    manifest: ProviderCapabilityManifest
    cleanup_should_fail: bool = False
    cleanup_calls: int = 0

    def provider_manifest(self) -> ProviderCapabilityManifest:
        return self.manifest

    def build_runtime(self) -> object:
        return object()

    def build_execution_adapter(self) -> ExecutionPort:
        return cast(ExecutionPort, object())

    def build_snapshot_adapter(self) -> BrokerSnapshotPort:
        return cast(BrokerSnapshotPort, object())

    def paper_account_fixture(self) -> ProviderAccountIdentity:
        return ProviderAccountIdentity(
            provider=self.manifest.provider,
            external_account_id="paper-account",
        )

    def cleanup(self) -> None:
        self.cleanup_calls += 1
        if self.cleanup_should_fail:
            raise RuntimeError("cleanup failed")


def pass_compliance_executor(
    fixture: ProviderFixture,
    scenario: ComplianceScenario,
) -> ComplianceObservation:
    """Return provider-neutral passing evidence of the required scenario type."""

    del fixture
    return ComplianceObservation(
        status=ComplianceStatus.PASS,
        evidence_type=scenario.required_evidence[0],
        payload={"observed": "expected", "scenario": scenario.scenario_id},
    )
