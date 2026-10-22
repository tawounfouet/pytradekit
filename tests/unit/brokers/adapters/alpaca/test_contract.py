"""Contract tests for the frozen Alpaca 0.5 integration rules."""

import pytest
from alpaca.trading.enums import OrderStatus as AlpacaOrderStatus
from alpaca.trading.enums import TradeEvent as AlpacaTradeEvent

from pytradekit.brokers.adapters.alpaca.contract import (
    ALPACA_CLIENT_ORDER_ID_MAX_LENGTH,
    ALPACA_ENVIRONMENT,
    ALPACA_ORDER_STATUS_RULES,
    ALPACA_PROVIDER_KEY,
    ALPACA_SDK_VERSION_TARGET,
    ALPACA_TRADE_EVENT_RULES,
    AlpacaStateDisposition,
    order_status_rule,
    supports_order_contract,
    trade_event_rule,
    validate_client_order_reference,
)
from pytradekit.execution import ExecutionStatus
from pytradekit.orders.domain import OrderType, TimeInForce


def test_contract_is_paper_only_and_pinned_to_qualified_sdk() -> None:
    assert ALPACA_PROVIDER_KEY == "alpaca"
    assert ALPACA_ENVIRONMENT == "PAPER"
    assert ALPACA_SDK_VERSION_TARGET == "0.44.0"


def test_every_current_alpaca_order_status_has_an_explicit_rule() -> None:
    assert set(ALPACA_ORDER_STATUS_RULES) == set(AlpacaOrderStatus)


def test_every_current_trade_event_has_an_explicit_rule() -> None:
    assert set(ALPACA_TRADE_EVENT_RULES) == set(AlpacaTradeEvent)


@pytest.mark.parametrize(
    ("provider_status", "canonical_status"),
    [
        (AlpacaOrderStatus.ACCEPTED, ExecutionStatus.ACCEPTED),
        (AlpacaOrderStatus.NEW, ExecutionStatus.ACCEPTED),
        (AlpacaOrderStatus.PARTIALLY_FILLED, ExecutionStatus.PARTIALLY_FILLED),
        (AlpacaOrderStatus.FILLED, ExecutionStatus.FILLED),
        (AlpacaOrderStatus.CANCELED, ExecutionStatus.CANCELLED),
        (AlpacaOrderStatus.EXPIRED, ExecutionStatus.EXPIRED),
        (AlpacaOrderStatus.REJECTED, ExecutionStatus.REJECTED),
    ],
)
def test_frozen_order_status_mappings(
    provider_status: AlpacaOrderStatus,
    canonical_status: ExecutionStatus,
) -> None:
    rule = order_status_rule(provider_status)

    assert rule.disposition is AlpacaStateDisposition.MAP
    assert rule.canonical_status is canonical_status


@pytest.mark.parametrize(
    ("event", "canonical_status"),
    [
        (AlpacaTradeEvent.ACCEPTED, ExecutionStatus.ACCEPTED),
        (AlpacaTradeEvent.NEW, ExecutionStatus.ACCEPTED),
        (AlpacaTradeEvent.PARTIAL_FILL, ExecutionStatus.PARTIALLY_FILLED),
        (AlpacaTradeEvent.FILL, ExecutionStatus.FILLED),
        (AlpacaTradeEvent.CANCELED, ExecutionStatus.CANCELLED),
        (AlpacaTradeEvent.EXPIRED, ExecutionStatus.EXPIRED),
        (AlpacaTradeEvent.REJECTED, ExecutionStatus.REJECTED),
    ],
)
def test_frozen_trade_event_mappings(
    event: AlpacaTradeEvent,
    canonical_status: ExecutionStatus,
) -> None:
    rule = trade_event_rule(event)

    assert rule.disposition is AlpacaStateDisposition.MAP
    assert rule.canonical_status is canonical_status


def test_pending_states_remain_transport_provider_transients() -> None:
    assert (
        order_status_rule(AlpacaOrderStatus.PENDING_NEW).disposition
        is AlpacaStateDisposition.TRANSIENT
    )
    assert (
        order_status_rule(AlpacaOrderStatus.PENDING_CANCEL).disposition
        is AlpacaStateDisposition.TRANSIENT
    )
    assert (
        trade_event_rule(AlpacaTradeEvent.PENDING_NEW).disposition
        is AlpacaStateDisposition.TRANSIENT
    )
    assert (
        trade_event_rule(AlpacaTradeEvent.PENDING_CANCEL).disposition
        is AlpacaStateDisposition.TRANSIENT
    )


def test_replace_path_is_explicitly_out_of_scope_for_0_5() -> None:
    assert (
        order_status_rule(AlpacaOrderStatus.REPLACED).disposition
        is AlpacaStateDisposition.OUT_OF_SCOPE
    )
    assert (
        trade_event_rule(AlpacaTradeEvent.REPLACED).disposition
        is AlpacaStateDisposition.OUT_OF_SCOPE
    )


def test_noncanonical_states_require_reconciliation_instead_of_domain_growth() -> None:
    for status in (
        AlpacaOrderStatus.DONE_FOR_DAY,
        AlpacaOrderStatus.PENDING_REVIEW,
        AlpacaOrderStatus.ACCEPTED_FOR_BIDDING,
        AlpacaOrderStatus.STOPPED,
        AlpacaOrderStatus.SUSPENDED,
        AlpacaOrderStatus.CALCULATED,
        AlpacaOrderStatus.HELD,
    ):
        rule = order_status_rule(status)
        assert rule.disposition is AlpacaStateDisposition.RECONCILE
        assert rule.canonical_status is None

    restated = trade_event_rule(AlpacaTradeEvent.RESTATED)
    assert restated.disposition is AlpacaStateDisposition.RECONCILE
    assert restated.canonical_status is None


def test_order_contract_is_deliberately_small_for_0_5() -> None:
    assert supports_order_contract(
        order_type=OrderType.MARKET,
        time_in_force=TimeInForce.DAY,
    )
    assert supports_order_contract(
        order_type=OrderType.LIMIT,
        time_in_force=TimeInForce.DAY,
    )
    assert not supports_order_contract(
        order_type=OrderType.STOP,
        time_in_force=TimeInForce.DAY,
    )
    assert not supports_order_contract(
        order_type=OrderType.MARKET,
        time_in_force=TimeInForce.GTC,
    )


def test_client_order_reference_respects_provider_limit() -> None:
    accepted = "p" * ALPACA_CLIENT_ORDER_ID_MAX_LENGTH
    assert validate_client_order_reference(accepted) == accepted

    with pytest.raises(ValueError, match="maximum length"):
        validate_client_order_reference(accepted + "x")

    with pytest.raises(ValueError, match="must not be empty"):
        validate_client_order_reference("   ")
