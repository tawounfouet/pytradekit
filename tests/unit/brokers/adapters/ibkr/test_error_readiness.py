"""Unit tests for IBKR error taxonomy and readiness."""

from datetime import UTC, datetime

import pytest

from pytradekit.brokers import (
    ProviderAuthorizationError,
    ProviderProtocolError,
    ProviderRateLimitError,
    ProviderRejectedOperationError,
    ProviderStateReconciliationRequired,
    ProviderUnavailableError,
    ProviderUncertainOutcomeError,
)
from pytradekit.brokers.adapters.ibkr import (
    IBKRConnectivityState,
    IBKRErrorCategory,
    IBKRErrorDisposition,
    IBKRErrorObservation,
    IBKRReadinessObservation,
    assert_ibkr_ready_for_economic_write,
    build_ibkr_capability_manifest,
    evaluate_ibkr_readiness,
    ibkr_connectivity_state,
    ibkr_error_rule,
    map_ibkr_provider_error,
)
from pytradekit.brokers.compliance import BrokerCapability
from pytradekit.runtime import RuntimeEnvironment

_NOW = datetime(2026, 10, 23, 6, 0, tzinfo=UTC)


def _error(code: int, message: str = "provider message") -> IBKRErrorObservation:
    return IBKRErrorObservation(
        request_id=-1,
        code=code,
        message=message,
        observed_at=_NOW,
    )


def _ready(**overrides: bool | int | None) -> IBKRReadinessObservation:
    values: dict[str, bool | int | None] = {
        "socket_connected": True,
        "protocol_negotiated": True,
        "next_valid_id_received": True,
        "account_verified": True,
        "paper_endpoint_verified": True,
        "reconciliation_complete": True,
        "account_ready": True,
        "api_read_only": False,
        "market_data_resubscribed": True,
        "last_connectivity_code": None,
    }
    values.update(overrides)
    return IBKRReadinessObservation(**values)  # type: ignore[arg-type]


def test_system_health_messages_are_not_canonical_errors() -> None:
    for code in (2104, 2106, 2107, 2108, 2158):
        rule = ibkr_error_rule(code)
        assert rule.category is IBKRErrorCategory.INFORMATION
        assert rule.disposition is IBKRErrorDisposition.IGNORE
        assert map_ibkr_provider_error(_error(code), operation="startup") is None


def test_message_rate_limit_maps_to_provider_rate_limit() -> None:
    mapped = map_ibkr_provider_error(_error(100), operation="request")

    assert isinstance(mapped, ProviderRateLimitError)
    assert mapped.provider_code == "100"


def test_contract_request_rejection_maps_to_rejected_operation() -> None:
    mapped = map_ibkr_provider_error(_error(200), operation="contract_details")

    assert isinstance(mapped, ProviderRejectedOperationError)


def test_security_restriction_maps_to_authorization_error() -> None:
    mapped = map_ibkr_provider_error(_error(203), operation="submit")

    assert isinstance(mapped, ProviderAuthorizationError)


def test_disconnect_during_economic_write_is_uncertain_not_retryable() -> None:
    mapped = map_ibkr_provider_error(
        _error(1100),
        operation="submit",
        economic_write_in_flight=True,
    )

    assert isinstance(mapped, ProviderUncertainOutcomeError)


def test_disconnect_without_inflight_write_requires_reconciliation() -> None:
    mapped = map_ibkr_provider_error(_error(1100), operation="runtime")

    assert isinstance(mapped, ProviderStateReconciliationRequired)


def test_client_id_conflict_is_provider_unavailable() -> None:
    mapped = map_ibkr_provider_error(_error(326), operation="connect")

    assert isinstance(mapped, ProviderUnavailableError)


def test_incompatible_gateway_fails_as_protocol_error() -> None:
    mapped = map_ibkr_provider_error(_error(503), operation="connect")

    assert isinstance(mapped, ProviderProtocolError)


def test_unknown_error_code_fails_closed() -> None:
    mapped = map_ibkr_provider_error(_error(999999), operation="request")

    assert isinstance(mapped, ProviderProtocolError)


def test_order_codes_remain_owned_by_order_callback_normalization() -> None:
    assert map_ibkr_provider_error(_error(201), operation="order_callback") is None
    assert map_ibkr_provider_error(_error(202), operation="order_callback") is None


def test_connectivity_states_preserve_1101_vs_1102_semantics() -> None:
    assert (
        ibkr_connectivity_state(1101)
        is IBKRConnectivityState.RESTORED_DATA_LOST
    )
    assert (
        ibkr_connectivity_state(1102)
        is IBKRConnectivityState.RESTORED_DATA_MAINTAINED
    )


def test_fully_proven_paper_runtime_is_ready_for_economic_writes() -> None:
    decision = evaluate_ibkr_readiness(_ready())

    assert decision.ready_for_reads
    assert decision.ready_for_market_data
    assert decision.ready_for_economic_writes
    assert not decision.reconciliation_required


def test_next_valid_id_is_required_for_writes_but_not_reads() -> None:
    decision = evaluate_ibkr_readiness(_ready(next_valid_id_received=False))

    assert decision.ready_for_reads
    assert not decision.ready_for_economic_writes


def test_read_only_api_blocks_writes() -> None:
    decision = evaluate_ibkr_readiness(_ready(api_read_only=True))

    assert decision.ready_for_reads
    assert not decision.ready_for_economic_writes


def test_account_ready_false_blocks_reads_and_writes() -> None:
    decision = evaluate_ibkr_readiness(_ready(account_ready=False))

    assert not decision.ready_for_reads
    assert not decision.ready_for_economic_writes


def test_1101_requires_reconciliation_and_market_data_resubscription() -> None:
    decision = evaluate_ibkr_readiness(
        _ready(
            last_connectivity_code=1101,
            reconciliation_complete=False,
            market_data_resubscribed=False,
        )
    )

    assert decision.ready_for_reads
    assert not decision.ready_for_market_data
    assert not decision.ready_for_economic_writes
    assert decision.reconciliation_required
    assert decision.market_data_resubscription_required


def test_market_data_farm_disconnect_does_not_block_account_reads() -> None:
    decision = evaluate_ibkr_readiness(_ready(last_connectivity_code=2103))

    assert decision.ready_for_reads
    assert decision.ready_for_economic_writes
    assert not decision.ready_for_market_data


def test_readiness_gate_raises_reconciliation_error_before_write() -> None:
    with pytest.raises(ProviderStateReconciliationRequired):
        assert_ibkr_ready_for_economic_write(
            _ready(reconciliation_complete=False)
        )


def test_manifest_is_paper_only_and_does_not_overclaim_optional_capabilities() -> None:
    manifest = build_ibkr_capability_manifest()

    assert manifest.provider == "ibkr"
    assert manifest.environment is RuntimeEnvironment.PAPER
    assert manifest.sdk_name is None
    assert not manifest.supports(BrokerCapability.LATEST_QUOTE)
    assert not manifest.supports(BrokerCapability.REPLACE_ORDER)
    assert manifest.supports(BrokerCapability.MARKET_ORDER)
    assert manifest.supports(BrokerCapability.RECONNECT_RECOVERY)
