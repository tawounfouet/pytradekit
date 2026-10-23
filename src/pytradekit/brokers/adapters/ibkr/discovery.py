"""IBKR discovery facts and contract freeze for PyTradeKit 0.8 LOT-04."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from pytradekit.brokers.compliance import BrokerCapability
from pytradekit.orders.domain import OrderType, TimeInForce
from pytradekit.reference.domain import AssetClass
from pytradekit.runtime import RuntimeEnvironment

IBKR_PROVIDER_KEY: Final = "ibkr"
IBKR_DISCOVERY_VERSION: Final = "1.0-rc1"
IBKR_TWS_API_TARGET: Final = "10.49"
IBKR_RUNTIME_TRANSPORT: Final = "TWS API socket"
IBKR_RUNTIME_GATEWAY: Final = "IB Gateway"
IBKR_OFFICIAL_SDK_LICENSE: Final = "GNU General Public License (GPL)"


class IBKRDiscoveryError(ValueError):
    """Raised when a frozen IBKR discovery invariant is violated."""


class IBKRClientSurface(StrEnum):
    """Supported TWS API host applications for the first IBKR vertical slice."""

    TWS = "TWS"
    IB_GATEWAY = "IB_GATEWAY"


class IBKRContractOutcome(StrEnum):
    """Outcome of one canonical contract compatibility decision."""

    UNCHANGED = "UNCHANGED"
    UNCHANGED_WITH_MAPPING = "UNCHANGED_WITH_MAPPING"
    ADAPTER_LOCAL = "ADAPTER_LOCAL"
    IMPLEMENTATION_CHANGE = "IMPLEMENTATION_CHANGE"
    PAPER_PROBE_REQUIRED = "PAPER_PROBE_REQUIRED"
    DEFERRED = "DEFERRED"


class IBKROrderIdentityRole(StrEnum):
    """Frozen semantic roles for IBKR order and execution identifiers."""

    CLIENT_REFERENCE = "orderRef"
    SESSION_ORDER_ID = "orderId"
    PERMANENT_ORDER_ID = "permId"
    EXECUTION_ID = "execId"
    CONTRACT_ID = "conId"
    CONNECTION_CLIENT_ID = "clientId"


class IBKRReadinessFact(StrEnum):
    """Provider observations required before the adapter is considered ready."""

    SOCKET_CONNECTED = "SOCKET_CONNECTED"
    PROTOCOL_NEGOTIATED = "PROTOCOL_NEGOTIATED"
    NEXT_VALID_ID_RECEIVED = "NEXT_VALID_ID_RECEIVED"
    ACCOUNT_VERIFIED = "ACCOUNT_VERIFIED"
    PAPER_ENDPOINT_VERIFIED = "PAPER_ENDPOINT_VERIFIED"
    RECONCILIATION_COMPLETE = "RECONCILIATION_COMPLETE"


IBKR_PAPER_PORTS = MappingProxyType(
    {
        IBKRClientSurface.TWS: 7497,
        IBKRClientSurface.IB_GATEWAY: 4002,
    }
)

IBKR_LIVE_PORTS = MappingProxyType(
    {
        IBKRClientSurface.TWS: 7496,
        IBKRClientSurface.IB_GATEWAY: 4001,
    }
)

IBKR_TARGET_CAPABILITIES: tuple[BrokerCapability, ...] = (
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
    BrokerCapability.LATEST_QUOTE,
)

IBKR_DEFERRED_CAPABILITIES: tuple[BrokerCapability, ...] = (
    BrokerCapability.REPLACE_ORDER,
)


@dataclass(frozen=True, slots=True)
class IBKRContractDecision:
    """One explicit LOT-04 decision about compatibility with the canonical contract."""

    subject: str
    outcome: IBKRContractOutcome
    decision: str
    rationale: str

    def __post_init__(self) -> None:
        for field_name in ("subject", "decision", "rationale"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise IBKRDiscoveryError(f"{field_name} must be non-empty.")
            object.__setattr__(self, field_name, value.strip())
        if not isinstance(self.outcome, IBKRContractOutcome):
            raise IBKRDiscoveryError("outcome must be an IBKRContractOutcome.")

    def to_dict(self) -> dict[str, str]:
        """Return deterministic JSON-safe decision content."""

        return {
            "subject": self.subject,
            "outcome": self.outcome.value,
            "decision": self.decision,
            "rationale": self.rationale,
        }


@dataclass(frozen=True, slots=True)
class IBKRContractFreeze:
    """Frozen 0.8.0a4 implementation envelope for the first IBKR adapter."""

    version: str
    provider: str
    environment: RuntimeEnvironment
    runtime_surface: IBKRClientSurface
    runtime_transport: str
    asset_classes: frozenset[AssetClass]
    order_types: frozenset[OrderType]
    time_in_force: frozenset[TimeInForce]
    target_capabilities: tuple[BrokerCapability, ...]
    deferred_capabilities: tuple[BrokerCapability, ...]
    readiness_facts: tuple[IBKRReadinessFact, ...]
    client_reference_field: str
    session_order_id_field: str
    external_order_id_field: str
    external_fill_id_field: str
    external_instrument_id_field: str
    reconnect_resubmit_setting: str
    decisions: tuple[IBKRContractDecision, ...]
    unresolved_paper_questions: tuple[str, ...]
    non_goals: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.version != IBKR_DISCOVERY_VERSION:
            raise IBKRDiscoveryError("IBKR discovery version does not match the freeze.")
        if self.provider != IBKR_PROVIDER_KEY:
            raise IBKRDiscoveryError("IBKR contract freeze provider must be ibkr.")
        if self.environment is not RuntimeEnvironment.PAPER:
            raise IBKRDiscoveryError("IBKR contract freeze is PAPER only.")
        if self.runtime_surface is not IBKRClientSurface.IB_GATEWAY:
            raise IBKRDiscoveryError("The first IBKR runtime is frozen to IB Gateway.")
        if not self.asset_classes or not self.order_types or not self.time_in_force:
            raise IBKRDiscoveryError("Frozen IBKR trading scope must not be empty.")
        if not self.target_capabilities:
            raise IBKRDiscoveryError("IBKR target_capabilities must not be empty.")

        overlap = set(self.target_capabilities) & set(self.deferred_capabilities)
        if overlap:
            raise IBKRDiscoveryError("Target and deferred capabilities must not overlap.")

        for field_name in (
            "runtime_transport",
            "client_reference_field",
            "session_order_id_field",
            "external_order_id_field",
            "external_fill_id_field",
            "external_instrument_id_field",
            "reconnect_resubmit_setting",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise IBKRDiscoveryError(f"{field_name} must be non-empty.")

        for field_name in ("unresolved_paper_questions", "non_goals"):
            values = getattr(self, field_name)
            if any(not value.strip() for value in values):
                raise IBKRDiscoveryError(f"{field_name} values must not be empty.")

    @property
    def paper_port(self) -> int:
        """Return the only default port accepted for the frozen runtime surface."""

        return IBKR_PAPER_PORTS[self.runtime_surface]

    @property
    def broker_neutral_core_change_required(self) -> bool:
        """Return whether LOT-04 found an IBKR-specific canonical core change."""

        return any(
            decision.outcome is IBKRContractOutcome.IMPLEMENTATION_CHANGE
            and decision.subject.startswith("core:")
            for decision in self.decisions
        )

    def to_dict(self) -> dict[str, object]:
        """Return deterministic JSON-safe freeze content."""

        return {
            "version": self.version,
            "provider": self.provider,
            "environment": self.environment.value,
            "runtime_surface": self.runtime_surface.value,
            "runtime_transport": self.runtime_transport,
            "paper_port": self.paper_port,
            "asset_classes": sorted(item.value for item in self.asset_classes),
            "order_types": sorted(item.value for item in self.order_types),
            "time_in_force": sorted(item.value for item in self.time_in_force),
            "target_capabilities": [item.value for item in self.target_capabilities],
            "deferred_capabilities": [item.value for item in self.deferred_capabilities],
            "readiness_facts": [item.value for item in self.readiness_facts],
            "identity_roles": {
                "client_reference": self.client_reference_field,
                "session_order_id": self.session_order_id_field,
                "external_order_id": self.external_order_id_field,
                "external_fill_id": self.external_fill_id_field,
                "external_instrument_id": self.external_instrument_id_field,
            },
            "reconnect_resubmit_setting": self.reconnect_resubmit_setting,
            "decisions": [item.to_dict() for item in self.decisions],
            "unresolved_paper_questions": list(self.unresolved_paper_questions),
            "non_goals": list(self.non_goals),
            "broker_neutral_core_change_required": (
                self.broker_neutral_core_change_required
            ),
        }


def validate_ibkr_paper_port(
    *,
    surface: IBKRClientSurface,
    port: int,
) -> int:
    """Reject LIVE or unexpected socket ports for the frozen PAPER runtime."""

    if not isinstance(surface, IBKRClientSurface):
        raise IBKRDiscoveryError("surface must be an IBKRClientSurface.")
    if type(port) is not int or port <= 0:
        raise IBKRDiscoveryError("IBKR socket port must be a positive integer.")

    live_port = IBKR_LIVE_PORTS[surface]
    if port == live_port:
        raise IBKRDiscoveryError(
            f"IBKR LIVE port {port} is forbidden by the PAPER contract freeze."
        )

    expected = IBKR_PAPER_PORTS[surface]
    if port != expected:
        raise IBKRDiscoveryError(
            f"IBKR PAPER {surface.value} port must be {expected}, got {port}."
        )
    return port


def build_ibkr_contract_freeze() -> IBKRContractFreeze:
    """Build the authoritative LOT-04 IBKR discovery and contract freeze."""

    return IBKRContractFreeze(
        version=IBKR_DISCOVERY_VERSION,
        provider=IBKR_PROVIDER_KEY,
        environment=RuntimeEnvironment.PAPER,
        runtime_surface=IBKRClientSurface.IB_GATEWAY,
        runtime_transport=IBKR_RUNTIME_TRANSPORT,
        asset_classes=frozenset({AssetClass.EQUITY}),
        order_types=frozenset({OrderType.MARKET, OrderType.LIMIT}),
        time_in_force=frozenset({TimeInForce.DAY}),
        target_capabilities=IBKR_TARGET_CAPABILITIES,
        deferred_capabilities=IBKR_DEFERRED_CAPABILITIES,
        readiness_facts=(
            IBKRReadinessFact.SOCKET_CONNECTED,
            IBKRReadinessFact.PROTOCOL_NEGOTIATED,
            IBKRReadinessFact.NEXT_VALID_ID_RECEIVED,
            IBKRReadinessFact.ACCOUNT_VERIFIED,
            IBKRReadinessFact.PAPER_ENDPOINT_VERIFIED,
            IBKRReadinessFact.RECONCILIATION_COMPLETE,
        ),
        client_reference_field=IBKROrderIdentityRole.CLIENT_REFERENCE.value,
        session_order_id_field=IBKROrderIdentityRole.SESSION_ORDER_ID.value,
        external_order_id_field=IBKROrderIdentityRole.PERMANENT_ORDER_ID.value,
        external_fill_id_field=IBKROrderIdentityRole.EXECUTION_ID.value,
        external_instrument_id_field=IBKROrderIdentityRole.CONTRACT_ID.value,
        reconnect_resubmit_setting="maintainAndResubmitOrdersOnReconnect=false",
        decisions=_contract_decisions(),
        unresolved_paper_questions=(
            "Verify orderRef persistence and uniqueness behavior for the target PAPER account.",
            "Observe exact callback ordering for MARKET, LIMIT, CANCEL and partial fills.",
            "Verify when non-zero permId first becomes available after placeOrder.",
            "Verify execution replay behavior and correction semantics for execId.",
            "Observe account cash tags required for the canonical Balance snapshot.",
            "Verify IEX-like latest quote expectations against available IBKR entitlements.",
            "Measure current pacing behavior for the qualified account and gateway version.",
        ),
        non_goals=(
            "LIVE trading.",
            "Web API implementation.",
            "Official ibapi dependency distribution before license review.",
            "Financial Advisor and multi-account allocation.",
            "Options, futures, FX, CFDs and crypto.",
            "GTC, bracket, conditional, algorithmic or complex orders.",
            "Order replacement certification.",
            "Automatic adoption of manual TWS orders.",
        ),
    )


def _contract_decisions() -> tuple[IBKRContractDecision, ...]:
    return (
        IBKRContractDecision(
            subject="core:ExecutionPort",
            outcome=IBKRContractOutcome.UNCHANGED,
            decision="Use the existing ExecutionPort for submit, cancel and query behavior.",
            rationale="IBKR transport details remain inside the adapter.",
        ),
        IBKRContractDecision(
            subject="core:BrokerSnapshotPort",
            outcome=IBKRContractOutcome.UNCHANGED,
            decision="Use the existing BrokerSnapshotPort for reconciliation snapshots.",
            rationale="Orders, fills, positions and balances already have canonical forms.",
        ),
        IBKRContractDecision(
            subject="core:ProviderOrderIdentity",
            outcome=IBKRContractOutcome.UNCHANGED_WITH_MAPPING,
            decision="Map client_reference to orderRef and external_order_id to permId.",
            rationale=(
                "orderId is session and client scoped, while permId is the stable host order "
                "identifier. orderId remains adapter-local routing state."
            ),
        ),
        IBKRContractDecision(
            subject="core:ProviderFillIdentity",
            outcome=IBKRContractOutcome.UNCHANGED_WITH_MAPPING,
            decision="Map external_fill_id to execId.",
            rationale="IBKR assigns a distinct execId to each partial execution.",
        ),
        IBKRContractDecision(
            subject="core:ProviderInstrumentIdentity",
            outcome=IBKRContractOutcome.UNCHANGED_WITH_MAPPING,
            decision="Map external_id to conId and retain symbol only as descriptive metadata.",
            rationale="IBKR recommends conId plus exchange as the stable contract definition.",
        ),
        IBKRContractDecision(
            subject="adapter:orderId",
            outcome=IBKRContractOutcome.ADAPTER_LOCAL,
            decision="Keep nextValidId allocation and orderId lifecycle inside the IBKR adapter.",
            rationale="orderId is provider sequencing state, not a canonical order identity.",
        ),
        IBKRContractDecision(
            subject="adapter:submission_ack",
            outcome=IBKRContractOutcome.PAPER_PROBE_REQUIRED,
            decision=(
                "Return ACKNOWLEDGED only after a non-zero permId is observed; otherwise "
                "return an uncertain outcome and reconcile."
            ),
            rationale=(
                "The canonical accepted order requires a stable external_order_id, while "
                "placeOrder itself is not an economic acknowledgement."
            ),
        ),
        IBKRContractDecision(
            subject="adapter:order_status",
            outcome=IBKRContractOutcome.ADAPTER_LOCAL,
            decision=(
                "Map PendingSubmit, PreSubmitted, Submitted, PendingCancel, Cancelled, "
                "ApiCancelled and Filled inside the ACL. Treat Inactive as reason-dependent."
            ),
            rationale="Provider status strings must not leak into the canonical OMS.",
        ),
        IBKRContractDecision(
            subject="adapter:reconnect",
            outcome=IBKRContractOutcome.ADAPTER_LOCAL,
            decision=(
                "Disable implicit reconnect resubmission and require reconciliation before "
                "new economic writes are admitted."
            ),
            rationale="Blind replay after a transport loss can duplicate economic effects.",
        ),
        IBKRContractDecision(
            subject="adapter:pacing",
            outcome=IBKRContractOutcome.ADAPTER_LOCAL,
            decision="Keep request pacing and error-code interpretation provider-specific.",
            rationale="IBKR pacing limits depend on provider settings and market data lines.",
        ),
        IBKRContractDecision(
            subject="runtime:profile",
            outcome=IBKRContractOutcome.IMPLEMENTATION_CHANGE,
            decision=(
                "Add an IBKR-specific PAPER runtime profile in the adapter composition "
                "instead of extending the Alpaca-only RuntimeProfile with IBKR branches."
            ),
            rationale="The existing RuntimeProfile is intentionally frozen to Alpaca 0.5.",
        ),
        IBKRContractDecision(
            subject="dependency:official_ibapi",
            outcome=IBKRContractOutcome.DEFERRED,
            decision="Do not bundle official TWS API 10.49+ before license review.",
            rationale="IBKR documents TWS API 10.49+ as GPL while PyTradeKit is Apache-2.0.",
        ),
        IBKRContractDecision(
            subject="dependency:ib_async",
            outcome=IBKRContractOutcome.PAPER_PROBE_REQUIRED,
            decision="Keep ib_async as a candidate transport implementation, not a contract.",
            rationale="It is community maintained and must pass protocol and PAPER qualification.",
        ),
    )
