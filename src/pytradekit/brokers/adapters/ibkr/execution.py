"""IBKR PAPER economic-write execution adapter."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Protocol, cast

from pytradekit.brokers import (
    ProviderExecutionContext,
    ProviderProtocolError,
    ProviderRejectedOperationError,
)
from pytradekit.execution import (
    CancelResult,
    CancelStatus,
    ExecutionReport,
    SubmissionResult,
    SubmissionStatus,
)
from pytradekit.orders.domain import Order
from pytradekit.runtime.ports import ClockPort
from pytradekit.shared import InstrumentId

from .contract_mapping import (
    IBKRContractRecord,
    IBKRInstrumentMappingResult,
    IBKRPriceIncrementMode,
)
from .discovery import IBKR_PROVIDER_KEY
from .identities import (
    IBKRClientId,
    IBKROrderReference,
    IBKRPermanentOrderId,
    IBKRSessionOrderId,
)
from .market_rules import (
    IBKRMarketRuleError,
    IBKRMarketRuleResolver,
    IBKRMarketRuleValidationEvidence,
)
from .operations_runtime import IBKROperationalGuard
from .order_callbacks import map_ibkr_order_status_report
from .order_commands import (
    IBKROrderCommandError,
    IBKROrderType,
    IBKRPlacementCommand,
    IBKRTransmitPolicy,
    map_ibkr_order_command,
)
from .order_session import (
    IBKROrderSessionReservation,
    IBKROrderSessionRuntime,
)
from .runtime import IBKRPaperConnectionRuntime

IBKR_ECONOMIC_WRITE_VERSION = "0.8.0b6-lot06.5"


class IBKRExecutionAdapterError(ValueError):
    """Raised when the provider execution adapter is configured unsafely."""


class _IBKRCommandClient(Protocol):
    def placeOrder(self, contract: object, order: object) -> object:
        """Place exactly one provider order and return its Trade object."""

        ...

    def cancelOrder(
        self,
        order: object,
        manualCancelOrderTime: str = "",
    ) -> object | None:
        """Cancel exactly one provider order."""

        ...

    def trades(self) -> list[object]:
        """Return synchronized provider trades."""

        ...


class _IBKRSDKConstructor(Protocol):
    def __call__(self, **kwargs: object) -> object:
        ...


class _ProviderOrderLike(Protocol):
    orderId: int
    clientId: int
    permId: int
    orderRef: str
    account: str


class _ProviderOrderStatusLike(Protocol):
    orderId: int
    status: str
    permId: int
    clientId: int


class _ProviderTradeLike(Protocol):
    order: object
    orderStatus: object


@dataclass(frozen=True, slots=True)
class IBKREconomicWriteAdmission:
    """Explicit provider-local prerequisites for controlled PAPER writes."""

    paper_endpoint_verified: bool
    account_ready: bool
    reconciliation_complete: bool
    api_read_only: bool
    economic_write_enabled: bool

    def __post_init__(self) -> None:
        for field_name in (
            "paper_endpoint_verified",
            "account_ready",
            "reconciliation_complete",
            "api_read_only",
            "economic_write_enabled",
        ):
            if type(getattr(self, field_name)) is not bool:
                raise IBKRExecutionAdapterError(
                    f"{field_name} must be a bool."
                )

    @property
    def admitted(self) -> bool:
        return (
            self.paper_endpoint_verified
            and self.account_ready
            and self.reconciliation_complete
            and not self.api_read_only
            and self.economic_write_enabled
        )

    def require(self, *, operation: str) -> None:
        if self.admitted:
            return
        raise ProviderRejectedOperationError(
            "IBKR PAPER economic-write admission is closed.",
            provider=IBKR_PROVIDER_KEY,
            operation=operation,
        )


@dataclass(frozen=True, slots=True)
class IBKRExecutionInstrumentBinding:
    """Qualified contract and canonical mapping used for execution."""

    contract: IBKRContractRecord
    mapping: IBKRInstrumentMappingResult

    def __post_init__(self) -> None:
        if not isinstance(self.contract, IBKRContractRecord):
            raise IBKRExecutionAdapterError(
                "contract must be an IBKRContractRecord."
            )
        if not isinstance(self.mapping, IBKRInstrumentMappingResult):
            raise IBKRExecutionAdapterError(
                "mapping must be an IBKRInstrumentMappingResult."
            )
        if self.mapping.identity.external_id != str(self.contract.contract_id):
            raise IBKRExecutionAdapterError(
                "execution binding conId does not match provider mapping."
            )
        if self.mapping.identity.external_symbol != self.contract.symbol:
            raise IBKRExecutionAdapterError(
                "execution binding symbol does not match provider mapping."
            )


class IBKRExecutionInstrumentResolver(Protocol):
    """Resolve a canonical instrument into one qualified IBKR execution binding."""

    def resolve(
        self,
        instrument_id: InstrumentId,
    ) -> IBKRExecutionInstrumentBinding | None:
        """Return the qualified execution binding or None."""

        ...


class StaticIBKRExecutionInstrumentResolver:
    """Deterministic resolver for explicitly qualified execution bindings."""

    def __init__(
        self,
        bindings: tuple[IBKRExecutionInstrumentBinding, ...],
    ) -> None:
        self._bindings: dict[
            InstrumentId,
            IBKRExecutionInstrumentBinding,
        ] = {}
        for binding in bindings:
            if not isinstance(binding, IBKRExecutionInstrumentBinding):
                raise IBKRExecutionAdapterError(
                    "bindings must contain IBKRExecutionInstrumentBinding values."
                )
            instrument_id = binding.mapping.instrument.id
            if instrument_id in self._bindings:
                raise IBKRExecutionAdapterError(
                    "execution bindings must be unique by InstrumentId."
                )
            self._bindings[instrument_id] = binding

    def resolve(
        self,
        instrument_id: InstrumentId,
    ) -> IBKRExecutionInstrumentBinding | None:
        if not isinstance(instrument_id, InstrumentId):
            raise IBKRExecutionAdapterError(
                "instrument_id must be an InstrumentId."
            )
        return self._bindings.get(instrument_id)


@dataclass(frozen=True, slots=True)
class IBKRSDKPlacement:
    """Provider SDK objects built before the one economic write call."""

    contract: object
    order: object


@dataclass(frozen=True, slots=True)
class IBKREconomicWriteAttempt:
    """Sanitized facts retained for the latest provider write attempt."""

    operation: str
    reservation: IBKROrderSessionReservation
    provider_call_attempted: bool
    provider_returned: bool
    permanent_order_id: IBKRPermanentOrderId | None
    provider_status: str | None


class IBKRSDKPlacementFactory:
    """Build ib_async Contract and Order objects behind the IBKR boundary."""

    def __init__(
        self,
        *,
        contract_constructor: _IBKRSDKConstructor | None = None,
        order_constructor: _IBKRSDKConstructor | None = None,
    ) -> None:
        self._contract_constructor = contract_constructor
        self._order_constructor = order_constructor

    def build(
        self,
        *,
        placement: IBKRPlacementCommand,
        reservation: IBKROrderSessionReservation,
        account_id: str,
    ) -> IBKRSDKPlacement:
        if not isinstance(placement, IBKRPlacementCommand):
            raise IBKRExecutionAdapterError(
                "placement must be an IBKRPlacementCommand."
            )
        if not isinstance(reservation, IBKROrderSessionReservation):
            raise IBKRExecutionAdapterError(
                "reservation must be an IBKROrderSessionReservation."
            )
        normalized_account = account_id.strip() if isinstance(account_id, str) else ""
        if not normalized_account:
            raise IBKRExecutionAdapterError(
                "account_id must be non-empty."
            )
        if placement.order.order_reference != reservation.order_reference:
            raise IBKRExecutionAdapterError(
                "placement orderRef does not match the reserved orderRef."
            )

        contract_constructor, order_constructor = self._constructors()
        contract = placement.contract
        contract_kwargs: dict[str, object] = {
            "conId": contract.contract_id.value,
            "symbol": contract.symbol,
            "secType": contract.security_type.value,
            "exchange": contract.exchange,
            "primaryExchange": contract.primary_exchange,
            "currency": contract.currency,
            "localSymbol": contract.local_symbol,
        }
        if contract.trading_class is not None:
            contract_kwargs["tradingClass"] = contract.trading_class

        order = placement.order
        order_kwargs: dict[str, object] = {
            "orderId": reservation.session_order_id.value,
            "action": order.action.value,
            "totalQuantity": order.total_quantity,
            "orderType": order.order_type.value,
            "tif": order.time_in_force.value,
            "orderRef": order.order_reference.value,
            "transmit": (
                order.transmit_policy is IBKRTransmitPolicy.TRANSMIT
            ),
            "outsideRth": order.outside_regular_trading_hours,
            "whatIf": order.what_if,
            "overridePercentageConstraints": (
                order.override_percentage_constraints
            ),
            "account": normalized_account,
        }
        if order.order_type is IBKROrderType.LIMIT:
            order_kwargs["lmtPrice"] = order.limit_price

        try:
            return IBKRSDKPlacement(
                contract=contract_constructor(**contract_kwargs),
                order=order_constructor(**order_kwargs),
            )
        except Exception as exc:
            raise ProviderProtocolError(
                "IBKR SDK placement objects could not be constructed safely.",
                provider=IBKR_PROVIDER_KEY,
                operation="submit",
            ) from exc

    def _constructors(
        self,
    ) -> tuple[_IBKRSDKConstructor, _IBKRSDKConstructor]:
        if (
            self._contract_constructor is not None
            and self._order_constructor is not None
        ):
            return self._contract_constructor, self._order_constructor

        try:
            module = import_module("ib_async")
            contract_constructor = cast(
                _IBKRSDKConstructor,
                module.Contract,
            )
            order_constructor = cast(
                _IBKRSDKConstructor,
                module.Order,
            )
        except (ImportError, AttributeError) as exc:
            raise ProviderProtocolError(
                "ib_async Contract or Order is unavailable.",
                provider=IBKR_PROVIDER_KEY,
                operation="submit",
            ) from exc

        return (
            self._contract_constructor or contract_constructor,
            self._order_constructor or order_constructor,
        )


class IBKRExecutionAdapter:
    """Execute qualified IBKR PAPER writes exactly once per application call."""

    def __init__(
        self,
        *,
        connection: IBKRPaperConnectionRuntime,
        session: IBKROrderSessionRuntime,
        instruments: IBKRExecutionInstrumentResolver,
        admission: IBKREconomicWriteAdmission,
        operations: IBKROperationalGuard,
        clock: ClockPort,
        market_rules: IBKRMarketRuleResolver | None = None,
        sdk_factory: IBKRSDKPlacementFactory | None = None,
    ) -> None:
        if not isinstance(connection, IBKRPaperConnectionRuntime):
            raise IBKRExecutionAdapterError(
                "connection must be an IBKRPaperConnectionRuntime."
            )
        if not isinstance(session, IBKROrderSessionRuntime):
            raise IBKRExecutionAdapterError(
                "session must be an IBKROrderSessionRuntime."
            )
        if not isinstance(admission, IBKREconomicWriteAdmission):
            raise IBKRExecutionAdapterError(
                "admission must be an IBKREconomicWriteAdmission."
            )
        if not isinstance(operations, IBKROperationalGuard):
            raise IBKRExecutionAdapterError(
                "operations must be an IBKROperationalGuard."
            )
        if market_rules is not None and not isinstance(
            market_rules,
            IBKRMarketRuleResolver,
        ):
            raise IBKRExecutionAdapterError(
                "market_rules must be an IBKRMarketRuleResolver or None."
            )
        self._connection = connection
        self._session = session
        self._instruments = instruments
        self._admission = admission
        self._operations = operations
        self._clock = clock
        self._market_rules = market_rules
        self._sdk_factory = sdk_factory or IBKRSDKPlacementFactory()
        self._last_attempt: IBKREconomicWriteAttempt | None = None
        self._last_market_rule_evidence: (
            IBKRMarketRuleValidationEvidence | None
        ) = None

    @property
    def last_attempt(self) -> IBKREconomicWriteAttempt | None:
        return self._last_attempt

    @property
    def last_market_rule_evidence(
        self,
    ) -> IBKRMarketRuleValidationEvidence | None:
        return self._last_market_rule_evidence

    def submit(self, order: Order) -> SubmissionResult:
        """Submit one qualified PAPER order with no automatic retry."""

        if not isinstance(order, Order):
            raise IBKRExecutionAdapterError(
                "order must be a canonical Order."
            )
        self._operations.require_write_allowed(operation="submit")
        self._admission.require(operation="submit")
        self._last_market_rule_evidence = None

        binding = self._instruments.resolve(order.instrument_id)
        if binding is None:
            return SubmissionResult(
                status=SubmissionStatus.REJECTED,
                reason=(
                    "No qualified IBKR execution binding exists for the "
                    "canonical instrument."
                ),
            )

        try:
            placement = map_ibkr_order_command(
                order,
                contract=binding.contract,
                instrument=binding.mapping,
            )
        except IBKROrderCommandError as exc:
            return SubmissionResult(
                status=SubmissionStatus.REJECTED,
                reason=f"IBKR order mapping rejected the submission: {exc}",
            )

        if (
            placement.order.order_type is IBKROrderType.LIMIT
            and placement.price_increment_mode
            is IBKRPriceIncrementMode.MARKET_RULE
        ):
            if self._market_rules is None:
                return SubmissionResult(
                    status=SubmissionStatus.REJECTED,
                    reason=(
                        "IBKR LIMIT execution requires configured dynamic "
                        "market-rule validation before economic write."
                    ),
                )
            limit_price = placement.order.limit_price
            if limit_price is None:
                raise IBKRExecutionAdapterError(
                    "LIMIT placement must retain limit_price."
                )
            try:
                evidence = self._market_rules.validate_limit_price(
                    instrument=binding.mapping,
                    price=limit_price,
                )
            except IBKRMarketRuleError as exc:
                return SubmissionResult(
                    status=SubmissionStatus.REJECTED,
                    reason=(
                        "IBKR dynamic market-rule validation rejected the "
                        f"LIMIT price: {exc}"
                    ),
                )
            self._last_market_rule_evidence = evidence
            if not evidence.valid:
                return SubmissionResult(
                    status=SubmissionStatus.REJECTED,
                    reason=(
                        "IBKR LIMIT price does not conform to the active "
                        "dynamic market-rule increment."
                    ),
                )

        self._operations.require_write_allowed(operation="submit")
        context = ProviderExecutionContext(
            order_id=order.id,
            correlation_id=order.correlation_id,
            client_order_reference=placement.order.order_reference.value,
            quote_currency=binding.mapping.instrument.quote_currency,
        )
        reservation = self._session.reserve(context)
        client = self._client()

        collision = _find_trade(
            client.trades(),
            client_id=reservation.client_id,
            session_order_id=reservation.session_order_id,
        )
        if collision is not None:
            raise ProviderProtocolError(
                "IBKR reserved order route already exists in synchronized trades.",
                provider=IBKR_PROVIDER_KEY,
                operation="submit",
            )

        sdk = self._sdk_factory.build(
            placement=placement,
            reservation=reservation,
            account_id=self._connection.profile.expected_account_id,
        )

        self._last_attempt = IBKREconomicWriteAttempt(
            operation="submit",
            reservation=reservation,
            provider_call_attempted=True,
            provider_returned=False,
            permanent_order_id=None,
            provider_status=None,
        )
        try:
            trade = client.placeOrder(sdk.contract, sdk.order)
        except Exception:
            return SubmissionResult(
                status=SubmissionStatus.UNCERTAIN,
                reason=(
                    "IBKR placeOrder was attempted once and its economic outcome "
                    "is unknown; reconcile by orderRef and reserved session route."
                ),
            )

        normalized = _normalize_trade(
            trade,
            expected_client_id=reservation.client_id,
            expected_session_order_id=reservation.session_order_id,
            expected_order_reference=reservation.order_reference,
            expected_account_id=self._connection.profile.expected_account_id,
        )
        if normalized is None:
            self._last_attempt = IBKREconomicWriteAttempt(
                operation="submit",
                reservation=reservation,
                provider_call_attempted=True,
                provider_returned=True,
                permanent_order_id=None,
                provider_status=None,
            )
            return SubmissionResult(
                status=SubmissionStatus.UNCERTAIN,
                reason=(
                    "IBKR placeOrder returned an unqualified Trade payload; "
                    "reconciliation is required and the write must not be retried."
                ),
            )

        provider_order, provider_status = normalized
        permanent_order_id = _permanent_order_id(provider_order.permId)
        self._last_attempt = IBKREconomicWriteAttempt(
            operation="submit",
            reservation=reservation,
            provider_call_attempted=True,
            provider_returned=True,
            permanent_order_id=permanent_order_id,
            provider_status=provider_status.status,
        )

        if permanent_order_id is None:
            return SubmissionResult(
                status=SubmissionStatus.UNCERTAIN,
                reason=(
                    "IBKR accepted the local placement call but no durable permId "
                    "is observable yet; wait for callback or reconciliation."
                ),
            )

        try:
            self._session.identities.bind_permanent_order_id(
                client_id=reservation.client_id,
                session_order_id=reservation.session_order_id,
                permanent_order_id=permanent_order_id,
            )
        except ValueError:
            return SubmissionResult(
                status=SubmissionStatus.UNCERTAIN,
                reason=(
                    "IBKR returned a permId that conflicts with the reserved "
                    "identity; reconciliation is required."
                ),
            )

        return SubmissionResult(
            status=SubmissionStatus.ACKNOWLEDGED,
            external_order_id=str(permanent_order_id),
        )

    def cancel(self, order: Order) -> CancelResult:
        """Issue one cancel request for a correlated provider order."""

        if not isinstance(order, Order):
            raise IBKRExecutionAdapterError(
                "order must be a canonical Order."
            )
        self._operations.require_write_allowed(operation="cancel")
        self._admission.require(operation="cancel")

        reservation = self._session.correlations.find_by_order_id(order.id)
        if reservation is None:
            return CancelResult(
                status=CancelStatus.UNCERTAIN,
                reason=(
                    "IBKR cancellation has no reserved session route; "
                    "reconciliation is required."
                ),
            )

        client = self._client()
        trade = _find_trade(
            client.trades(),
            client_id=reservation.client_id,
            session_order_id=reservation.session_order_id,
        )
        if trade is None:
            return CancelResult(
                status=CancelStatus.UNCERTAIN,
                reason=(
                    "IBKR synchronized Trade is unavailable for cancellation; "
                    "reconciliation is required."
                ),
            )

        normalized = _normalize_trade(
            trade,
            expected_client_id=reservation.client_id,
            expected_session_order_id=reservation.session_order_id,
            expected_order_reference=reservation.order_reference,
            expected_account_id=self._connection.profile.expected_account_id,
        )
        if normalized is None:
            return CancelResult(
                status=CancelStatus.UNCERTAIN,
                reason=(
                    "IBKR synchronized Trade identity cannot be qualified for "
                    "cancellation."
                ),
            )
        provider_order, provider_status = normalized

        self._last_attempt = IBKREconomicWriteAttempt(
            operation="cancel",
            reservation=reservation,
            provider_call_attempted=True,
            provider_returned=False,
            permanent_order_id=_permanent_order_id(provider_order.permId),
            provider_status=provider_status.status,
        )
        try:
            response = client.cancelOrder(provider_order)
        except Exception:
            return CancelResult(
                status=CancelStatus.UNCERTAIN,
                reason=(
                    "IBKR cancelOrder was attempted once and its economic outcome "
                    "is unknown; reconcile before any further cancel action."
                ),
            )

        if response is None:
            return CancelResult(
                status=CancelStatus.UNCERTAIN,
                reason=(
                    "IBKR cancelOrder returned no correlated Trade; "
                    "reconciliation is required."
                ),
            )

        self._last_attempt = IBKREconomicWriteAttempt(
            operation="cancel",
            reservation=reservation,
            provider_call_attempted=True,
            provider_returned=True,
            permanent_order_id=_permanent_order_id(provider_order.permId),
            provider_status=provider_status.status,
        )
        return CancelResult(status=CancelStatus.ACKNOWLEDGED)

    def query_order(self, order: Order) -> ExecutionReport | None:
        """Query synchronized provider state without fabricating fill facts."""

        if not isinstance(order, Order):
            raise IBKRExecutionAdapterError(
                "order must be a canonical Order."
            )
        reservation = self._session.correlations.find_by_order_id(order.id)
        if reservation is None:
            return None

        client = self._client()
        trade = _find_trade(
            client.trades(),
            client_id=reservation.client_id,
            session_order_id=reservation.session_order_id,
        )
        if trade is None:
            return None

        correlated = self._session.callbacks.correlate_order_status(
            trade,
            observed_at=self._clock.now(),
        )
        if correlated is None:
            return None
        return map_ibkr_order_status_report(
            correlated.observation,
            context=correlated.reservation.context,
            registry=self._session.identities,
        )

    def _client(self) -> _IBKRCommandClient:
        provider_client = self._connection.read_client()
        required = ("placeOrder", "cancelOrder", "trades")
        if any(not hasattr(provider_client, name) for name in required):
            raise ProviderProtocolError(
                "IBKR PAPER client lacks the qualified economic-write surface.",
                provider=IBKR_PROVIDER_KEY,
                operation="execution",
            )
        return cast(_IBKRCommandClient, provider_client)


def build_ibkr_execution_adapter(
    *,
    connection: IBKRPaperConnectionRuntime,
    session: IBKROrderSessionRuntime,
    instruments: IBKRExecutionInstrumentResolver,
    admission: IBKREconomicWriteAdmission,
    operations: IBKROperationalGuard,
    clock: ClockPort,
    market_rules: IBKRMarketRuleResolver | None = None,
    sdk_factory: IBKRSDKPlacementFactory | None = None,
) -> IBKRExecutionAdapter:
    """Compose LOT-06.5 over a started PAPER session and LOT-06.4 routing."""

    return IBKRExecutionAdapter(
        connection=connection,
        session=session,
        instruments=instruments,
        admission=admission,
        operations=operations,
        clock=clock,
        market_rules=market_rules,
        sdk_factory=sdk_factory,
    )


def _find_trade(
    trades: list[object],
    *,
    client_id: IBKRClientId,
    session_order_id: IBKRSessionOrderId,
) -> object | None:
    matches: list[object] = []
    for trade in trades:
        if not hasattr(trade, "order"):
            continue
        candidate = cast(_ProviderTradeLike, trade)
        order = candidate.order
        if not hasattr(order, "clientId") or not hasattr(order, "orderId"):
            continue
        provider_order = cast(_ProviderOrderLike, order)
        if (
            provider_order.clientId == client_id.value
            and provider_order.orderId == session_order_id.value
        ):
            matches.append(trade)

    if len(matches) > 1:
        raise ProviderProtocolError(
            "IBKR synchronized trades contain duplicate routing identities.",
            provider=IBKR_PROVIDER_KEY,
            operation="execution",
        )
    return matches[0] if matches else None


def _normalize_trade(
    trade: object,
    *,
    expected_client_id: IBKRClientId,
    expected_session_order_id: IBKRSessionOrderId,
    expected_order_reference: IBKROrderReference,
    expected_account_id: str,
) -> tuple[_ProviderOrderLike, _ProviderOrderStatusLike] | None:
    if not hasattr(trade, "order") or not hasattr(trade, "orderStatus"):
        return None
    candidate = cast(_ProviderTradeLike, trade)
    order = candidate.order
    status = candidate.orderStatus
    order_fields = ("orderId", "clientId", "permId", "orderRef", "account")
    status_fields = ("orderId", "status", "permId", "clientId")
    if any(not hasattr(order, name) for name in order_fields):
        return None
    if any(not hasattr(status, name) for name in status_fields):
        return None

    provider_order = cast(_ProviderOrderLike, order)
    provider_status = cast(_ProviderOrderStatusLike, status)
    if (
        type(provider_order.orderId) is not int
        or type(provider_order.clientId) is not int
        or type(provider_order.permId) is not int
        or not isinstance(provider_order.orderRef, str)
        or not isinstance(provider_order.account, str)
        or type(provider_status.orderId) is not int
        or type(provider_status.clientId) is not int
        or type(provider_status.permId) is not int
        or not isinstance(provider_status.status, str)
    ):
        return None
    if provider_order.permId < 0 or provider_status.permId < 0:
        return None
    if provider_order.clientId != expected_client_id.value:
        return None
    if provider_status.clientId != expected_client_id.value:
        return None
    if provider_order.orderId != expected_session_order_id.value:
        return None
    if provider_status.orderId != expected_session_order_id.value:
        return None
    if provider_order.orderRef != expected_order_reference.value:
        return None
    if provider_order.account != expected_account_id:
        return None
    if (
        provider_order.permId > 0
        and provider_status.permId > 0
        and provider_order.permId != provider_status.permId
    ):
        return None
    return provider_order, provider_status


def _permanent_order_id(value: object) -> IBKRPermanentOrderId | None:
    if type(value) is not int or value <= 0:
        return None
    return IBKRPermanentOrderId(value)
