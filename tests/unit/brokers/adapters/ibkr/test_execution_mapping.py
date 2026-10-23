"""Unit tests for IBKR execDetails and Fill mapping."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from pytradekit.brokers import (
    ProviderExecutionContext,
    ProviderProtocolError,
    ProviderStateReconciliationRequired,
)
from pytradekit.brokers.adapters.ibkr import (
    IBKRClientId,
    IBKRContractDetailsRecord,
    IBKRContractId,
    IBKRContractRecord,
    IBKRExecutionDetailsObservation,
    IBKRExecutionDisposition,
    IBKRExecutionId,
    IBKRExecutionMappingError,
    IBKRExecutionRegistry,
    IBKRExecutionSide,
    IBKRInstrumentMappingResult,
    IBKROrderIdentityRegistry,
    IBKROrderReference,
    IBKRPermanentOrderId,
    IBKRSecurityType,
    IBKRSessionOrderId,
    map_ibkr_execution_report,
    map_ibkr_stock_contract,
    parse_ibkr_execution_time,
)
from pytradekit.execution import ExecutionStatus
from pytradekit.orders.domain import OrderId, OrderSide
from pytradekit.shared import CorrelationId, Currency, InstrumentId, Quantity

_NOW = datetime(2026, 10, 23, 14, 56, 24, tzinfo=UTC)


def _context(reference: str = "ptk-exec-1") -> ProviderExecutionContext:
    return ProviderExecutionContext(
        order_id=OrderId.new(),
        correlation_id=CorrelationId.new(),
        client_order_reference=reference,
        quote_currency=Currency("USD"),
    )


def _instrument() -> tuple[IBKRContractRecord, IBKRInstrumentMappingResult]:
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
    instrument = map_ibkr_stock_contract(
        IBKRContractDetailsRecord(
            contract=contract,
            min_size=Decimal("1"),
            size_increment=Decimal("1"),
        ),
        instrument_id=InstrumentId.new(),
    )
    return contract, instrument


def _execution(
    *,
    exec_id: str = "0000e0d5.68fa9014.01.01",
    shares: str = "5",
    cumulative_quantity: str = "5",
    side: IBKRExecutionSide = IBKRExecutionSide.BOUGHT,
    pending_price_revision: bool = False,
    order_reference: str = "ptk-exec-1",
    contract_id: int = 265598,
) -> IBKRExecutionDetailsObservation:
    return IBKRExecutionDetailsObservation(
        contract_id=IBKRContractId(contract_id),
        symbol="AAPL",
        execution_id=IBKRExecutionId(exec_id),
        client_id=IBKRClientId(3),
        session_order_id=IBKRSessionOrderId(101),
        permanent_order_id=IBKRPermanentOrderId(900101),
        order_reference=IBKROrderReference(order_reference),
        side=side,
        shares=Decimal(shares),
        price=Decimal("250.10"),
        cumulative_quantity=Decimal(cumulative_quantity),
        average_price=Decimal("250.10"),
        exchange="IEX",
        account="DU1234567",
        occurred_at=_NOW,
        pending_price_revision=pending_price_revision,
    )


def test_full_execution_maps_to_one_canonical_filled_report() -> None:
    _contract, instrument = _instrument()
    order_registry = IBKROrderIdentityRegistry()
    execution_registry = IBKRExecutionRegistry()
    context = _context()

    report = map_ibkr_execution_report(
        _execution(shares="5", cumulative_quantity="5"),
        context=context,
        expected_side=OrderSide.BUY,
        expected_quantity=Quantity(Decimal("5")),
        instrument=instrument,
        order_registry=order_registry,
        execution_registry=execution_registry,
    )

    assert report is not None
    assert report.status is ExecutionStatus.FILLED
    assert report.external_order_id == "900101"
    assert report.fill is not None
    assert report.fill.quantity == Quantity(Decimal("5"))
    assert report.fill.price.value == Decimal("250.10")
    assert report.fill.price.currency == Currency("USD")
    assert report.fill.external_fill_id == "0000e0d5.68fa9014.01.01"
    assert report.fill.fee is None


def test_partial_execution_maps_to_partially_filled() -> None:
    _contract, instrument = _instrument()

    report = map_ibkr_execution_report(
        _execution(shares="2", cumulative_quantity="2"),
        context=_context(),
        expected_side=OrderSide.BUY,
        expected_quantity=Quantity(Decimal("5")),
        instrument=instrument,
        order_registry=IBKROrderIdentityRegistry(),
        execution_registry=IBKRExecutionRegistry(),
    )

    assert report is not None
    assert report.status is ExecutionStatus.PARTIALLY_FILLED
    assert report.fill is not None
    assert report.fill.quantity.value == Decimal("2")


def test_exact_exec_id_replay_is_deduplicated() -> None:
    _contract, instrument = _instrument()
    order_registry = IBKROrderIdentityRegistry()
    execution_registry = IBKRExecutionRegistry()
    context = _context()
    observation = _execution(shares="2", cumulative_quantity="2")

    first = map_ibkr_execution_report(
        observation,
        context=context,
        expected_side=OrderSide.BUY,
        expected_quantity=Quantity(Decimal("5")),
        instrument=instrument,
        order_registry=order_registry,
        execution_registry=execution_registry,
    )
    second = map_ibkr_execution_report(
        observation,
        context=context,
        expected_side=OrderSide.BUY,
        expected_quantity=Quantity(Decimal("5")),
        instrument=instrument,
        order_registry=order_registry,
        execution_registry=execution_registry,
    )

    assert first is not None
    assert second is None
    assert len(execution_registry) == 1


def test_exec_id_correction_never_becomes_second_fill() -> None:
    _contract, instrument = _instrument()
    order_registry = IBKROrderIdentityRegistry()
    execution_registry = IBKRExecutionRegistry()
    context = _context()

    first = map_ibkr_execution_report(
        _execution(
            exec_id="0000e0d5.68fa9014.01.01",
            shares="2",
            cumulative_quantity="2",
        ),
        context=context,
        expected_side=OrderSide.BUY,
        expected_quantity=Quantity(Decimal("5")),
        instrument=instrument,
        order_registry=order_registry,
        execution_registry=execution_registry,
    )

    assert first is not None

    correction = _execution(
        exec_id="0000e0d5.68fa9014.01.02",
        shares="2",
        cumulative_quantity="2",
    )
    with pytest.raises(
        ProviderStateReconciliationRequired,
        match="correction",
    ):
        map_ibkr_execution_report(
            correction,
            context=context,
            expected_side=OrderSide.BUY,
            expected_quantity=Quantity(Decimal("5")),
            instrument=instrument,
            order_registry=order_registry,
            execution_registry=execution_registry,
        )

    with pytest.raises(
        ProviderStateReconciliationRequired,
        match="correction",
    ):
        map_ibkr_execution_report(
            correction,
            context=context,
            expected_side=OrderSide.BUY,
            expected_quantity=Quantity(Decimal("5")),
            instrument=instrument,
            order_registry=order_registry,
            execution_registry=execution_registry,
        )

    assert len(execution_registry) == 1


def test_execution_registry_reports_duplicate_and_correction() -> None:
    registry = IBKRExecutionRegistry()
    first_id = IBKRExecutionId("ABC.01")
    correction_id = IBKRExecutionId("ABC.02")

    first = registry.register(first_id)
    duplicate = registry.register(first_id)
    correction = registry.register(correction_id)

    assert first.disposition is IBKRExecutionDisposition.NEW
    assert duplicate.disposition is IBKRExecutionDisposition.DUPLICATE
    assert correction.disposition is IBKRExecutionDisposition.CORRECTION
    assert correction.previous_execution_id == first_id


def test_pending_price_revision_blocks_fill_before_registry_effect() -> None:
    _contract, instrument = _instrument()
    execution_registry = IBKRExecutionRegistry()

    with pytest.raises(
        ProviderStateReconciliationRequired,
        match="price revision",
    ):
        map_ibkr_execution_report(
            _execution(pending_price_revision=True),
            context=_context(),
            expected_side=OrderSide.BUY,
            expected_quantity=Quantity(Decimal("5")),
            instrument=instrument,
            order_registry=IBKROrderIdentityRegistry(),
            execution_registry=execution_registry,
        )

    assert len(execution_registry) == 0


def test_execution_side_mismatch_is_protocol_error() -> None:
    _contract, instrument = _instrument()

    with pytest.raises(ProviderProtocolError, match="side"):
        map_ibkr_execution_report(
            _execution(side=IBKRExecutionSide.SOLD),
            context=_context(),
            expected_side=OrderSide.BUY,
            expected_quantity=Quantity(Decimal("5")),
            instrument=instrument,
            order_registry=IBKROrderIdentityRegistry(),
            execution_registry=IBKRExecutionRegistry(),
        )


def test_execution_order_ref_mismatch_is_protocol_error() -> None:
    _contract, instrument = _instrument()

    with pytest.raises(ProviderProtocolError, match="orderRef"):
        map_ibkr_execution_report(
            _execution(order_reference="different-reference"),
            context=_context(),
            expected_side=OrderSide.BUY,
            expected_quantity=Quantity(Decimal("5")),
            instrument=instrument,
            order_registry=IBKROrderIdentityRegistry(),
            execution_registry=IBKRExecutionRegistry(),
        )


def test_execution_contract_mismatch_is_protocol_error() -> None:
    _contract, instrument = _instrument()

    with pytest.raises(ProviderProtocolError, match="conId"):
        map_ibkr_execution_report(
            _execution(contract_id=999999),
            context=_context(),
            expected_side=OrderSide.BUY,
            expected_quantity=Quantity(Decimal("5")),
            instrument=instrument,
            order_registry=IBKROrderIdentityRegistry(),
            execution_registry=IBKRExecutionRegistry(),
        )


def test_cumulative_quantity_cannot_exceed_canonical_order() -> None:
    _contract, instrument = _instrument()

    with pytest.raises(ProviderProtocolError, match="exceeds"):
        map_ibkr_execution_report(
            _execution(shares="6", cumulative_quantity="6"),
            context=_context(),
            expected_side=OrderSide.BUY,
            expected_quantity=Quantity(Decimal("5")),
            instrument=instrument,
            order_registry=IBKROrderIdentityRegistry(),
            execution_registry=IBKRExecutionRegistry(),
        )


def test_parse_ibkr_utc_execution_time() -> None:
    parsed = parse_ibkr_execution_time("20251022-18:56:24")

    assert parsed == datetime(2025, 10, 22, 18, 56, 24, tzinfo=UTC)


def test_parse_ibkr_zoned_execution_time_converts_to_utc() -> None:
    parsed = parse_ibkr_execution_time(
        "20251022 14:56:24 US/Eastern"
    )

    assert parsed == datetime(2025, 10, 22, 18, 56, 24, tzinfo=UTC)


def test_parse_ibkr_execution_time_rejects_naive_local_time() -> None:
    with pytest.raises(IBKRExecutionMappingError, match="timezone"):
        parse_ibkr_execution_time("20251022 14:56:24")
