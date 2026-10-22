"""Provider capability manifest for broker compliance."""

from __future__ import annotations

from dataclasses import dataclass

from pytradekit.orders.domain import OrderType, TimeInForce
from pytradekit.reference.domain import AssetClass
from pytradekit.runtime.configuration import RuntimeEnvironment

from .capability import BrokerCapability, CapabilitySupport


def _required_text(value: str, *, field_name: str) -> str:
    normalized = value.strip() if isinstance(value, str) else ""
    if not normalized:
        raise ValueError(f"{field_name} must be a non-empty string.")
    return normalized


@dataclass(frozen=True, slots=True)
class ProviderCapabilityManifest:
    """Immutable declaration of what one provider adapter claims to support."""

    provider: str
    environment: RuntimeEnvironment
    adapter_version: str
    account_mode: str
    asset_classes: frozenset[AssetClass]
    supported_order_types: frozenset[OrderType]
    supported_time_in_force: frozenset[TimeInForce]
    capabilities: tuple[CapabilitySupport, ...]
    stream_model: str
    session_model: str
    sdk_name: str | None = None
    sdk_version: str | None = None
    known_limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        provider = _required_text(self.provider, field_name="provider").lower()
        adapter_version = _required_text(
            self.adapter_version,
            field_name="adapter_version",
        )
        account_mode = _required_text(self.account_mode, field_name="account_mode")
        stream_model = _required_text(self.stream_model, field_name="stream_model")
        session_model = _required_text(self.session_model, field_name="session_model")

        if not isinstance(self.environment, RuntimeEnvironment):
            raise ValueError("environment must be a RuntimeEnvironment.")
        if not self.asset_classes:
            raise ValueError("asset_classes must not be empty.")
        if not self.capabilities:
            raise ValueError("capabilities must not be empty.")

        if (self.sdk_name is None) != (self.sdk_version is None):
            raise ValueError("sdk_name and sdk_version must be declared together.")
        if self.sdk_name is not None:
            _required_text(self.sdk_name, field_name="sdk_name")
        if self.sdk_version is not None:
            _required_text(self.sdk_version, field_name="sdk_version")

        if any(not value.strip() for value in self.known_limitations):
            raise ValueError("known_limitations values must not be empty.")

        seen: set[BrokerCapability] = set()
        for support in self.capabilities:
            if not isinstance(support, CapabilitySupport):
                raise ValueError("capabilities must contain CapabilitySupport values.")
            if support.capability in seen:
                raise ValueError(
                    f"Duplicate capability declaration: {support.capability.value}."
                )
            seen.add(support.capability)
            self._validate_constraints(support)

        for capability, order_type in (
            (BrokerCapability.MARKET_ORDER, OrderType.MARKET),
            (BrokerCapability.LIMIT_ORDER, OrderType.LIMIT),
        ):
            if capability in seen and order_type not in self.supported_order_types:
                raise ValueError(
                    f"{capability.value} requires {order_type.value} in supported_order_types."
                )

        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "adapter_version", adapter_version)
        object.__setattr__(self, "account_mode", account_mode)
        object.__setattr__(self, "stream_model", stream_model)
        object.__setattr__(self, "session_model", session_model)

    def _validate_constraints(self, support: CapabilitySupport) -> None:
        constraints = support.constraints
        if (
            constraints.asset_classes
            and not constraints.asset_classes.issubset(self.asset_classes)
        ):
            raise ValueError(
                f"{support.capability.value} asset constraints exceed the provider envelope."
            )
        if (
            constraints.order_types
            and not constraints.order_types.issubset(self.supported_order_types)
        ):
            raise ValueError(
                f"{support.capability.value} order constraints exceed the provider envelope."
            )
        if (
            constraints.time_in_force
            and not constraints.time_in_force.issubset(self.supported_time_in_force)
        ):
            raise ValueError(
                f"{support.capability.value} TIF constraints exceed the provider envelope."
            )
        if constraints.environments and self.environment not in constraints.environments:
            raise ValueError(
                f"{support.capability.value} does not apply to this provider environment."
            )
        if constraints.account_modes and self.account_mode not in constraints.account_modes:
            raise ValueError(
                f"{support.capability.value} does not apply to this provider account mode."
            )

    @property
    def capability_set(self) -> frozenset[BrokerCapability]:
        """Return all capabilities declared by this manifest."""

        return frozenset(support.capability for support in self.capabilities)

    def supports(self, capability: BrokerCapability) -> bool:
        """Return whether the adapter declares the requested capability."""

        return capability in self.capability_set

    def support_for(self, capability: BrokerCapability) -> CapabilitySupport | None:
        """Return the scoped declaration for one capability."""

        for support in self.capabilities:
            if support.capability is capability:
                return support
        return None

    @property
    def supports_cancel(self) -> bool:
        return self.supports(BrokerCapability.CANCEL_ORDER)

    @property
    def supports_replace(self) -> bool:
        return self.supports(BrokerCapability.REPLACE_ORDER)

    @property
    def supports_client_reference(self) -> bool:
        return self.supports(BrokerCapability.CLIENT_ORDER_REFERENCE)

    @property
    def supports_order_query(self) -> bool:
        return self.supports(BrokerCapability.ORDER_QUERY)

    @property
    def supports_execution_event_ids(self) -> bool:
        return self.supports(BrokerCapability.EXECUTION_FACTS)

    @property
    def supports_position_query(self) -> bool:
        return self.supports(BrokerCapability.POSITION_QUERY)

    @property
    def supports_balance_query(self) -> bool:
        return self.supports(BrokerCapability.BALANCE_QUERY)

    @property
    def supports_market_data(self) -> bool:
        return self.supports(BrokerCapability.LATEST_QUOTE)

    def to_dict(self) -> dict[str, object]:
        """Return a stable diagnostic representation without certification claims."""

        return {
            "provider": self.provider,
            "environment": self.environment.value,
            "adapter_version": self.adapter_version,
            "sdk": (
                None
                if self.sdk_name is None
                else {"name": self.sdk_name, "version": self.sdk_version}
            ),
            "account_mode": self.account_mode,
            "asset_classes": sorted(value.value for value in self.asset_classes),
            "supported_order_types": sorted(
                value.value for value in self.supported_order_types
            ),
            "supported_time_in_force": sorted(
                value.value for value in self.supported_time_in_force
            ),
            "capabilities": [
                {
                    "capability": support.capability.value,
                    "constraints": {
                        "asset_classes": sorted(
                            value.value for value in support.constraints.asset_classes
                        ),
                        "order_types": sorted(
                            value.value for value in support.constraints.order_types
                        ),
                        "time_in_force": sorted(
                            value.value for value in support.constraints.time_in_force
                        ),
                        "environments": sorted(
                            value.value for value in support.constraints.environments
                        ),
                        "account_modes": sorted(support.constraints.account_modes),
                        "required_settings": list(
                            support.constraints.required_settings
                        ),
                        "notes": list(support.constraints.notes),
                    },
                }
                for support in self.capabilities
            ],
            "stream_model": self.stream_model,
            "session_model": self.session_model,
            "known_limitations": list(self.known_limitations),
        }
