"""LOT-05.5 qualification for IBKR execDetails and Fill mapping."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from pytradekit.brokers import (
    ProviderExecutionContext,
    ProviderStateReconciliationRequired,
)
from pytradekit.brokers.adapters.ibkr import (
    IBKRClientId,
    IBKRContractDetailsRecord,
    IBKRContractId,
    IBKRContractRecord,
    IBKRExecutionDetailsObservation,
    IBKRExecutionId,
    IBKRExecutionRegistry,
    IBKRExecutionSide,
    IBKROrderIdentityRegistry,
    IBKROrderReference,
    IBKRPermanentOrderId,
    IBKRSecurityType,
    IBKRSessionOrderId,
    map_ibkr_execution_report,
    map_ibkr_stock_contract,
)
from pytradekit.execution import ExecutionStatus
from pytradekit.orders.domain import OrderId, OrderSide
from pytradekit.shared import CorrelationId, Currency, InstrumentId, Quantity

_NOW = datetime(2026, 10, 23, 14, 56, 24, tzinfo=UTC)


def _observation(exec_id: str, cumulative: str) -> IBKRExecutionDetailsObservation:
    return IBKRExecutionDetailsObservation(
        contract_id=IBKRContractId(265598),
        symbol="AAPL",
        execution_id=IBKRExecutionId(exec_id),
        client_id=IBKRClientId(3),
        session_order_id=IBKRSessionOrderId(101),
        permanent_order_id=IBKRPermanentOrderId(900101),
        order_reference=IBKROrderReference("ptk-lot05-5"),
        side=IBKRExecutionSide.BOUGHT,
        shares=Decimal("2"),
        price=Decimal("250.10"),
        cumulative_quantity=Decimal(cumulative),
        average_price=Decimal("250.10"),
        exchange="IEX",
        account="DU1234567",
        occurred_at=_NOW,
    )


def test_lot05_5_produces_one_effect_per_real_exec_id() -> None:
    contract = IBKRContractRecord(
        contract_id=IBKRContractId(265598),
        symbol="AAPL",
        security_type=IBKRSecurityType.STOCK,
        exchange="SMART",
        primary_exchange="NASDAQ",
        currency="USD",
        local_symbol="AAPL",
    )
    instrument = map_ibkr_stock_contract(
        IBKRContractDetailsRecord(
            contract=contract,
            min_size=Decimal("1"),
            size_increment=Decimal("1"),
        ),
        instrument_id=InstrumentId.new(),
    )
    context = ProviderExecutionContext(
        order_id=OrderId.new(),
        correlation_id=CorrelationId.new(),
        client_order_reference="ptk-lot05-5",
        quote_currency=Currency("USD"),
    )
    order_registry = IBKROrderIdentityRegistry()
    execution_registry = IBKRExecutionRegistry()

    first = map_ibkr_execution_report(
        _observation("EXEC.01.01", "2"),
        context=context,
        expected_side=OrderSide.BUY,
        expected_quantity=Quantity(Decimal("4")),
        instrument=instrument,
        order_registry=order_registry,
        execution_registry=execution_registry,
    )
    replay = map_ibkr_execution_report(
        _observation("EXEC.01.01", "2"),
        context=context,
        expected_side=OrderSide.BUY,
        expected_quantity=Quantity(Decimal("4")),
        instrument=instrument,
        order_registry=order_registry,
        execution_registry=execution_registry,
    )
    final = map_ibkr_execution_report(
        _observation("EXEC.02.01", "4"),
        context=context,
        expected_side=OrderSide.BUY,
        expected_quantity=Quantity(Decimal("4")),
        instrument=instrument,
        order_registry=order_registry,
        execution_registry=execution_registry,
    )

    assert first is not None
    assert first.status is ExecutionStatus.PARTIALLY_FILLED
    assert replay is None
    assert final is not None
    assert final.status is ExecutionStatus.FILLED

    with pytest.raises(ProviderStateReconciliationRequired, match="correction"):
        map_ibkr_execution_report(
            _observation("EXEC.01.02", "2"),
            context=context,
            expected_side=OrderSide.BUY,
            expected_quantity=Quantity(Decimal("4")),
            instrument=instrument,
            order_registry=order_registry,
            execution_registry=execution_registry,
        )
