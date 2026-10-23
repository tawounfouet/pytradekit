"""Unit tests for IBKR LOT-06.5 economic-write execution."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from pytradekit.brokers import ProviderProtocolError, ProviderRejectedOperationError
from pytradekit.brokers.adapters.ibkr import (
    IBKRClientId,
    IBKRContractDetailsRecord,
    IBKRContractId,
    IBKRContractRecord,
    IBKREconomicWriteAdmission,
    IBKRExecutionAdapter,
    IBKRExecutionInstrumentBinding,
    IBKRPaperConnectionRuntime,
    IBKRPaperRuntimeProfile,
    IBKRSDKPlacementFactory,
    IBKRSecurityType,
    IBKRTransportConnectionEvidence,
    StaticIBKRExecutionInstrumentResolver,
    build_ibkr_order_session_runtime,
    map_ibkr_stock_contract,
)
from pytradekit.execution import CancelStatus, ExecutionStatus, SubmissionStatus
from pytradekit.orders.domain import (
    Order,
    OrderId,
    OrderSide,
    TimeInForce,
)
from pytradekit.shared import CorrelationId, Currency, InstrumentId, Price, Quantity

_NOW = datetime(2026, 10, 23, 10, 30, tzinfo=UTC)


class _Clock:
    def now(self) -> datetime:
        return _NOW


class _LowLevel:
    def __init__(self) -> None:
        self.next_id = 500

    def isReady(self) -> bool:
        return True

    def getReqId(self) -> int:
        value = self.next_id
        self.next_id += 1
        return value


class _Object:
    def __init__(self, **kwargs: object) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


class _ProviderClient:
    def __init__(self) -> None:
        self.client = _LowLevel()
        self.place_calls = 0
        self.cancel_calls = 0
        self.place_error: Exception | None = None
        self.cancel_error: Exception | None = None
        self.perm_id = 700
        self._trades: list[object] = []

    def placeOrder(self, contract: object, order: object) -> object:
        self.place_calls += 1
        if self.place_error is not None:
            raise self.place_error

        setattr(order, "clientId", 7)
        setattr(order, "permId", self.perm_id)
        status = _Object(
            orderId=getattr(order, "orderId"),
            status="Submitted",
            filled=Decimal("0"),
            remaining=getattr(order, "totalQuantity"),
            avgFillPrice=Decimal("0"),
            permId=self.perm_id,
            clientId=7,
            lastFillPrice=Decimal("0"),
            whyHeld="",
        )
        trade = _Object(
            contract=contract,
            order=order,
            orderStatus=status,
            advancedError="",
        )
        self._trades.append(trade)
        return trade

    def cancelOrder(
        self,
        order: object,
        manualCancelOrderTime: str = "",
    ) -> object | None:
        _ = manualCancelOrderTime
        self.cancel_calls += 1
        if self.cancel_error is not None:
            raise self.cancel_error
        for trade in self._trades:
            if getattr(trade, "order") is order:
                return trade
        return None

    def trades(self) -> list[object]:
        return list(self._trades)


class _Transport:
    def __init__(self, provider: _ProviderClient) -> None:
        self.provider = provider
        self.connected = False

    def connect(
        self,
        profile: IBKRPaperRuntimeProfile,
    ) -> IBKRTransportConnectionEvidence:
        self.connected = True
        return IBKRTransportConnectionEvidence(
            transport_name="deterministic",
            transport_version="2.1.0",
            socket_connected=True,
            protocol_ready=True,
            account_verified=True,
            managed_accounts=(profile.expected_account_id,),
            server_version=200,
        )

    def disconnect(self) -> None:
        self.connected = False

    def is_connected(self) -> bool:
        return self.connected

    def read_client(self) -> object:
        if not self.connected:
            raise RuntimeError("disconnected")
        return self.provider


def _binding(
    *,
    market_rule: bool = False,
) -> IBKRExecutionInstrumentBinding:
    contract = IBKRContractRecord(
        contract_id=IBKRContractId(265598),
        symbol="AAPL",
        security_type=IBKRSecurityType.STOCK,
        exchange="SMART",
        primary_exchange="NASDAQ",
        currency="USD",
        local_symbol="AAPL",
        trading_class="NMS",
    )
    details = IBKRContractDetailsRecord(
        contract=contract,
        min_tick=Decimal("0.01"),
        min_size=Decimal("1"),
        size_increment=Decimal("1"),
        valid_exchanges=("SMART",),
        market_rule_ids=((26,) if market_rule else ()),
    )
    mapping = map_ibkr_stock_contract(
        details,
        instrument_id=InstrumentId.new(),
    )
    return IBKRExecutionInstrumentBinding(
        contract=contract,
        mapping=mapping,
    )


def _admission(
    *,
    enabled: bool = True,
) -> IBKREconomicWriteAdmission:
    return IBKREconomicWriteAdmission(
        paper_endpoint_verified=True,
        account_ready=True,
        reconciliation_complete=True,
        api_read_only=False,
        economic_write_enabled=enabled,
    )


def _order(
    binding: IBKRExecutionInstrumentBinding,
    *,
    limit_price: Decimal | None = None,
    reference: str = "ptk-exec-1",
) -> Order:
    if limit_price is None:
        order = Order.create_market(
            order_id=OrderId.new(),
            instrument_id=binding.mapping.instrument.id,
            side=OrderSide.BUY,
            quantity=Quantity(Decimal("1")),
            time_in_force=TimeInForce.DAY,
            correlation_id=CorrelationId.new(),
            occurred_at=_NOW,
            client_order_id=reference,
        )
    else:
        order = Order.create_limit(
            order_id=OrderId.new(),
            instrument_id=binding.mapping.instrument.id,
            side=OrderSide.BUY,
            quantity=Quantity(Decimal("1")),
            time_in_force=TimeInForce.DAY,
            correlation_id=CorrelationId.new(),
            occurred_at=_NOW,
            limit_price=Price(limit_price, Currency("USD")),
            client_order_id=reference,
        )
    order.validate(occurred_at=_NOW)
    order.mark_submitted(occurred_at=_NOW)
    return order


def _adapter(
    binding: IBKRExecutionInstrumentBinding,
    *,
    admission: IBKREconomicWriteAdmission | None = None,
) -> tuple[IBKRExecutionAdapter, _ProviderClient]:
    provider = _ProviderClient()
    connection = IBKRPaperConnectionRuntime(
        profile=IBKRPaperRuntimeProfile(
            expected_account_id="DU1234567",
            client_id=IBKRClientId(7),
        ),
        transport=_Transport(provider),
    )
    startup = connection.start()
    assert startup.ready_for_startup
    session = build_ibkr_order_session_runtime(connection=connection)
    resolver = StaticIBKRExecutionInstrumentResolver((binding,))
    sdk_factory = IBKRSDKPlacementFactory(
        contract_constructor=_Object,
        order_constructor=_Object,
    )
    return (
        IBKRExecutionAdapter(
            connection=connection,
            session=session,
            instruments=resolver,
            admission=admission or _admission(),
            clock=_Clock(),
            sdk_factory=sdk_factory,
        ),
        provider,
    )


def test_market_submit_calls_place_order_once_and_acknowledges_perm_id() -> None:
    binding = _binding()
    adapter, provider = _adapter(binding)

    result = adapter.submit(_order(binding))

    assert result.status is SubmissionStatus.ACKNOWLEDGED
    assert result.external_order_id == "700"
    assert provider.place_calls == 1
    assert len(provider.trades()) == 1

    trade = provider.trades()[0]
    sdk_order = getattr(trade, "order")
    sdk_contract = getattr(trade, "contract")
    assert sdk_order.orderId == 500
    assert sdk_order.clientId == 7
    assert sdk_order.orderRef == "ptk-exec-1"
    assert sdk_order.account == "DU1234567"
    assert sdk_order.action == "BUY"
    assert sdk_order.orderType == "MKT"
    assert sdk_order.tif == "DAY"
    assert sdk_order.transmit is True
    assert sdk_order.outsideRth is False
    assert sdk_order.whatIf is False
    assert sdk_order.overridePercentageConstraints is False
    assert sdk_contract.conId == 265598
    assert sdk_contract.exchange == "SMART"


def test_place_order_exception_is_uncertain_and_never_retried() -> None:
    binding = _binding()
    adapter, provider = _adapter(binding)
    provider.place_error = ConnectionError("wire lost")

    result = adapter.submit(_order(binding))

    assert result.status is SubmissionStatus.UNCERTAIN
    assert provider.place_calls == 1
    assert adapter.last_attempt is not None
    assert adapter.last_attempt.provider_call_attempted
    assert not adapter.last_attempt.provider_returned


def test_zero_perm_id_after_place_order_is_uncertain() -> None:
    binding = _binding()
    adapter, provider = _adapter(binding)
    provider.perm_id = 0

    result = adapter.submit(_order(binding))

    assert result.status is SubmissionStatus.UNCERTAIN
    assert result.external_order_id is None
    assert provider.place_calls == 1


def test_market_rule_limit_is_rejected_before_economic_write() -> None:
    binding = _binding(market_rule=True)
    adapter, provider = _adapter(binding)

    result = adapter.submit(
        _order(binding, limit_price=Decimal("250.12"))
    )

    assert result.status is SubmissionStatus.REJECTED
    assert "market-rule" in (result.reason or "")
    assert provider.place_calls == 0


def test_static_limit_builds_decimal_lmt_price_and_places_once() -> None:
    binding = _binding()
    adapter, provider = _adapter(binding)

    result = adapter.submit(
        _order(binding, limit_price=Decimal("250.12"))
    )

    assert result.status is SubmissionStatus.ACKNOWLEDGED
    assert provider.place_calls == 1
    sdk_order = getattr(provider.trades()[0], "order")
    assert sdk_order.orderType == "LMT"
    assert sdk_order.lmtPrice == Decimal("250.12")
    assert isinstance(sdk_order.lmtPrice, Decimal)


def test_closed_admission_never_reaches_provider() -> None:
    binding = _binding()
    adapter, provider = _adapter(
        binding,
        admission=_admission(enabled=False),
    )

    with pytest.raises(ProviderRejectedOperationError, match="admission"):
        adapter.submit(_order(binding))

    assert provider.place_calls == 0


def test_existing_provider_route_collision_blocks_place_order() -> None:
    binding = _binding()
    adapter, provider = _adapter(binding)
    provider._trades.append(
        _Object(
            order=_Object(
                orderId=500,
                clientId=7,
                permId=999,
                orderRef="external",
                account="DU1234567",
            ),
            orderStatus=_Object(
                orderId=500,
                status="Submitted",
                permId=999,
                clientId=7,
            ),
        )
    )

    with pytest.raises(ProviderProtocolError, match="already exists"):
        adapter.submit(_order(binding))

    assert provider.place_calls == 0


def test_cancel_calls_provider_once_and_acknowledges_request() -> None:
    binding = _binding()
    adapter, provider = _adapter(binding)
    order = _order(binding)
    submit = adapter.submit(order)
    assert submit.status is SubmissionStatus.ACKNOWLEDGED

    result = adapter.cancel(order)

    assert result.status is CancelStatus.ACKNOWLEDGED
    assert provider.cancel_calls == 1


def test_cancel_exception_is_uncertain_and_never_retried() -> None:
    binding = _binding()
    adapter, provider = _adapter(binding)
    order = _order(binding)
    assert adapter.submit(order).status is SubmissionStatus.ACKNOWLEDGED
    provider.cancel_error = ConnectionError("wire lost")

    result = adapter.cancel(order)

    assert result.status is CancelStatus.UNCERTAIN
    assert provider.cancel_calls == 1


def test_query_order_reuses_callback_normalization() -> None:
    binding = _binding()
    adapter, _provider = _adapter(binding)
    order = _order(binding)
    assert adapter.submit(order).status is SubmissionStatus.ACKNOWLEDGED

    report = adapter.query_order(order)

    assert report is not None
    assert report.status is ExecutionStatus.ACCEPTED
    assert report.external_order_id == "700"
    assert report.order_id == order.id
