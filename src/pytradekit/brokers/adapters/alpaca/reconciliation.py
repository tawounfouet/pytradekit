"""Alpaca execution-history observations for reconciliation."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Protocol

from pytradekit.brokers import ProviderProtocolError
from pytradekit.orders.domain import OrderId
from pytradekit.reconciliation.domain import CanonicalFill, ExternalActivityOrigin
from pytradekit.shared import Currency

from .contract import ALPACA_PROVIDER_KEY


class AlpacaActivityClient(Protocol):
    """Minimal read-only REST surface used for account activities."""

    def get(
        self,
        path: str,
        data: dict[str, object] | None = None,
    ) -> object: ...


class OrderIdentityResolver(Protocol):
    """Resolve provider order identity to a canonical OrderId when known."""

    def resolve_order_id(self, external_order_id: str) -> OrderId | None: ...


class AlpacaExternalActivityReader:
    """Read stable Alpaca FILL activities without fabricating executions."""

    def __init__(
        self,
        *,
        client: AlpacaActivityClient,
        orders: OrderIdentityResolver,
        currency: Currency | None = None,
    ) -> None:
        self._client = client
        self._orders = orders
        self._currency = currency or Currency("USD")

    def list_fills(self) -> tuple[CanonicalFill, ...]:
        """Return provider executions identified by stable activity IDs."""

        raw = self._client.get(
            "/account/activities/FILL",
            data={"direction": "asc", "page_size": 100},
        )
        if not isinstance(raw, list):
            raise self._protocol_error("Alpaca FILL activities response must be a list.")

        result: list[CanonicalFill] = []
        for item in raw:
            if not isinstance(item, dict):
                raise self._protocol_error("Alpaca FILL activity must be a JSON object.")
            activity_id = _required_text(item, "id")
            external_order_id = _required_text(item, "order_id")
            order_id = self._orders.resolve_order_id(external_order_id)
            result.append(
                CanonicalFill(
                    external_fill_id=activity_id,
                    order_id=order_id,
                    external_order_id=external_order_id,
                    quantity=_required_decimal(item, "qty"),
                    price=_required_decimal(item, "price"),
                    currency=self._currency,
                    occurred_at=_required_datetime(item, "transaction_time"),
                    origin=(
                        ExternalActivityOrigin.INTERNAL
                        if order_id is not None
                        else ExternalActivityOrigin.UNKNOWN_EXTERNAL
                    ),
                )
            )
        result.sort(key=lambda fill: (fill.occurred_at, fill.external_fill_id))
        return tuple(result)

    @staticmethod
    def _protocol_error(message: str) -> ProviderProtocolError:
        return ProviderProtocolError(
            message,
            provider=ALPACA_PROVIDER_KEY,
            operation="account_fill_activities",
        )


def _required_text(value: dict[object, object], key: str) -> str:
    raw = value.get(key)
    normalized = str(raw).strip() if raw is not None else ""
    if not normalized:
        raise AlpacaExternalActivityReader._protocol_error(
            f"Alpaca FILL activity is missing {key}."
        )
    return normalized


def _required_decimal(value: dict[object, object], key: str) -> Decimal:
    raw = _required_text(value, key)
    try:
        parsed = Decimal(raw)
    except Exception as exc:
        raise AlpacaExternalActivityReader._protocol_error(
            f"Alpaca FILL activity {key} is not a Decimal."
        ) from exc
    if not parsed.is_finite() or parsed <= 0:
        raise AlpacaExternalActivityReader._protocol_error(
            f"Alpaca FILL activity {key} must be positive."
        )
    return parsed


def _required_datetime(value: dict[object, object], key: str) -> datetime:
    raw = _required_text(value, key)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AlpacaExternalActivityReader._protocol_error(
            f"Alpaca FILL activity {key} is not ISO-8601."
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise AlpacaExternalActivityReader._protocol_error(
            f"Alpaca FILL activity {key} must be timezone-aware."
        )
    return parsed
