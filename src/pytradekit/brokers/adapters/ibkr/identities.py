"""IBKR provider primitives and identity model for the anti-corruption layer."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Self

from pytradekit.brokers import (
    ProviderFillIdentity,
    ProviderInstrumentIdentity,
    ProviderOrderIdentity,
)

from .discovery import IBKR_PROVIDER_KEY


class IBKRIdentityError(ValueError):
    """Raised when an IBKR provider identity violates the frozen contract."""


def _require_int(
    value: object,
    *,
    field_name: str,
    minimum: int,
) -> int:
    if type(value) is not int:
        raise IBKRIdentityError(f"{field_name} must be an integer.")
    if value < minimum:
        raise IBKRIdentityError(f"{field_name} must be >= {minimum}.")
    return value


def _require_text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise IBKRIdentityError(f"{field_name} must be a string.")
    normalized = value.strip()
    if not normalized:
        raise IBKRIdentityError(f"{field_name} must be non-empty.")
    return normalized


@dataclass(frozen=True, slots=True)
class IBKRClientId:
    """TWS API client identity used to distinguish concurrent API clients."""

    value: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "value",
            _require_int(self.value, field_name="IBKRClientId.value", minimum=0),
        )

    def __int__(self) -> int:
        return self.value

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class IBKRSessionOrderId:
    """Client/session scoped TWS API order identifier."""

    value: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "value",
            _require_int(self.value, field_name="IBKRSessionOrderId.value", minimum=0),
        )

    def __int__(self) -> int:
        return self.value

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class IBKRPermanentOrderId:
    """Stable non-zero IBKR host order identifier represented by permId."""

    value: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "value",
            _require_int(self.value, field_name="IBKRPermanentOrderId.value", minimum=1),
        )

    def __int__(self) -> int:
        return self.value

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class IBKROrderReference:
    """User-defined IBKR orderRef used for PyTradeKit correlation."""

    value: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "value",
            _require_text(self.value, field_name="IBKROrderReference.value"),
        )

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class IBKRExecutionId:
    """IBKR execId identifying one provider execution observation."""

    value: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "value",
            _require_text(self.value, field_name="IBKRExecutionId.value"),
        )

    @property
    def correction_family(self) -> str | None:
        """Return the prefix used by IBKR to relate execution corrections."""

        prefix, separator, _suffix = self.value.rpartition(".")
        return prefix if separator and prefix else None

    @property
    def correction_revision(self) -> str | None:
        """Return the provider revision suffix after the final period."""

        _prefix, separator, suffix = self.value.rpartition(".")
        return suffix if separator and suffix else None

    def can_be_correction_of(self, previous: Self) -> bool:
        """Return whether two execIds can represent revisions of one execution."""

        if not isinstance(previous, IBKRExecutionId) or previous == self:
            return False
        family = self.correction_family
        return family is not None and family == previous.correction_family

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class IBKRContractId:
    """Qualified IBKR contract identifier represented by conId."""

    value: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "value",
            _require_int(self.value, field_name="IBKRContractId.value", minimum=1),
        )

    def __int__(self) -> int:
        return self.value

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class IBKRConnectionIdentity:
    """Identity of one API client connection to TWS or IB Gateway."""

    client_id: IBKRClientId

    def __post_init__(self) -> None:
        if not isinstance(self.client_id, IBKRClientId):
            raise IBKRIdentityError(
                "IBKRConnectionIdentity.client_id must be an IBKRClientId."
            )


@dataclass(frozen=True, slots=True)
class IBKROrderIdentity:
    """IBKR order identity without collapsing session and durable identifiers."""

    client_id: IBKRClientId
    session_order_id: IBKRSessionOrderId
    client_reference: IBKROrderReference
    permanent_order_id: IBKRPermanentOrderId | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.client_id, IBKRClientId):
            raise IBKRIdentityError("IBKROrderIdentity.client_id must be an IBKRClientId.")
        if not isinstance(self.session_order_id, IBKRSessionOrderId):
            raise IBKRIdentityError(
                "IBKROrderIdentity.session_order_id must be an IBKRSessionOrderId."
            )
        if not isinstance(self.client_reference, IBKROrderReference):
            raise IBKRIdentityError(
                "IBKROrderIdentity.client_reference must be an IBKROrderReference."
            )
        if self.permanent_order_id is not None and not isinstance(
            self.permanent_order_id,
            IBKRPermanentOrderId,
        ):
            raise IBKRIdentityError(
                "IBKROrderIdentity.permanent_order_id must be an "
                "IBKRPermanentOrderId or None."
            )

    @property
    def routing_key(self) -> tuple[int, int]:
        """Return the provider-local routing key for the current API client."""

        return (self.client_id.value, self.session_order_id.value)

    @property
    def has_durable_identity(self) -> bool:
        """Return whether a non-zero permId has been observed."""

        return self.permanent_order_id is not None

    def bind_permanent_order_id(
        self,
        permanent_order_id: IBKRPermanentOrderId,
    ) -> Self:
        """Bind a stable permId once and reject conflicting reassignment."""

        if not isinstance(permanent_order_id, IBKRPermanentOrderId):
            raise IBKRIdentityError(
                "permanent_order_id must be an IBKRPermanentOrderId."
            )
        if self.permanent_order_id is not None:
            if self.permanent_order_id != permanent_order_id:
                raise IBKRIdentityError(
                    "IBKROrderIdentity permId cannot be rebound to another value."
                )
            return self
        return replace(self, permanent_order_id=permanent_order_id)

    def to_provider_identity(self) -> ProviderOrderIdentity:
        """Translate a fully identified IBKR order to the provider-neutral model."""

        if self.permanent_order_id is None:
            raise IBKRIdentityError(
                "A non-zero permId is required before ProviderOrderIdentity can be emitted."
            )
        return ProviderOrderIdentity(
            provider=IBKR_PROVIDER_KEY,
            client_reference=self.client_reference.value,
            external_order_id=str(self.permanent_order_id),
        )


@dataclass(frozen=True, slots=True)
class IBKRExecutionIdentity:
    """IBKR execution identity and optional linkage back to its originating order."""

    execution_id: IBKRExecutionId
    permanent_order_id: IBKRPermanentOrderId | None = None
    session_order_id: IBKRSessionOrderId | None = None
    client_id: IBKRClientId | None = None
    order_reference: IBKROrderReference | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.execution_id, IBKRExecutionId):
            raise IBKRIdentityError(
                "IBKRExecutionIdentity.execution_id must be an IBKRExecutionId."
            )
        optional_types = (
            ("permanent_order_id", self.permanent_order_id, IBKRPermanentOrderId),
            ("session_order_id", self.session_order_id, IBKRSessionOrderId),
            ("client_id", self.client_id, IBKRClientId),
            ("order_reference", self.order_reference, IBKROrderReference),
        )
        for field_name, value, expected_type in optional_types:
            if value is not None and not isinstance(value, expected_type):
                raise IBKRIdentityError(
                    f"IBKRExecutionIdentity.{field_name} has an invalid type."
                )

    def to_provider_identity(self) -> ProviderFillIdentity:
        """Translate the raw execId into the provider-neutral fill identity."""

        return ProviderFillIdentity(
            provider=IBKR_PROVIDER_KEY,
            external_fill_id=self.execution_id.value,
        )


@dataclass(frozen=True, slots=True)
class IBKRExecutionCorrection:
    """Explicit relationship between two provider execution observations."""

    previous: IBKRExecutionId
    corrected: IBKRExecutionId

    def __post_init__(self) -> None:
        if not isinstance(self.previous, IBKRExecutionId):
            raise IBKRIdentityError(
                "IBKRExecutionCorrection.previous must be an IBKRExecutionId."
            )
        if not isinstance(self.corrected, IBKRExecutionId):
            raise IBKRIdentityError(
                "IBKRExecutionCorrection.corrected must be an IBKRExecutionId."
            )
        if not self.corrected.can_be_correction_of(self.previous):
            raise IBKRIdentityError(
                "IBKR execution correction must keep the same execId family and "
                "change the final revision."
            )

    @property
    def family_id(self) -> str:
        """Return the common provider execution correction family."""

        family = self.corrected.correction_family
        if family is None:
            raise IBKRIdentityError("IBKR execution correction family is unavailable.")
        return family


@dataclass(frozen=True, slots=True)
class IBKRContractIdentity:
    """Qualified IBKR contract identity before canonical instrument mapping."""

    contract_id: IBKRContractId
    symbol: str

    def __post_init__(self) -> None:
        if not isinstance(self.contract_id, IBKRContractId):
            raise IBKRIdentityError(
                "IBKRContractIdentity.contract_id must be an IBKRContractId."
            )
        object.__setattr__(
            self,
            "symbol",
            _require_text(self.symbol, field_name="IBKRContractIdentity.symbol"),
        )

    def to_provider_identity(self) -> ProviderInstrumentIdentity:
        """Translate conId and symbol to the provider-neutral instrument identity."""

        return ProviderInstrumentIdentity(
            provider=IBKR_PROVIDER_KEY,
            external_id=str(self.contract_id),
            external_symbol=self.symbol,
        )
