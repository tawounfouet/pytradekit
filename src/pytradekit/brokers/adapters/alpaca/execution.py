"""Alpaca PAPER implementation of the broker-neutral ExecutionPort."""

from __future__ import annotations

from decimal import Decimal
from math import isfinite
from typing import Protocol
from uuid import UUID

from alpaca.common.exceptions import APIError
from alpaca.trading.enums import OrderSide as AlpacaOrderSide
from alpaca.trading.enums import TimeInForce as AlpacaTimeInForce
from alpaca.trading.models import Order as AlpacaOrder
from alpaca.trading.requests import (
    LimitOrderRequest,
    MarketOrderRequest,
    OrderRequest,
)

from pytradekit.brokers import (
    ProviderError,
    ProviderExecutionContext,
    ProviderProtocolError,
    ProviderRejectedOperationError,
    ProviderUncertainOutcomeError,
)
from pytradekit.execution import (
    CancelResult,
    CancelStatus,
    ExecutionReport,
    SubmissionResult,
    SubmissionStatus,
)
from pytradekit.orders.domain import Order, OrderSide, OrderType
from pytradekit.reference.domain import InstrumentMapping
from pytradekit.shared import Currency, InstrumentId

from .contract import (
    ALPACA_PROVIDER_KEY,
    supports_order_contract,
    validate_client_order_reference,
)
from .errors import AlpacaOperation, translate_alpaca_error
from .mappers import map_order_query_report, map_submission_ack

_USD = Currency("USD")


class AlpacaCommandClient(Protocol):
    """Minimal write-side Alpaca client required by the execution adapter."""

    def submit_order(self, order_data: OrderRequest) -> object:
        """Submit exactly one order request."""

        ...

    def cancel_order_by_id(self, order_id: UUID | str) -> None:
        """Cancel exactly one provider order."""

        ...


class AlpacaReadClient(Protocol):
    """Minimal read-side Alpaca client required for reconciliation."""

    def get_order_by_id(self, order_id: UUID | str) -> object:
        """Read one provider order by external ID."""

        ...

    def get_order_by_client_id(self, client_id: str) -> object:
        """Read one provider order by client reference."""

        ...


class AlpacaInstrumentResolver(Protocol):
    """Resolve a canonical instrument into its Alpaca provider mapping."""

    def resolve(self, instrument_id: InstrumentId) -> InstrumentMapping | None:
        """Return the provider mapping for one canonical instrument."""

        ...


