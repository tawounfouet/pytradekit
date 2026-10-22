"""Read-only Alpaca asset, market-data, account, and position snapshots."""

from __future__ import annotations

from typing import Protocol

from alpaca.data.enums import DataFeed
from alpaca.data.models.quotes import Quote as AlpacaQuote
from alpaca.data.requests import StockLatestQuoteRequest
from alpaca.trading.models import Asset, Position, TradeAccount

from pytradekit.brokers import (
    ProviderAccountSnapshot,
    ProviderInstrumentSnapshot,
    ProviderPositionSnapshot,
    ProviderProtocolError,
    ProviderQuoteSnapshot,
    ProviderStateReconciliationRequired,
)
from pytradekit.portfolio.domain import AccountId
from pytradekit.reference.domain import InstrumentMapping
from pytradekit.runtime.ports import ClockPort
from pytradekit.shared import Currency, InstrumentId

from .contract import ALPACA_PROVIDER_KEY
from .errors import AlpacaOperation, translate_alpaca_error
from .mappers import (
    map_account_snapshot,
    map_asset_snapshot,
    map_latest_quote,
    map_position_snapshot,
)


class AlpacaSnapshotTradingClient(Protocol):
    """Read-only Trading API surface required by LOT-08."""

    def get_asset(self, symbol_or_asset_id: object) -> object:
        """Return one provider asset."""

        ...

    def get_account(self) -> object:
        """Return provider account state."""

        ...

    def get_all_positions(self) -> object:
        """Return provider open positions."""

        ...


class AlpacaStockDataClient(Protocol):
    """Read-only stock market-data surface required by LOT-08."""

    def get_stock_latest_quote(self, request_params: StockLatestQuoteRequest) -> object:
        """Return latest level-1 quotes keyed by provider symbol."""

        ...


class AlpacaSnapshotReferenceResolver(Protocol):
    """Bidirectional instrument mapping boundary required by snapshot reads."""

    def resolve(self, instrument_id: InstrumentId) -> InstrumentMapping | None:
        """Resolve canonical instrument to Alpaca mapping."""

        ...

    def resolve_provider(
        self,
        *,
        external_id: str | None,
        external_symbol: str,
    ) -> InstrumentMapping | None:
        """Resolve provider identity to canonical instrument mapping."""

        ...


