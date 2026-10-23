"""Broker capability taxonomy and capability-scoped constraints."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from pytradekit.orders.domain import OrderType, TimeInForce
from pytradekit.reference.domain import AssetClass
from pytradekit.runtime.configuration import RuntimeEnvironment


class BrokerCapability(StrEnum):
    """Canonical broker capabilities understood by the 0.8 contract candidate."""

    ACCOUNT_QUERY = "ACCOUNT_QUERY"
    ORDER_QUERY = "ORDER_QUERY"
    MARKET_ORDER = "MARKET_ORDER"
    LIMIT_ORDER = "LIMIT_ORDER"
    CANCEL_ORDER = "CANCEL_ORDER"
    PARTIAL_FILL = "PARTIAL_FILL"
    POSITION_QUERY = "POSITION_QUERY"
    BALANCE_QUERY = "BALANCE_QUERY"
    CLIENT_ORDER_REFERENCE = "CLIENT_ORDER_REFERENCE"
    EXECUTION_FACTS = "EXECUTION_FACTS"
    RECONNECT_RECOVERY = "RECONNECT_RECOVERY"
    LATEST_QUOTE = "LATEST_QUOTE"
    REPLACE_ORDER = "REPLACE_ORDER"


P0_BROKER_CAPABILITIES: frozenset[BrokerCapability] = frozenset(
    {
        BrokerCapability.ACCOUNT_QUERY,
        BrokerCapability.ORDER_QUERY,
        BrokerCapability.MARKET_ORDER,
        BrokerCapability.LIMIT_ORDER,
        BrokerCapability.CANCEL_ORDER,
        BrokerCapability.PARTIAL_FILL,
        BrokerCapability.POSITION_QUERY,
        BrokerCapability.BALANCE_QUERY,
        BrokerCapability.CLIENT_ORDER_REFERENCE,
        BrokerCapability.EXECUTION_FACTS,
        BrokerCapability.RECONNECT_RECOVERY,
    }
)

OPTIONAL_BROKER_CAPABILITIES: frozenset[BrokerCapability] = frozenset(
    {
        BrokerCapability.LATEST_QUOTE,
        BrokerCapability.REPLACE_ORDER,
    }
)

BROKER_CAPABILITY_CATALOG: frozenset[BrokerCapability] = (
    P0_BROKER_CAPABILITIES | OPTIONAL_BROKER_CAPABILITIES
)


@dataclass(frozen=True, slots=True)
class CapabilityConstraint:
    """Narrow applicability envelope for one declared broker capability."""

    asset_classes: frozenset[AssetClass] = field(default_factory=frozenset)
    order_types: frozenset[OrderType] = field(default_factory=frozenset)
    time_in_force: frozenset[TimeInForce] = field(default_factory=frozenset)
    environments: frozenset[RuntimeEnvironment] = field(default_factory=frozenset)
    account_modes: frozenset[str] = field(default_factory=frozenset)
    required_settings: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name, values in (
            ("account_modes", self.account_modes),
            ("required_settings", self.required_settings),
            ("notes", self.notes),
        ):
            if any(not value.strip() for value in values):
                raise ValueError(
                    f"CapabilityConstraint {field_name} values must not be empty."
                )


@dataclass(frozen=True, slots=True)
class CapabilitySupport:
    """A capability declaration and the exact constraints under which it applies."""

    capability: BrokerCapability
    constraints: CapabilityConstraint = field(default_factory=CapabilityConstraint)

    def __post_init__(self) -> None:
        if not isinstance(self.capability, BrokerCapability):
            raise ValueError("CapabilitySupport capability must be a BrokerCapability.")
