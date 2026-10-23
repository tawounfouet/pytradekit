"""IBKR capability declaration for the 0.8 anti-corruption layer."""

from __future__ import annotations

from pytradekit.brokers.compliance import (
    BrokerCapability,
    CapabilityConstraint,
    CapabilitySupport,
    ProviderCapabilityManifest,
)
from pytradekit.orders.domain import OrderType, TimeInForce
from pytradekit.reference.domain import AssetClass
from pytradekit.runtime import RuntimeEnvironment

from .discovery import IBKR_PROVIDER_KEY

IBKR_ACL_ADAPTER_VERSION = "0.8.0b1-lot05.7"

IBKR_ACL_DECLARED_CAPABILITIES: tuple[BrokerCapability, ...] = (
    BrokerCapability.ACCOUNT_QUERY,
    BrokerCapability.ORDER_QUERY,
    BrokerCapability.MARKET_ORDER,
    BrokerCapability.LIMIT_ORDER,
    BrokerCapability.CANCEL_ORDER,
    BrokerCapability.PARTIAL_FILL,
    BrokerCapability.POSITION_QUERY,
    BrokerCapability.BALANCE_QUERY,
    BrokerCapability.CLIENT_ORDER_REFERENCE,
    BrokerCapability.EXECUTION_FACTS,
    BrokerCapability.RECONNECT_RECOVERY,
)


def build_ibkr_capability_manifest() -> ProviderCapabilityManifest:
    """Build the conservative IBKR PAPER capability declaration for LOT-05.7."""

    paper_equity = CapabilityConstraint(
        asset_classes=frozenset({AssetClass.EQUITY}),
        environments=frozenset({RuntimeEnvironment.PAPER}),
        account_modes=frozenset({"paper"}),
        required_settings=("paper_endpoint_verified=true",),
        notes=(
            "US equities only.",
            "Declaration is not certification.",
        ),
    )
    market_order = CapabilityConstraint(
        asset_classes=paper_equity.asset_classes,
        order_types=frozenset({OrderType.MARKET}),
        time_in_force=frozenset({TimeInForce.DAY}),
        environments=paper_equity.environments,
        account_modes=paper_equity.account_modes,
        required_settings=(
            "paper_endpoint_verified=true",
            "api_read_only=false",
        ),
        notes=("Regular-hours-only frozen order command mapping.",),
    )
    limit_order = CapabilityConstraint(
        asset_classes=paper_equity.asset_classes,
        order_types=frozenset({OrderType.LIMIT}),
        time_in_force=frozenset({TimeInForce.DAY}),
        environments=paper_equity.environments,
        account_modes=paper_equity.account_modes,
        required_settings=(
            "paper_endpoint_verified=true",
            "api_read_only=false",
        ),
        notes=(
            "Regular-hours-only frozen order command mapping.",
            "Dynamic market-rule pricing remains provider-specific.",
        ),
    )
    cancel_order = CapabilityConstraint(
        asset_classes=paper_equity.asset_classes,
        order_types=frozenset({OrderType.MARKET, OrderType.LIMIT}),
        time_in_force=frozenset({TimeInForce.DAY}),
        environments=paper_equity.environments,
        account_modes=paper_equity.account_modes,
        required_settings=(
            "paper_endpoint_verified=true",
            "api_read_only=false",
        ),
        notes=("PendingCancel is not terminal cancellation.",),
    )
    reconnect = CapabilityConstraint(
        asset_classes=paper_equity.asset_classes,
        environments=paper_equity.environments,
        account_modes=paper_equity.account_modes,
        required_settings=(
            "maintainAndResubmitOrdersOnReconnect=false",
            "reconciliation_complete=true",
        ),
        notes=(
            "Connectivity restoration never implies safe economic-write replay.",
            "Code 1101 requires market-data resubscription.",
        ),
    )
    execution_facts = CapabilityConstraint(
        asset_classes=paper_equity.asset_classes,
        environments=paper_equity.environments,
        account_modes=paper_equity.account_modes,
        notes=(
            "execId is the provider execution identity.",
            "Execution corrections require reconciliation.",
        ),
    )

    scoped = {
        BrokerCapability.MARKET_ORDER: market_order,
        BrokerCapability.LIMIT_ORDER: limit_order,
        BrokerCapability.CANCEL_ORDER: cancel_order,
        BrokerCapability.RECONNECT_RECOVERY: reconnect,
        BrokerCapability.EXECUTION_FACTS: execution_facts,
    }

    manifest = ProviderCapabilityManifest(
        provider=IBKR_PROVIDER_KEY,
        environment=RuntimeEnvironment.PAPER,
        adapter_version=IBKR_ACL_ADAPTER_VERSION,
        account_mode="paper",
        asset_classes=frozenset({AssetClass.EQUITY}),
        supported_order_types=frozenset({OrderType.MARKET, OrderType.LIMIT}),
        supported_time_in_force=frozenset({TimeInForce.DAY}),
        capabilities=tuple(
            CapabilitySupport(
                capability=capability,
                constraints=scoped.get(capability, paper_equity),
            )
            for capability in IBKR_ACL_DECLARED_CAPABILITIES
        ),
        stream_model="tws-api-callbacks",
        session_model="ib-gateway-socket",
        sdk_name=None,
        sdk_version=None,
        known_limitations=(
            "PAPER only.",
            "US equities only.",
            "MARKET and LIMIT submission with DAY time in force.",
            "No SDK-backed transport is selected by LOT-05.7.",
            "No provider network call is made by LOT-05.7.",
            "LATEST_QUOTE is not declared until transport and entitlement semantics are mapped.",
            "REPLACE_ORDER is not declared.",
            "No IBKR capability is C3 PAPER certified by this manifest.",
            "LIVE qualification is unavailable.",
        ),
    )
    validate_ibkr_capability_manifest(manifest)
    return manifest


def validate_ibkr_capability_manifest(
    manifest: ProviderCapabilityManifest,
) -> None:
    """Fail closed if the LOT-05.7 manifest overclaims the frozen scope."""

    if not isinstance(manifest, ProviderCapabilityManifest):
        raise ValueError("manifest must be a ProviderCapabilityManifest.")
    if manifest.provider != IBKR_PROVIDER_KEY:
        raise ValueError("IBKR capability manifest provider must be ibkr.")
    if manifest.environment is not RuntimeEnvironment.PAPER:
        raise ValueError("IBKR capability manifest must remain PAPER only.")
    if manifest.capability_set != frozenset(IBKR_ACL_DECLARED_CAPABILITIES):
        raise ValueError("IBKR capability manifest does not match LOT-05.7 scope.")
    if manifest.supports(BrokerCapability.LATEST_QUOTE):
        raise ValueError("LATEST_QUOTE must remain undeclared in LOT-05.7.")
    if manifest.supports(BrokerCapability.REPLACE_ORDER):
        raise ValueError("REPLACE_ORDER must remain undeclared in LOT-05.7.")
    if manifest.sdk_name is not None or manifest.sdk_version is not None:
        raise ValueError("LOT-05.7 must not select a provider SDK.")
