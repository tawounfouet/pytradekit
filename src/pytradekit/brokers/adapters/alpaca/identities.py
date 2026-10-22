"""Translate Alpaca identities into provider-neutral identity models."""

from __future__ import annotations

from alpaca.trading.models import Asset, Order, TradeAccount, TradeUpdate

from pytradekit.brokers import (
    ProviderAccountIdentity,
    ProviderFillIdentity,
    ProviderInstrumentIdentity,
    ProviderOrderIdentity,
    ProviderProtocolError,
)

from .contract import ALPACA_PROVIDER_KEY


def map_order_identity(order: Order) -> ProviderOrderIdentity:
    """Map Alpaca Order identifiers without promoting them to canonical IDs."""

    client_reference = order.client_order_id.strip()
    external_order_id = str(order.id).strip()
    if not client_reference or not external_order_id:
        raise _identity_error("Alpaca order identity is incomplete.")
    return ProviderOrderIdentity(
        provider=ALPACA_PROVIDER_KEY,
        client_reference=client_reference,
        external_order_id=external_order_id,
    )


def map_fill_identity(update: TradeUpdate) -> ProviderFillIdentity:
    """Map an Alpaca execution ID into an external fill identity."""

    if update.execution_id is None:
        raise _identity_error("Alpaca fill event is missing execution_id.")
    return ProviderFillIdentity(
        provider=ALPACA_PROVIDER_KEY,
        external_fill_id=str(update.execution_id),
    )


def map_account_identity(account: TradeAccount) -> ProviderAccountIdentity:
    """Map the Alpaca account UUID while ignoring account_number as an identity."""

    external_account_id = str(account.id).strip()
    if not external_account_id:
        raise _identity_error("Alpaca account identity is empty.")
    return ProviderAccountIdentity(
        provider=ALPACA_PROVIDER_KEY,
        external_account_id=external_account_id,
    )


def map_instrument_identity(asset: Asset) -> ProviderInstrumentIdentity:
    """Map Alpaca asset UUID and symbol into provider-neutral external identity."""

    external_id = str(asset.id).strip()
    external_symbol = asset.symbol.strip()
    if not external_id or not external_symbol:
        raise _identity_error("Alpaca asset identity is incomplete.")
    return ProviderInstrumentIdentity(
        provider=ALPACA_PROVIDER_KEY,
        external_id=external_id,
        external_symbol=external_symbol,
    )


def _identity_error(message: str) -> ProviderProtocolError:
    return ProviderProtocolError(
        message,
        provider=ALPACA_PROVIDER_KEY,
        operation="map_identity",
    )
