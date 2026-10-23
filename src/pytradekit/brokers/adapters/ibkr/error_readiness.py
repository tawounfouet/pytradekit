"""IBKR SDK-free error classification and runtime readiness policy."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from pytradekit.brokers import (
    ProviderAuthorizationError,
    ProviderError,
    ProviderProtocolError,
    ProviderRateLimitError,
    ProviderRejectedOperationError,
    ProviderStateReconciliationRequired,
    ProviderUnavailableError,
    ProviderUncertainOutcomeError,
)
from pytradekit.shared import require_utc_datetime

from .discovery import IBKR_PROVIDER_KEY, IBKRReadinessFact


class IBKRErrorMappingError(ValueError):
    """Raised when an IBKR error or readiness observation is invalid."""


class IBKRErrorCategory(StrEnum):
    """Provider-local classes for TWS API messages and errors."""

    INFORMATION = "INFORMATION"
    CONNECTIVITY = "CONNECTIVITY"
    PACING = "PACING"
    REQUEST_REJECTED = "REQUEST_REJECTED"
    ORDER_REJECTED = "ORDER_REJECTED"
    ORDER_STATE = "ORDER_STATE"
    AUTHORIZATION = "AUTHORIZATION"
    PROTOCOL = "PROTOCOL"
    UNKNOWN = "UNKNOWN"


class IBKRErrorDisposition(StrEnum):
    """How PyTradeKit must react to one provider message class."""

    IGNORE = "IGNORE"
    DEGRADE = "DEGRADE"
    RECONNECT = "RECONNECT"
    RECONCILE = "RECONCILE"
    RATE_LIMIT = "RATE_LIMIT"
    REJECT_OPERATION = "REJECT_OPERATION"
    ORDER_CALLBACK = "ORDER_CALLBACK"
    FAIL_CLOSED = "FAIL_CLOSED"


class IBKRConnectivityState(StrEnum):
    """Connection state implied by a provider system message."""

    CONNECTED = "CONNECTED"
    LOST = "LOST"
    RESTORED_DATA_LOST = "RESTORED_DATA_LOST"
    RESTORED_DATA_MAINTAINED = "RESTORED_DATA_MAINTAINED"
    PORT_RESET = "PORT_RESET"
    DEGRADED = "DEGRADED"
    MARKET_DATA_DEGRADED = "MARKET_DATA_DEGRADED"


@dataclass(frozen=True, slots=True)
class IBKRErrorRule:
    """Frozen handling rule for one documented IBKR code."""

    category: IBKRErrorCategory
    disposition: IBKRErrorDisposition
    safe_message: str
    affects_order_writes: bool = False
    affects_market_data: bool = False
    market_data_resubscription_required: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.category, IBKRErrorCategory):
            raise IBKRErrorMappingError("category must be an IBKRErrorCategory.")
        if not isinstance(self.disposition, IBKRErrorDisposition):
            raise IBKRErrorMappingError(
                "disposition must be an IBKRErrorDisposition."
            )
        if not isinstance(self.safe_message, str) or not self.safe_message.strip():
            raise IBKRErrorMappingError("safe_message must be non-empty.")


@dataclass(frozen=True, slots=True)
class IBKRErrorObservation:
    """SDK-free observation derived from the TWS API error callback."""

    request_id: int
    code: int
    message: str
    observed_at: datetime
    advanced_order_reject_json: str | None = None

    def __post_init__(self) -> None:
        if type(self.request_id) is not int:
            raise IBKRErrorMappingError("request_id must be an int.")
        if type(self.code) is not int or self.code <= 0:
            raise IBKRErrorMappingError("code must be a positive int.")
        object.__setattr__(
            self,
            "message",
            _required_text(self.message, field_name="message"),
        )
        object.__setattr__(
            self,
            "observed_at",
            require_utc_datetime(
                self.observed_at,
                field_name="IBKR error observed_at",
            ),
        )
        if self.advanced_order_reject_json is not None:
            object.__setattr__(
                self,
                "advanced_order_reject_json",
                _required_text(
                    self.advanced_order_reject_json,
                    field_name="advanced_order_reject_json",
                ),
            )


@dataclass(frozen=True, slots=True)
class IBKRReadinessObservation:
    """Explicit facts required before IBKR reads or economic writes are admitted."""

    socket_connected: bool
    protocol_negotiated: bool
    next_valid_id_received: bool
    account_verified: bool
    paper_endpoint_verified: bool
    reconciliation_complete: bool
    account_ready: bool
    api_read_only: bool
    market_data_resubscribed: bool = True
    last_connectivity_code: int | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "socket_connected",
            "protocol_negotiated",
            "next_valid_id_received",
            "account_verified",
            "paper_endpoint_verified",
            "reconciliation_complete",
            "account_ready",
            "api_read_only",
            "market_data_resubscribed",
        ):
            if type(getattr(self, field_name)) is not bool:
                raise IBKRErrorMappingError(f"{field_name} must be a bool.")
        if self.last_connectivity_code is not None and (
            type(self.last_connectivity_code) is not int
            or self.last_connectivity_code <= 0
        ):
            raise IBKRErrorMappingError(
                "last_connectivity_code must be a positive int or None."
            )


@dataclass(frozen=True, slots=True)
class IBKRReadinessDecision:
    """Derived admission decision for the frozen IBKR PAPER runtime."""

    ready_for_reads: bool
    ready_for_economic_writes: bool
    ready_for_market_data: bool
    reconciliation_required: bool
    market_data_resubscription_required: bool
    missing_facts: tuple[IBKRReadinessFact, ...]
    blocking_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        for field_name in (
            "ready_for_reads",
            "ready_for_economic_writes",
            "ready_for_market_data",
            "reconciliation_required",
            "market_data_resubscription_required",
        ):
            if type(getattr(self, field_name)) is not bool:
                raise IBKRErrorMappingError(f"{field_name} must be a bool.")
        if any(not reason.strip() for reason in self.blocking_reasons):
            raise IBKRErrorMappingError("blocking_reasons must not contain blanks.")


IBKR_ERROR_RULES: Final[Mapping[int, IBKRErrorRule]] = MappingProxyType(
    {
        100: IBKRErrorRule(
            IBKRErrorCategory.PACING,
            IBKRErrorDisposition.RATE_LIMIT,
            "IBKR message rate limit exceeded.",
            affects_order_writes=True,
            affects_market_data=True,
        ),
        200: IBKRErrorRule(
            IBKRErrorCategory.REQUEST_REJECTED,
            IBKRErrorDisposition.REJECT_OPERATION,
            "IBKR rejected the requested contract or request.",
        ),
        201: IBKRErrorRule(
            IBKRErrorCategory.ORDER_REJECTED,
            IBKRErrorDisposition.ORDER_CALLBACK,
            "IBKR rejected the order.",
            affects_order_writes=True,
        ),
        202: IBKRErrorRule(
            IBKRErrorCategory.ORDER_STATE,
            IBKRErrorDisposition.ORDER_CALLBACK,
            "IBKR confirmed order cancellation.",
            affects_order_writes=True,
        ),
        203: IBKRErrorRule(
            IBKRErrorCategory.AUTHORIZATION,
            IBKRErrorDisposition.REJECT_OPERATION,
            "IBKR account is not authorized to trade the requested security.",
            affects_order_writes=True,
        ),
        326: IBKRErrorRule(
            IBKRErrorCategory.CONNECTIVITY,
            IBKRErrorDisposition.FAIL_CLOSED,
            "IBKR API client id is already in use.",
            affects_order_writes=True,
        ),
        502: IBKRErrorRule(
            IBKRErrorCategory.CONNECTIVITY,
            IBKRErrorDisposition.RECONNECT,
            "PyTradeKit could not connect to TWS or IB Gateway.",
            affects_order_writes=True,
        ),
        503: IBKRErrorRule(
            IBKRErrorCategory.PROTOCOL,
            IBKRErrorDisposition.FAIL_CLOSED,
            "TWS or IB Gateway is incompatible with the requested API operation.",
            affects_order_writes=True,
        ),
        504: IBKRErrorRule(
            IBKRErrorCategory.CONNECTIVITY,
            IBKRErrorDisposition.RECONNECT,
            "IBKR API request attempted without an active socket connection.",
            affects_order_writes=True,
        ),
        507: IBKRErrorRule(
            IBKRErrorCategory.CONNECTIVITY,
            IBKRErrorDisposition.RECONNECT,
            "IBKR socket connection is no longer valid.",
            affects_order_writes=True,
        ),
        1100: IBKRErrorRule(
            IBKRErrorCategory.CONNECTIVITY,
            IBKRErrorDisposition.RECONCILE,
            "Connectivity between TWS or IB Gateway and IBKR was lost.",
            affects_order_writes=True,
            affects_market_data=True,
        ),
        1101: IBKRErrorRule(
            IBKRErrorCategory.CONNECTIVITY,
            IBKRErrorDisposition.RECONCILE,
            "IBKR connectivity was restored with provider data subscriptions lost.",
            affects_order_writes=True,
            affects_market_data=True,
            market_data_resubscription_required=True,
        ),
        1102: IBKRErrorRule(
            IBKRErrorCategory.CONNECTIVITY,
            IBKRErrorDisposition.RECONCILE,
            "IBKR connectivity was restored with provider data maintained.",
            affects_order_writes=True,
        ),
        1300: IBKRErrorRule(
            IBKRErrorCategory.CONNECTIVITY,
            IBKRErrorDisposition.RECONNECT,
            "TWS or IB Gateway reset the API socket port and dropped the connection.",
            affects_order_writes=True,
            affects_market_data=True,
        ),
        2103: IBKRErrorRule(
            IBKRErrorCategory.CONNECTIVITY,
            IBKRErrorDisposition.DEGRADE,
            "IBKR market data farm is disconnected.",
            affects_market_data=True,
        ),
        2104: IBKRErrorRule(
            IBKRErrorCategory.INFORMATION,
            IBKRErrorDisposition.IGNORE,
            "IBKR market data farm connection is healthy.",
        ),
        2105: IBKRErrorRule(
            IBKRErrorCategory.INFORMATION,
            IBKRErrorDisposition.IGNORE,
            "IBKR historical data farm is disconnected.",
        ),
        2106: IBKRErrorRule(
            IBKRErrorCategory.INFORMATION,
            IBKRErrorDisposition.IGNORE,
            "IBKR historical data farm connection is healthy.",
        ),
        2107: IBKRErrorRule(
            IBKRErrorCategory.INFORMATION,
            IBKRErrorDisposition.IGNORE,
            "IBKR historical data farm is inactive until needed.",
        ),
        2108: IBKRErrorRule(
            IBKRErrorCategory.INFORMATION,
            IBKRErrorDisposition.IGNORE,
            "IBKR market data farm is inactive until needed.",
        ),
        2110: IBKRErrorRule(
            IBKRErrorCategory.CONNECTIVITY,
            IBKRErrorDisposition.RECONCILE,
            "Connectivity between TWS or IB Gateway and IBKR is broken.",
            affects_order_writes=True,
            affects_market_data=True,
        ),
        2158: IBKRErrorRule(
            IBKRErrorCategory.INFORMATION,
            IBKRErrorDisposition.IGNORE,
            "IBKR security definition farm connection is healthy.",
        ),
    }
)


_CONNECTIVITY_STATES: Final[Mapping[int, IBKRConnectivityState]] = MappingProxyType(
    {
        1100: IBKRConnectivityState.LOST,
        1101: IBKRConnectivityState.RESTORED_DATA_LOST,
        1102: IBKRConnectivityState.RESTORED_DATA_MAINTAINED,
        1300: IBKRConnectivityState.PORT_RESET,
        2103: IBKRConnectivityState.MARKET_DATA_DEGRADED,
        2104: IBKRConnectivityState.CONNECTED,
        2110: IBKRConnectivityState.DEGRADED,
    }
)


def ibkr_error_rule(code: int) -> IBKRErrorRule:
    """Return the frozen rule for a documented code or a conservative fallback."""

    if type(code) is not int or code <= 0:
        raise IBKRErrorMappingError("code must be a positive int.")
    rule = IBKR_ERROR_RULES.get(code)
    if rule is not None:
        return rule
    return IBKRErrorRule(
        category=IBKRErrorCategory.UNKNOWN,
        disposition=IBKRErrorDisposition.FAIL_CLOSED,
        safe_message=f"Unclassified IBKR provider code {code}.",
    )


def ibkr_connectivity_state(code: int | None) -> IBKRConnectivityState | None:
    """Return the connection state implied by a provider code."""

    if code is None:
        return None
    if type(code) is not int or code <= 0:
        raise IBKRErrorMappingError("code must be a positive int or None.")
    return _CONNECTIVITY_STATES.get(code)


def map_ibkr_provider_error(
    observation: IBKRErrorObservation,
    *,
    operation: str,
    economic_write_in_flight: bool = False,
) -> ProviderError | None:
    """Map one provider message without inventing retry safety."""

    if not isinstance(observation, IBKRErrorObservation):
        raise IBKRErrorMappingError(
            "observation must be an IBKRErrorObservation."
        )
    normalized_operation = _required_text(operation, field_name="operation")
    if type(economic_write_in_flight) is not bool:
        raise IBKRErrorMappingError(
            "economic_write_in_flight must be a bool."
        )

    rule = ibkr_error_rule(observation.code)
    provider_code = str(observation.code)

    if rule.disposition in {
        IBKRErrorDisposition.IGNORE,
        IBKRErrorDisposition.ORDER_CALLBACK,
    }:
        return None

    if economic_write_in_flight and (
        rule.affects_order_writes
        or rule.category is IBKRErrorCategory.UNKNOWN
    ):
        return ProviderUncertainOutcomeError(
            "IBKR economic write outcome is uncertain and requires reconciliation.",
            provider=IBKR_PROVIDER_KEY,
            operation=normalized_operation,
            provider_code=provider_code,
        )

    if rule.disposition is IBKRErrorDisposition.RATE_LIMIT:
        return ProviderRateLimitError(
            rule.safe_message,
            provider=IBKR_PROVIDER_KEY,
            operation=normalized_operation,
            provider_code=provider_code,
        )

    if rule.category is IBKRErrorCategory.AUTHORIZATION:
        return ProviderAuthorizationError(
            rule.safe_message,
            provider=IBKR_PROVIDER_KEY,
            operation=normalized_operation,
            provider_code=provider_code,
        )

    if rule.disposition is IBKRErrorDisposition.REJECT_OPERATION:
        return ProviderRejectedOperationError(
            rule.safe_message,
            provider=IBKR_PROVIDER_KEY,
            operation=normalized_operation,
            provider_code=provider_code,
        )

    if rule.disposition is IBKRErrorDisposition.RECONCILE:
        return ProviderStateReconciliationRequired(
            rule.safe_message,
            provider=IBKR_PROVIDER_KEY,
            operation=normalized_operation,
            provider_code=provider_code,
        )

    if rule.disposition in {
        IBKRErrorDisposition.DEGRADE,
        IBKRErrorDisposition.RECONNECT,
    }:
        return ProviderUnavailableError(
            rule.safe_message,
            provider=IBKR_PROVIDER_KEY,
            operation=normalized_operation,
            provider_code=provider_code,
        )

    if observation.code == 326:
        return ProviderUnavailableError(
            rule.safe_message,
            provider=IBKR_PROVIDER_KEY,
            operation=normalized_operation,
            provider_code=provider_code,
        )

    return ProviderProtocolError(
        rule.safe_message,
        provider=IBKR_PROVIDER_KEY,
        operation=normalized_operation,
        provider_code=provider_code,
    )


def evaluate_ibkr_readiness(
    observation: IBKRReadinessObservation,
) -> IBKRReadinessDecision:
    """Evaluate read, market-data, and economic-write admission separately."""

    if not isinstance(observation, IBKRReadinessObservation):
        raise IBKRErrorMappingError(
            "observation must be an IBKRReadinessObservation."
        )

    facts = {
        IBKRReadinessFact.SOCKET_CONNECTED: observation.socket_connected,
        IBKRReadinessFact.PROTOCOL_NEGOTIATED: observation.protocol_negotiated,
        IBKRReadinessFact.NEXT_VALID_ID_RECEIVED: (
            observation.next_valid_id_received
        ),
        IBKRReadinessFact.ACCOUNT_VERIFIED: observation.account_verified,
        IBKRReadinessFact.PAPER_ENDPOINT_VERIFIED: (
            observation.paper_endpoint_verified
        ),
        IBKRReadinessFact.RECONCILIATION_COMPLETE: (
            observation.reconciliation_complete
        ),
    }
    missing_facts = tuple(
        fact for fact in IBKRReadinessFact if not facts[fact]
    )

    read_facts = (
        IBKRReadinessFact.SOCKET_CONNECTED,
        IBKRReadinessFact.PROTOCOL_NEGOTIATED,
        IBKRReadinessFact.ACCOUNT_VERIFIED,
        IBKRReadinessFact.PAPER_ENDPOINT_VERIFIED,
    )
    write_facts = (
        *read_facts,
        IBKRReadinessFact.NEXT_VALID_ID_RECEIVED,
        IBKRReadinessFact.RECONCILIATION_COMPLETE,
    )
    reads_ready = all(facts[fact] for fact in read_facts) and observation.account_ready
    writes_ready = all(facts[fact] for fact in write_facts) and observation.account_ready

    connectivity = ibkr_connectivity_state(observation.last_connectivity_code)
    hard_disconnect = connectivity in {
        IBKRConnectivityState.LOST,
        IBKRConnectivityState.PORT_RESET,
        IBKRConnectivityState.DEGRADED,
    }
    if hard_disconnect:
        reads_ready = False
        writes_ready = False

    reconciliation_required = not observation.reconciliation_complete
    if connectivity in {
        IBKRConnectivityState.LOST,
        IBKRConnectivityState.PORT_RESET,
        IBKRConnectivityState.DEGRADED,
    }:
        reconciliation_required = True

    market_data_resubscription_required = (
        connectivity is IBKRConnectivityState.RESTORED_DATA_LOST
        and not observation.market_data_resubscribed
    )
    market_data_ready = (
        reads_ready
        and connectivity
        not in {
            IBKRConnectivityState.LOST,
            IBKRConnectivityState.PORT_RESET,
            IBKRConnectivityState.DEGRADED,
            IBKRConnectivityState.MARKET_DATA_DEGRADED,
        }
        and not market_data_resubscription_required
    )

    if observation.api_read_only:
        writes_ready = False
    if reconciliation_required:
        writes_ready = False

    reasons: list[str] = []
    if missing_facts:
        reasons.append(
            "missing readiness facts: "
            + ", ".join(fact.value for fact in missing_facts)
        )
    if not observation.account_ready:
        reasons.append("AccountReady is false")
    if observation.api_read_only:
        reasons.append("IBKR API read-only mode blocks order submission")
    if hard_disconnect:
        reasons.append("IBKR connectivity is not healthy")
    if reconciliation_required:
        reasons.append("reconciliation is required before economic writes")
    if market_data_resubscription_required:
        reasons.append("market data subscriptions must be restored")

    return IBKRReadinessDecision(
        ready_for_reads=reads_ready,
        ready_for_economic_writes=writes_ready,
        ready_for_market_data=market_data_ready,
        reconciliation_required=reconciliation_required,
        market_data_resubscription_required=market_data_resubscription_required,
        missing_facts=missing_facts,
        blocking_reasons=tuple(reasons),
    )


def assert_ibkr_ready_for_economic_write(
    observation: IBKRReadinessObservation,
    *,
    operation: str = "economic_write",
) -> None:
    """Fail closed unless all economic-write readiness facts are proven."""

    decision = evaluate_ibkr_readiness(observation)
    if decision.ready_for_economic_writes:
        return

    normalized_operation = _required_text(operation, field_name="operation")
    if decision.reconciliation_required:
        raise ProviderStateReconciliationRequired(
            "IBKR reconciliation must complete before economic writes are admitted.",
            provider=IBKR_PROVIDER_KEY,
            operation=normalized_operation,
        )
    raise ProviderUnavailableError(
        "IBKR runtime is not ready for economic writes.",
        provider=IBKR_PROVIDER_KEY,
        operation=normalized_operation,
    )


def _required_text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise IBKRErrorMappingError(f"{field_name} must be a string.")
    normalized = value.strip()
    if not normalized:
        raise IBKRErrorMappingError(f"{field_name} must be non-empty.")
    return normalized