class AlpacaMarketDataSnapshots:
    """Read-only facade over Alpaca reference, market data, account, and positions."""

    def __init__(
        self,
        *,
        trading_client: AlpacaSnapshotTradingClient,
        market_data_client: AlpacaStockDataClient,
        references: AlpacaSnapshotReferenceResolver,
        account_id: AccountId,
        expected_external_account_id: str,
        clock: ClockPort,
    ) -> None:
        expected = expected_external_account_id.strip()
        if not expected:
            raise ProviderProtocolError(
                "Expected Alpaca account identity must not be empty.",
                provider=ALPACA_PROVIDER_KEY,
                operation="configure_snapshots",
            )
        self._trading_client = trading_client
        self._market_data_client = market_data_client
        self._references = references
        self._account_id = account_id
        self._expected_external_account_id = expected
        self._clock = clock

    def get_asset_snapshot(self, instrument_id: InstrumentId) -> ProviderInstrumentSnapshot:
        """Load and translate one Alpaca US equity asset."""

        mapping = self._require_mapping(instrument_id)
        lookup: object = mapping.external_id or mapping.external_symbol

        try:
            response = self._trading_client.get_asset(lookup)
        except Exception as exc:
            raise translate_alpaca_error(exc, operation=AlpacaOperation.READ) from exc

        asset = self._require_asset(response)
        self._validate_asset_against_mapping(asset, mapping)
        return map_asset_snapshot(
            asset,
            instrument_id=instrument_id,
            observed_at=self._clock.now(),
        )

    def get_latest_quote(self, instrument_id: InstrumentId) -> ProviderQuoteSnapshot:
        """Load latest IEX quote and translate it into canonical market data."""

        mapping = self._require_mapping(instrument_id)
        request = StockLatestQuoteRequest(
            symbol_or_symbols=mapping.external_symbol,
            feed=DataFeed.IEX,
        )

        try:
            response = self._market_data_client.get_stock_latest_quote(request)
        except Exception as exc:
            raise translate_alpaca_error(exc, operation=AlpacaOperation.READ) from exc

        if not isinstance(response, dict):
            raise self._protocol_error(
                "Alpaca latest quote response must be keyed by symbol.",
                operation="latest_quote",
            )

        raw_quote = response.get(mapping.external_symbol)
        if not isinstance(raw_quote, AlpacaQuote):
            raise self._protocol_error(
                "Alpaca latest quote response is missing the requested symbol.",
                operation="latest_quote",
            )

        return map_latest_quote(
            raw_quote,
            mapping=mapping,
            quote_currency=Currency("USD"),
            feed=DataFeed.IEX.value,
            observed_at=self._clock.now(),
        )

    def get_account_snapshot(self) -> ProviderAccountSnapshot:
        """Load the configured Alpaca account and map it to canonical portfolio data."""

        try:
            response = self._trading_client.get_account()
        except Exception as exc:
            raise translate_alpaca_error(exc, operation=AlpacaOperation.READ) from exc

        account = self._require_account(response)
        if str(account.id) != self._expected_external_account_id:
            raise self._protocol_error(
                "Alpaca account identity does not match the configured runtime account.",
                operation="account_snapshot",
            )

        return map_account_snapshot(
            account,
            account_id=self._account_id,
            observed_at=self._clock.now(),
        )

    def get_position_snapshots(self) -> tuple[ProviderPositionSnapshot, ...]:
        """Load all open Alpaca positions and translate every mapped US equity."""

        try:
            response = self._trading_client.get_all_positions()
        except Exception as exc:
            raise translate_alpaca_error(exc, operation=AlpacaOperation.READ) from exc

        if not isinstance(response, list):
            raise self._protocol_error(
                "Alpaca positions response must be a list.",
                operation="position_snapshots",
            )

        observed_at = self._clock.now()
        snapshots: list[ProviderPositionSnapshot] = []

        for raw_position in response:
            position = self._require_position(raw_position)
            mapping = self._references.resolve_provider(
                external_id=str(position.asset_id),
                external_symbol=position.symbol,
            )
            if mapping is None:
                raise ProviderStateReconciliationRequired(
                    (
                        "Alpaca position has no canonical instrument mapping; "
                        "reference reconciliation is required."
                    ),
                    provider=ALPACA_PROVIDER_KEY,
                    operation="position_snapshots",
                )
            if mapping.provider.strip().lower() != ALPACA_PROVIDER_KEY:
                raise self._protocol_error(
                    "Resolved position mapping does not belong to Alpaca.",
                    operation="position_snapshots",
                )

            snapshots.append(
                map_position_snapshot(
                    position,
                    account_id=self._account_id,
                    instrument_id=mapping.instrument_id,
                    quote_currency=Currency("USD"),
                    observed_at=observed_at,
                )
            )

        snapshots.sort(
            key=lambda snapshot: snapshot.provider_instrument.external_symbol
        )
        return tuple(snapshots)

    def _require_mapping(self, instrument_id: InstrumentId) -> InstrumentMapping:
        mapping = self._references.resolve(instrument_id)
        if mapping is None:
            raise ProviderStateReconciliationRequired(
                "Canonical instrument has no Alpaca mapping.",
                provider=ALPACA_PROVIDER_KEY,
                operation="reference_snapshot",
            )
        if mapping.provider.strip().lower() != ALPACA_PROVIDER_KEY:
            raise self._protocol_error(
                "Resolved instrument mapping does not belong to Alpaca.",
                operation="reference_snapshot",
            )
        return mapping

    @staticmethod
    def _validate_asset_against_mapping(
        asset: Asset,
        mapping: InstrumentMapping,
    ) -> None:
        if asset.symbol != mapping.external_symbol:
            raise ProviderProtocolError(
                "Alpaca asset symbol does not match configured instrument mapping.",
                provider=ALPACA_PROVIDER_KEY,
                operation="asset_snapshot",
            )
        if mapping.external_id is not None and str(asset.id) != mapping.external_id:
            raise ProviderProtocolError(
                "Alpaca asset ID does not match configured instrument mapping.",
                provider=ALPACA_PROVIDER_KEY,
                operation="asset_snapshot",
            )

    @staticmethod
    def _require_asset(value: object) -> Asset:
        if not isinstance(value, Asset):
            raise ProviderProtocolError(
                "Alpaca asset query returned an unexpected payload type.",
                provider=ALPACA_PROVIDER_KEY,
                operation="asset_snapshot",
            )
        return value

    @staticmethod
    def _require_account(value: object) -> TradeAccount:
        if not isinstance(value, TradeAccount):
            raise ProviderProtocolError(
                "Alpaca account query returned an unexpected payload type.",
                provider=ALPACA_PROVIDER_KEY,
                operation="account_snapshot",
            )
        return value

    @staticmethod
    def _require_position(value: object) -> Position:
        if not isinstance(value, Position):
            raise ProviderProtocolError(
                "Alpaca positions query returned an unexpected payload type.",
                provider=ALPACA_PROVIDER_KEY,
                operation="position_snapshots",
            )
        return value

    @staticmethod
    def _protocol_error(message: str, *, operation: str) -> ProviderProtocolError:
        return ProviderProtocolError(
            message,
            provider=ALPACA_PROVIDER_KEY,
            operation=operation,
        )