class AlpacaExecutionAdapter:
    """Translate broker-neutral execution commands into Alpaca PAPER operations."""

    def __init__(
        self,
        *,
        command_client: AlpacaCommandClient,
        read_client: AlpacaReadClient,
        instruments: AlpacaInstrumentResolver,
    ) -> None:
        self._command_client = command_client
        self._read_client = read_client
        self._instruments = instruments

    def submit(self, order: Order) -> SubmissionResult:
        """Submit MARKET or LIMIT once and preserve unknown economic outcomes."""

        contract_rejection = self._validate_submit_contract(order)
        if contract_rejection is not None:
            return contract_rejection

        request = self._build_order_request(order)

        try:
            response = self._command_client.submit_order(request)
        except Exception as exc:
            translated = translate_alpaca_error(
                exc,
                operation=AlpacaOperation.SUBMIT,
            )
            if isinstance(translated, ProviderRejectedOperationError):
                return SubmissionResult(
                    status=SubmissionStatus.REJECTED,
                    reason="Alpaca rejected the order submission.",
                )
            if isinstance(translated, ProviderUncertainOutcomeError):
                return SubmissionResult(
                    status=SubmissionStatus.UNCERTAIN,
                    reason=(
                        "Alpaca submission outcome is unknown and requires "
                        "client_order_id reconciliation."
                    ),
                )
            raise translated from exc

        provider_order = self._require_order_model(
            response,
            operation="submit",
        )
        return map_submission_ack(
            provider_order,
            expected_client_order_reference=self._client_reference(order),
        )

    def cancel(self, order: Order) -> CancelResult:
        """Issue at most one cancel request for one known provider order."""

        external_order_id = order.external_order_id
        if external_order_id is None:
            provider_order = self._read_by_client_reference(order)
            if provider_order is None:
                return CancelResult(
                    status=CancelStatus.UNCERTAIN,
                    reason=(
                        "Alpaca order identity could not be resolved safely; "
                        "cancellation requires reconciliation."
                    ),
                )
            external_order_id = str(provider_order.id)

        provider_order_id = self._provider_order_uuid(external_order_id)

        try:
            self._command_client.cancel_order_by_id(provider_order_id)
        except Exception as exc:
            translated = translate_alpaca_error(
                exc,
                operation=AlpacaOperation.CANCEL,
            )
            if isinstance(translated, ProviderRejectedOperationError):
                return CancelResult(
                    status=CancelStatus.REJECTED,
                    reason="Alpaca rejected the cancellation request.",
                )
            if isinstance(translated, ProviderUncertainOutcomeError):
                return CancelResult(
                    status=CancelStatus.UNCERTAIN,
                    reason=(
                        "Alpaca cancellation outcome is unknown and requires "
                        "order-state reconciliation."
                    ),
                )
            raise translated from exc

        return CancelResult(status=CancelStatus.ACKNOWLEDGED)

    def query_order(self, order: Order) -> ExecutionReport | None:
        """Query latest provider order state without creating synthetic fills."""

        provider_order = self._read_order(order)
        if provider_order is None:
            return None

        return map_order_query_report(
            provider_order,
            context=self._execution_context(order),
        )

    def _validate_submit_contract(self, order: Order) -> SubmissionResult | None:
        if not supports_order_contract(
            order_type=order.order_type,
            time_in_force=order.time_in_force,
        ):
            return SubmissionResult(
                status=SubmissionStatus.REJECTED,
                reason=(
                    "Order shape is outside the frozen Alpaca 0.5 contract "
                    "(MARKET/LIMIT with DAY only)."
                ),
            )
        return None

    def _build_order_request(self, order: Order) -> OrderRequest:
        mapping = self._resolve_instrument(order.instrument_id)
        client_reference = self._client_reference(order)
        side = (
            AlpacaOrderSide.BUY
            if order.side is OrderSide.BUY
            else AlpacaOrderSide.SELL
        )
        quantity = self._provider_float(
            order.quantity.value,
            field_name="quantity",
        )

        try:
            if order.order_type is OrderType.MARKET:
                return MarketOrderRequest(
                    symbol=mapping.external_symbol,
                    qty=quantity,
                    side=side,
                    time_in_force=AlpacaTimeInForce.DAY,
                    client_order_id=client_reference,
                )

            if order.order_type is OrderType.LIMIT:
                if order.limit_price is None:
                    raise self._protocol_error(
                        "Canonical LIMIT order is missing limit_price.",
                        operation="submit",
                    )
                return LimitOrderRequest(
                    symbol=mapping.external_symbol,
                    qty=quantity,
                    side=side,
                    time_in_force=AlpacaTimeInForce.DAY,
                    client_order_id=client_reference,
                    limit_price=self._provider_float(
                        order.limit_price.value,
                        field_name="limit_price",
                    ),
                )
        except ProviderError:
            raise
        except (TypeError, ValueError) as exc:
            raise self._protocol_error(
                "Canonical order could not be represented by the Alpaca SDK request model.",
                operation="submit",
            ) from exc

        raise self._protocol_error(
            f"Unsupported canonical order type {order.order_type.value!r}.",
            operation="submit",
        )

    def _read_order(self, order: Order) -> AlpacaOrder | None:
        if order.external_order_id is not None:
            provider_order_id = self._provider_order_uuid(order.external_order_id)
            try:
                response = self._read_client.get_order_by_id(provider_order_id)
            except APIError as exc:
                if self._api_status_code(exc) == 404:
                    return None
                raise translate_alpaca_error(
                    exc,
                    operation=AlpacaOperation.READ,
                ) from exc
            except Exception as exc:
                raise translate_alpaca_error(
                    exc,
                    operation=AlpacaOperation.READ,
                ) from exc
            return self._require_order_model(response, operation="query_order")

        return self._read_by_client_reference(order)

    def _read_by_client_reference(self, order: Order) -> AlpacaOrder | None:
        client_reference = self._client_reference(order)
        try:
            response = self._read_client.get_order_by_client_id(client_reference)
        except APIError as exc:
            if self._api_status_code(exc) == 404:
                return None
            raise translate_alpaca_error(
                exc,
                operation=AlpacaOperation.READ,
            ) from exc
        except Exception as exc:
            raise translate_alpaca_error(
                exc,
                operation=AlpacaOperation.READ,
            ) from exc
        return self._require_order_model(response, operation="query_order")

    def _resolve_instrument(self, instrument_id: InstrumentId) -> InstrumentMapping:
        mapping = self._instruments.resolve(instrument_id)
        if mapping is None:
            raise self._protocol_error(
                "No Alpaca instrument mapping exists for the canonical instrument.",
                operation="submit",
            )
        if mapping.instrument_id != instrument_id:
            raise self._protocol_error(
                "Resolved Alpaca instrument mapping does not match canonical instrument.",
                operation="submit",
            )
        if mapping.provider.strip().lower() != ALPACA_PROVIDER_KEY:
            raise self._protocol_error(
                "Resolved instrument mapping does not belong to Alpaca.",
                operation="submit",
            )
        return mapping

    @staticmethod
    def _client_reference(order: Order) -> str:
        if order.client_order_id is None:
            raise ProviderProtocolError(
                "Canonical order is missing client_order_id.",
                provider=ALPACA_PROVIDER_KEY,
                operation="map_order",
            )
        try:
            return validate_client_order_reference(order.client_order_id)
        except ValueError as exc:
            raise ProviderProtocolError(
                "Canonical order client_order_id violates the Alpaca contract.",
                provider=ALPACA_PROVIDER_KEY,
                operation="map_order",
            ) from exc

    @staticmethod
    def _execution_context(order: Order) -> ProviderExecutionContext:
        return ProviderExecutionContext(
            order_id=order.id,
            correlation_id=order.correlation_id,
            client_order_reference=AlpacaExecutionAdapter._client_reference(order),
            quote_currency=_USD,
        )

    @staticmethod
    def _provider_order_uuid(value: str) -> UUID:
        try:
            return UUID(value)
        except ValueError as exc:
            raise ProviderProtocolError(
                "Alpaca external order ID must be a UUID.",
                provider=ALPACA_PROVIDER_KEY,
                operation="map_order",
            ) from exc

    @staticmethod
    def _provider_float(value: Decimal, *, field_name: str) -> float:
        encoded = float(value)
        if not isfinite(encoded) or Decimal(str(encoded)) != value:
            raise ProviderProtocolError(
                f"Canonical {field_name} cannot be represented safely by alpaca-py.",
                provider=ALPACA_PROVIDER_KEY,
                operation="submit",
            )
        return encoded

    @staticmethod
    def _require_order_model(value: object, *, operation: str) -> AlpacaOrder:
        if not isinstance(value, AlpacaOrder):
            raise ProviderProtocolError(
                "Alpaca client returned an unexpected order payload type.",
                provider=ALPACA_PROVIDER_KEY,
                operation=operation,
            )
        return value

    @staticmethod
    def _api_status_code(error: APIError) -> int | None:
        try:
            value: object = error.status_code
        except Exception:
            return None
        return value if isinstance(value, int) else None

    @staticmethod
    def _protocol_error(message: str, *, operation: str) -> ProviderProtocolError:
        return ProviderProtocolError(
            message,
            provider=ALPACA_PROVIDER_KEY,
            operation=operation,
        )
