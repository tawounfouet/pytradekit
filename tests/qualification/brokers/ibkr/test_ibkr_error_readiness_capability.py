"""LOT-05.7 qualification for IBKR error, readiness, and capability semantics."""

from datetime import UTC, datetime

from pytradekit.brokers import (
    ProviderStateReconciliationRequired,
    ProviderUncertainOutcomeError,
)
from pytradekit.brokers.adapters.ibkr import (
    IBKRErrorObservation,
    IBKRReadinessObservation,
    build_ibkr_capability_manifest,
    evaluate_ibkr_readiness,
    map_ibkr_provider_error,
)
from pytradekit.brokers.compliance import BrokerCapability

_NOW = datetime(2026, 10, 23, 6, 15, tzinfo=UTC)


def test_lot05_7_connectivity_loss_never_implies_blind_order_retry() -> None:
    observation = IBKRErrorObservation(
        request_id=-1,
        code=1100,
        message="Connectivity lost",
        observed_at=_NOW,
    )

    no_write = map_ibkr_provider_error(observation, operation="runtime")
    in_flight = map_ibkr_provider_error(
        observation,
        operation="submit",
        economic_write_in_flight=True,
    )

    assert isinstance(no_write, ProviderStateReconciliationRequired)
    assert isinstance(in_flight, ProviderUncertainOutcomeError)


def test_lot05_7_1101_requires_resubscription_and_reconciliation() -> None:
    decision = evaluate_ibkr_readiness(
        IBKRReadinessObservation(
            socket_connected=True,
            protocol_negotiated=True,
            next_valid_id_received=True,
            account_verified=True,
            paper_endpoint_verified=True,
            reconciliation_complete=False,
            account_ready=True,
            api_read_only=False,
            market_data_resubscribed=False,
            last_connectivity_code=1101,
        )
    )

    assert decision.ready_for_reads
    assert not decision.ready_for_market_data
    assert not decision.ready_for_economic_writes
    assert decision.reconciliation_required
    assert decision.market_data_resubscription_required


def test_lot05_7_manifest_is_conservative_before_paper_certification() -> None:
    manifest = build_ibkr_capability_manifest()

    assert manifest.supports(BrokerCapability.ACCOUNT_QUERY)
    assert manifest.supports(BrokerCapability.MARKET_ORDER)
    assert manifest.supports(BrokerCapability.RECONNECT_RECOVERY)
    assert not manifest.supports(BrokerCapability.LATEST_QUOTE)
    assert not manifest.supports(BrokerCapability.REPLACE_ORDER)
    assert manifest.sdk_name is None
