"""Unit tests for the IBKR LOT-04 discovery contract freeze."""

import pytest

from pytradekit.brokers.adapters.ibkr import (
    IBKR_DEFERRED_CAPABILITIES,
    IBKR_DISCOVERY_VERSION,
    IBKR_LIVE_PORTS,
    IBKR_PAPER_PORTS,
    IBKR_TARGET_CAPABILITIES,
    IBKRClientSurface,
    IBKRContractOutcome,
    IBKRDiscoveryError,
    IBKROrderIdentityRole,
    IBKRReadinessFact,
    build_ibkr_contract_freeze,
    validate_ibkr_paper_port,
)
from pytradekit.brokers.compliance import BrokerCapability
from pytradekit.orders.domain import OrderType, TimeInForce
from pytradekit.reference import AssetClass
from pytradekit.runtime import RuntimeEnvironment


def test_freeze_matches_first_ibkr_vertical_slice() -> None:
    freeze = build_ibkr_contract_freeze()

    assert freeze.version == IBKR_DISCOVERY_VERSION
    assert freeze.provider == "ibkr"
    assert freeze.environment is RuntimeEnvironment.PAPER
    assert freeze.runtime_surface is IBKRClientSurface.IB_GATEWAY
    assert freeze.paper_port == 4002
    assert freeze.asset_classes == frozenset({AssetClass.EQUITY})
    assert freeze.order_types == frozenset({OrderType.MARKET, OrderType.LIMIT})
    assert freeze.time_in_force == frozenset({TimeInForce.DAY})
    assert freeze.target_capabilities == IBKR_TARGET_CAPABILITIES
    assert freeze.deferred_capabilities == IBKR_DEFERRED_CAPABILITIES
    assert not freeze.broker_neutral_core_change_required


def test_paper_ports_are_explicit_and_live_ports_are_rejected() -> None:
    assert IBKR_PAPER_PORTS[IBKRClientSurface.TWS] == 7497
    assert IBKR_PAPER_PORTS[IBKRClientSurface.IB_GATEWAY] == 4002
    assert IBKR_LIVE_PORTS[IBKRClientSurface.TWS] == 7496
    assert IBKR_LIVE_PORTS[IBKRClientSurface.IB_GATEWAY] == 4001

    assert (
        validate_ibkr_paper_port(
            surface=IBKRClientSurface.TWS,
            port=7497,
        )
        == 7497
    )
    assert (
        validate_ibkr_paper_port(
            surface=IBKRClientSurface.IB_GATEWAY,
            port=4002,
        )
        == 4002
    )

    with pytest.raises(IBKRDiscoveryError):
        validate_ibkr_paper_port(
            surface=IBKRClientSurface.TWS,
            port=7496,
        )
    with pytest.raises(IBKRDiscoveryError):
        validate_ibkr_paper_port(
            surface=IBKRClientSurface.IB_GATEWAY,
            port=4001,
        )
    with pytest.raises(IBKRDiscoveryError):
        validate_ibkr_paper_port(
            surface=IBKRClientSurface.IB_GATEWAY,
            port=9999,
        )


def test_identity_roles_are_not_collapsed() -> None:
    freeze = build_ibkr_contract_freeze()

    assert freeze.client_reference_field == IBKROrderIdentityRole.CLIENT_REFERENCE.value
    assert freeze.session_order_id_field == IBKROrderIdentityRole.SESSION_ORDER_ID.value
    assert freeze.external_order_id_field == (
        IBKROrderIdentityRole.PERMANENT_ORDER_ID.value
    )
    assert freeze.external_fill_id_field == IBKROrderIdentityRole.EXECUTION_ID.value
    assert freeze.external_instrument_id_field == IBKROrderIdentityRole.CONTRACT_ID.value

    assert freeze.session_order_id_field == "orderId"
    assert freeze.external_order_id_field == "permId"
    assert freeze.session_order_id_field != freeze.external_order_id_field


def test_readiness_requires_next_valid_id_and_reconciliation() -> None:
    freeze = build_ibkr_contract_freeze()

    assert IBKRReadinessFact.NEXT_VALID_ID_RECEIVED in freeze.readiness_facts
    assert IBKRReadinessFact.ACCOUNT_VERIFIED in freeze.readiness_facts
    assert IBKRReadinessFact.RECONCILIATION_COMPLETE in freeze.readiness_facts


def test_replace_is_deferred_and_core_p0_capabilities_are_targeted() -> None:
    assert BrokerCapability.REPLACE_ORDER in IBKR_DEFERRED_CAPABILITIES
    assert BrokerCapability.REPLACE_ORDER not in IBKR_TARGET_CAPABILITIES

    required = {
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
    }
    assert required.issubset(set(IBKR_TARGET_CAPABILITIES))


def test_freeze_records_implementation_changes_outside_canonical_core() -> None:
    freeze = build_ibkr_contract_freeze()
    by_subject = {decision.subject: decision for decision in freeze.decisions}

    assert by_subject["core:ExecutionPort"].outcome is IBKRContractOutcome.UNCHANGED
    assert by_subject["core:BrokerSnapshotPort"].outcome is (
        IBKRContractOutcome.UNCHANGED
    )
    assert by_subject["runtime:profile"].outcome is (
        IBKRContractOutcome.IMPLEMENTATION_CHANGE
    )
    assert by_subject["adapter:submission_ack"].outcome is (
        IBKRContractOutcome.PAPER_PROBE_REQUIRED
    )
    assert by_subject["dependency:official_ibapi"].outcome is (
        IBKRContractOutcome.DEFERRED
    )


def test_unresolved_provider_facts_remain_explicit() -> None:
    freeze = build_ibkr_contract_freeze()

    joined = "\n".join(freeze.unresolved_paper_questions)

    assert "orderRef" in joined
    assert "permId" in joined
    assert "callback ordering" in joined
    assert "execId" in joined
    assert "pacing" in joined
