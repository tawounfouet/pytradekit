"""Unit tests for the milestone 0.8 broker compliance contract models."""

from dataclasses import replace

import pytest

from pytradekit.brokers.compliance import (
    BROKER_ADAPTER_CONTRACT_V1_CANDIDATE,
    BrokerCapability,
    CapabilityConstraint,
    CapabilitySupport,
    CertificationLevel,
    ProviderCapabilityManifest,
)
from pytradekit.orders.domain import OrderType, TimeInForce
from pytradekit.reference import AssetClass
from pytradekit.runtime import RuntimeEnvironment


def _market_support() -> CapabilitySupport:
    return CapabilitySupport(
        capability=BrokerCapability.MARKET_ORDER,
        constraints=CapabilityConstraint(
            asset_classes=frozenset({AssetClass.EQUITY}),
            order_types=frozenset({OrderType.MARKET}),
            time_in_force=frozenset({TimeInForce.DAY}),
            environments=frozenset({RuntimeEnvironment.PAPER}),
            account_modes=frozenset({"cash"}),
        ),
    )


def _manifest() -> ProviderCapabilityManifest:
    return ProviderCapabilityManifest(
        provider="example",
        environment=RuntimeEnvironment.PAPER,
        adapter_version="0.8.0a1",
        account_mode="cash",
        asset_classes=frozenset({AssetClass.EQUITY}),
        supported_order_types=frozenset({OrderType.MARKET}),
        supported_time_in_force=frozenset({TimeInForce.DAY}),
        capabilities=(
            _market_support(),
            CapabilitySupport(BrokerCapability.ACCOUNT_QUERY),
            CapabilitySupport(BrokerCapability.ORDER_QUERY),
            CapabilitySupport(BrokerCapability.CANCEL_ORDER),
            CapabilitySupport(BrokerCapability.CLIENT_ORDER_REFERENCE),
            CapabilitySupport(BrokerCapability.EXECUTION_FACTS),
        ),
        stream_model="push",
        session_model="request-response",
        sdk_name="example-sdk",
        sdk_version="1.2.3",
        known_limitations=("PAPER only",),
    )


def test_certification_levels_are_monotonic() -> None:
    assert CertificationLevel.C0_DEFINED < CertificationLevel.C1_IMPLEMENTED
    assert CertificationLevel.C2_INTEGRATION_QUALIFIED < CertificationLevel.C3_PAPER_QUALIFIED
    assert CertificationLevel.C3_PAPER_QUALIFIED.code == "C3"


def test_manifest_exposes_capability_specific_claims_without_certification() -> None:
    manifest = _manifest()

    assert manifest.provider == "example"
    assert manifest.supports(BrokerCapability.MARKET_ORDER)
    assert manifest.supports_cancel
    assert manifest.supports_client_reference
    assert manifest.supports_execution_event_ids
    assert not manifest.supports_replace
    assert not manifest.supports_market_data
    assert manifest.support_for(BrokerCapability.MARKET_ORDER) == _market_support()

    BROKER_ADAPTER_CONTRACT_V1_CANDIDATE.validate_manifest(manifest)


def test_manifest_rejects_duplicate_capability_declarations() -> None:
    manifest = _manifest()

    with pytest.raises(ValueError, match="Duplicate capability declaration"):
        replace(
            manifest,
            capabilities=(
                CapabilitySupport(BrokerCapability.ACCOUNT_QUERY),
                CapabilitySupport(BrokerCapability.ACCOUNT_QUERY),
            ),
        )


def test_manifest_rejects_capability_constraints_outside_provider_envelope() -> None:
    manifest = _manifest()
    invalid = CapabilitySupport(
        capability=BrokerCapability.LIMIT_ORDER,
        constraints=CapabilityConstraint(
            order_types=frozenset({OrderType.LIMIT}),
        ),
    )

    with pytest.raises(ValueError, match="order constraints exceed"):
        replace(
            manifest,
            capabilities=(invalid,),
        )


def test_manifest_requires_sdk_name_and_version_together() -> None:
    manifest = _manifest()

    with pytest.raises(ValueError, match="declared together"):
        replace(manifest, sdk_version=None)


def test_manifest_to_dict_is_stable_and_contains_no_certification_claim() -> None:
    payload = _manifest().to_dict()

    assert payload["provider"] == "example"
    assert payload["environment"] == "PAPER"
    assert "certification" not in payload
