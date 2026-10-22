"""Unit tests for Alpaca LOT-08 read-only market data and snapshots."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import cast
from uuid import UUID

import pytest
from alpaca.data.enums import DataFeed
from alpaca.data.models.quotes import Quote as AlpacaQuote
from alpaca.data.requests import StockLatestQuoteRequest
from alpaca.trading.models import Asset, Position, TradeAccount

from pytradekit.brokers import (
    ProviderStateReconciliationRequired,
)
from pytradekit.brokers.adapters.alpaca import (
    AlpacaMarketDataSnapshots,
    AlpacaSnapshotReferenceResolver,
    AlpacaSnapshotTradingClient,
    AlpacaStockDataClient,
    StaticAlpacaReferenceResolver,
)
from pytradekit.portfolio.domain import AccountId
from pytradekit.reference.domain import InstrumentMapping
from pytradekit.runtime.ports import ClockPort
from pytradekit.shared import InstrumentId

NOW = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)
QUOTE_TIME = datetime(2026, 10, 22, 11, 59, 59, 500000, tzinfo=UTC)
ASSET_ID = UUID("11111111-2222-3333-4444-555555555555")
ACCOUNT_PROVIDER_ID = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")


class _Clock:
    def now(self) -> datetime:
        return NOW


class _TradingClient:
    def __init__(
        self,
        *,
        asset: object,
        account: object,
        positions: object,
    ) -> None:
        self.asset = asset
        self.account = account
        self.positions = positions
        self.asset_queries: list[object] = []
        self.account_queries = 0
        self.position_queries = 0

    def get_asset(self, symbol_or_asset_id: object) -> object:
        self.asset_queries.append(symbol_or_asset_id)
        return self.asset

    def get_account(self) -> object:
        self.account_queries += 1
        return self.account

    def get_all_positions(self) -> object:
        self.position_queries += 1
        return self.positions


class _MarketDataClient:
    def __init__(self, response: object) -> None:
        self.response = response
        self.requests: list[StockLatestQuoteRequest] = []

    def get_stock_latest_quote(self, request_params: StockLatestQuoteRequest) -> object:
        self.requests.append(request_params)
        return self.response


def _mapping(
    *,
    instrument_id: InstrumentId | None = None,
    symbol: str = "AAPL",
    external_id: str | None = str(ASSET_ID),
) -> InstrumentMapping:
    return InstrumentMapping(
        instrument_id=instrument_id or InstrumentId.new(),
        provider="alpaca",
        external_symbol=symbol,
        external_id=external_id,
    )


def _asset() -> Asset:
    return Asset.model_validate(
        {
            "id": str(ASSET_ID),
            "class": "us_equity",
            "exchange": "NASDAQ",
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "status": "active",
            "tradable": True,
            "marginable": True,
            "shortable": True,
            "easy_to_borrow": True,
            "fractionable": True,
            "min_order_size": 0.001,
            "min_trade_increment": 0.001,
            "price_increment": 0.01,
        }
    )


def _account() -> TradeAccount:
    return TradeAccount.model_validate(
        {
            "id": str(ACCOUNT_PROVIDER_ID),
            "account_number": "PA123456",
            "status": "ACTIVE",
            "currency": "USD",
            "cash": "1000.25",
            "buying_power": "2000.50",
            "equity": "1500.75",
            "portfolio_value": "1500.75",
            "trading_blocked": False,
            "account_blocked": False,
        }
    )


def _position() -> Position:
    return Position.model_validate(
        {
            "asset_id": str(ASSET_ID),
            "symbol": "AAPL",
            "exchange": "NASDAQ",
            "asset_class": "us_equity",
            "avg_entry_price": "190.125",
            "qty": "2.5",
            "side": "long",
            "market_value": "475.00",
            "cost_basis": "475.3125",
            "unrealized_pl": "-0.3125",
            "current_price": "190.00",
            "qty_available": "2.0",
        }
    )


def _quote(
    *,
    bid_price: float = 191.24,
    bid_size: float = 10.0,
    ask_price: float = 191.25,
    ask_size: float = 8.0,
) -> AlpacaQuote:
    return AlpacaQuote.model_construct(
        symbol="AAPL",
        timestamp=QUOTE_TIME,
        bid_price=bid_price,
        bid_size=bid_size,
        bid_exchange="V",
        ask_price=ask_price,
        ask_size=ask_size,
        ask_exchange="V",
        conditions=None,
        tape="C",
    )


def _service(
    mapping: InstrumentMapping,
    *,
    quote: AlpacaQuote | None = None,
    positions: object | None = None,
    account: TradeAccount | None = None,
) -> tuple[AlpacaMarketDataSnapshots, _TradingClient, _MarketDataClient]:
    resolver = StaticAlpacaReferenceResolver([mapping])
    trading = _TradingClient(
        asset=_asset(),
        account=account or _account(),
        positions=[_position()] if positions is None else positions,
    )
    market = _MarketDataClient(
        {mapping.external_symbol: quote or _quote()}
    )
    service = AlpacaMarketDataSnapshots(
        trading_client=cast(AlpacaSnapshotTradingClient, trading),
        market_data_client=cast(AlpacaStockDataClient, market),
        references=cast(AlpacaSnapshotReferenceResolver, resolver),
        account_id=AccountId.new(),
        expected_external_account_id=str(ACCOUNT_PROVIDER_ID),
        clock=cast(ClockPort, _Clock()),
    )
    return service, trading, market


def test_asset_snapshot_reuses_canonical_instrument_identity() -> None:
    mapping = _mapping()
    service, trading, _ = _service(mapping)

    snapshot = service.get_asset_snapshot(mapping.instrument_id)

    assert snapshot.instrument.id == mapping.instrument_id
    assert snapshot.mapping.external_id == str(ASSET_ID)
    assert snapshot.specification.tick_size == Decimal("0.01")
    assert trading.asset_queries == [str(ASSET_ID)]


def test_latest_quote_is_iex_and_preserves_provider_and_observation_times() -> None:
    mapping = _mapping()
    service, _, market = _service(mapping)

    snapshot = service.get_latest_quote(mapping.instrument_id)

    assert snapshot.provider == "alpaca"
    assert snapshot.feed == "iex"
    assert snapshot.quote.instrument_id == mapping.instrument_id
    assert snapshot.quote.bid_price is not None
    assert snapshot.quote.bid_price.value == Decimal("191.24")
    assert snapshot.quote.ask_price is not None
    assert snapshot.quote.ask_price.value == Decimal("191.25")
    assert snapshot.quote.bid_size.value == Decimal("10.0")
    assert snapshot.quote.occurred_at == QUOTE_TIME
    assert snapshot.observed_at == NOW
    assert snapshot.bid_exchange == "V"
    assert snapshot.ask_exchange == "V"

    assert len(market.requests) == 1
    request = market.requests[0]
    assert request.symbol_or_symbols == "AAPL"
    assert request.feed is DataFeed.IEX


def test_zero_quote_side_maps_to_absent_price_instead_of_invalid_price() -> None:
    mapping = _mapping()
    service, _, _ = _service(
        mapping,
        quote=_quote(bid_price=0.0, bid_size=0.0),
    )

    snapshot = service.get_latest_quote(mapping.instrument_id)

    assert snapshot.quote.bid_price is None
    assert snapshot.quote.bid_size.value == Decimal("0.0")
    assert snapshot.quote.ask_price is not None


def test_account_snapshot_enforces_expected_provider_account_identity() -> None:
    mapping = _mapping()
    service, trading, _ = _service(mapping)

    snapshot = service.get_account_snapshot()

    assert snapshot.identity.external_account_id == str(ACCOUNT_PROVIDER_ID)
    assert snapshot.cash_balance is not None
    assert snapshot.cash_balance.cash.amount == Decimal("1000.25")
    assert trading.account_queries == 1


def test_position_snapshots_use_reverse_reference_mapping() -> None:
    mapping = _mapping()
    service, trading, _ = _service(mapping)

    snapshots = service.get_position_snapshots()

    assert len(snapshots) == 1
    snapshot = snapshots[0]
    assert snapshot.instrument_id == mapping.instrument_id
    assert snapshot.signed_quantity == Decimal("2.5")
    assert snapshot.average_price.value == Decimal("190.125")
    assert trading.position_queries == 1


def test_unmapped_provider_position_requires_reference_reconciliation() -> None:
    mapping = _mapping(
        symbol="MSFT",
        external_id="99999999-2222-3333-4444-555555555555",
    )
    service, _, _ = _service(mapping, positions=[_position()])

    with pytest.raises(
        ProviderStateReconciliationRequired,
        match="no canonical instrument mapping",
    ):
        service.get_position_snapshots()