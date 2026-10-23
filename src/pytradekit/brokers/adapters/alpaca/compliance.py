"""Alpaca capability mapping and compliance certification for PyTradeKit 0.8."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType

from alpaca.trading.enums import OrderStatus as AlpacaOrderStatus
from alpaca.trading.enums import TradeEvent as AlpacaTradeEvent

from pytradekit.brokers import ProviderAccountIdentity
from pytradekit.brokers.compliance import (
    BROKER_ADAPTER_CONTRACT_V1_CANDIDATE,
    PROVIDER_CAPABILITY_MANIFEST_VERSION,
    BrokerCapability,
    CapabilityConstraint,
    CapabilitySupport,
    CertificationLevel,
    ComplianceBlockedError,
    ComplianceCriticality,
    ComplianceEvidenceType,
    ComplianceHarness,
    ComplianceObservation,
    ComplianceReportGenerator,
    ComplianceRequirement,
    ComplianceRun,
    ComplianceScenario,
    ComplianceStatus,
    EvidenceSanitizer,
    ProviderCapabilityManifest,
    ProviderFixture,
)
from pytradekit.execution import ExecutionStatus
from pytradekit.orders.domain import OrderType, TimeInForce
from pytradekit.orders.ports import ExecutionPort
from pytradekit.reconciliation.ports import BrokerSnapshotPort
from pytradekit.reference import AssetClass
from pytradekit.runtime import RuntimeEnvironment

from .compliance_evidence import AlpacaPaperEvidenceBundle
from .contract import (
    ALPACA_PROVIDER_KEY,
    ALPACA_SDK_VERSION_TARGET,
    order_status_rule,
    supports_order_contract,
    trade_event_rule,
    validate_client_order_reference,
)
from .execution import AlpacaExecutionAdapter
from .snapshots import AlpacaMarketDataSnapshots
from .startup import AlpacaPaperRuntimeSystem

ALPACA_COMPLIANCE_ADAPTER_VERSION = "0.5.0-frozen"

ALPACA_DECLARED_CAPABILITIES: tuple[BrokerCapability, ...] = (
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

ALPACA_REAL_PAPER_C3_CAPABILITIES: frozenset[BrokerCapability] = frozenset(
    capability
    for capability in ALPACA_DECLARED_CAPABILITIES
    if capability is not BrokerCapability.PARTIAL_FILL
)

ALPACA_EXPECTED_CERTIFICATION_LEVELS: Mapping[
    BrokerCapability,
    CertificationLevel,
] = MappingProxyType(
    {
        capability: (
            CertificationLevel.C3_PAPER_QUALIFIED
            if capability in ALPACA_REAL_PAPER_C3_CAPABILITIES
            else CertificationLevel.C2_INTEGRATION_QUALIFIED
        )
        for capability in ALPACA_DECLARED_CAPABILITIES
    }
)


@dataclass(slots=True)
class AlpacaRetainedEvidenceFixture:
    """Evidence replay fixture used to qualify the frozen Alpaca PAPER adapter."""

    manifest: ProviderCapabilityManifest
    cleanup_calls: int = 0

    def provider_manifest(self) -> ProviderCapabilityManifest:
        return self.manifest

    def build_runtime(self) -> object:
        raise ComplianceBlockedError(
            "Retained evidence replay does not materialize a provider runtime."
        )

    def build_execution_adapter(self) -> ExecutionPort:
        raise ComplianceBlockedError(
            "Retained evidence replay does not materialize an execution adapter."
        )

    def build_snapshot_adapter(self) -> BrokerSnapshotPort:
        raise ComplianceBlockedError(
            "Retained evidence replay does not materialize a snapshot adapter."
        )

    def paper_account_fixture(self) -> ProviderAccountIdentity:
        raise ComplianceBlockedError(
            "Retained evidence stores only masked PAPER account identity."
        )

    def cleanup(self) -> None:
        self.cleanup_calls += 1


@dataclass(frozen=True, slots=True)
class _CapturedAtClock:
    captured_at: datetime

    def now(self) -> datetime:
        return self.captured_at


class AlpacaComplianceScenarioExecutor:
    """Execute Alpaca compliance scenarios from retained and deterministic evidence."""

    def __init__(self, evidence: AlpacaPaperEvidenceBundle) -> None:
        self._evidence = evidence

    def __call__(
        self,
        fixture: ProviderFixture,
        scenario: ComplianceScenario,
    ) -> ComplianceObservation:
        manifest = fixture.provider_manifest()
        if manifest.provider != ALPACA_PROVIDER_KEY:
            return ComplianceObservation(
                status=ComplianceStatus.FAIL,
                evidence_type=ComplianceEvidenceType.DIAGNOSTIC,
                payload={"observed_provider": manifest.provider},
                reason="Alpaca compliance executor received a non-Alpaca fixture.",
            )

        evidence_type = scenario.required_evidence[0]
        if evidence_type is ComplianceEvidenceType.INTEGRATION:
            return self._integration_observation(manifest, scenario)
        if evidence_type is ComplianceEvidenceType.PAPER:
            return self._paper_observation(scenario)

        return ComplianceObservation(
            status=ComplianceStatus.FAIL,
            evidence_type=ComplianceEvidenceType.DIAGNOSTIC,
            payload={"required_evidence": evidence_type.value},
            reason="Alpaca LOT-03 supports only INTEGRATION and PAPER qualification.",
        )

    def _integration_observation(
        self,
        manifest: ProviderCapabilityManifest,
        scenario: ComplianceScenario,
    ) -> ComplianceObservation:
        supported, detail = _deterministic_capability_check(
            manifest,
            scenario.capability,
        )
        passed = self._evidence.deterministic_qualified and supported

        payload = self._evidence.common_evidence_payload()
        payload["qualification_class"] = "deterministic"
        payload["capability"] = scenario.capability.value
        payload["ci_quality_gate"] = self._evidence.gates.get("ci_quality_gate")
        payload["deterministic_check"] = detail

        return ComplianceObservation(
            status=ComplianceStatus.PASS if passed else ComplianceStatus.FAIL,
            evidence_type=(
                ComplianceEvidenceType.INTEGRATION
                if passed
                else ComplianceEvidenceType.DIAGNOSTIC
            ),
            payload=payload,
            reason=None if passed else "Deterministic Alpaca capability evidence failed.",
        )

    def _paper_observation(
        self,
        scenario: ComplianceScenario,
    ) -> ComplianceObservation:
        passed = self._evidence.paper_proof_passes(scenario.capability)
        payload = self._evidence.common_evidence_payload()
        payload["qualification_class"] = "real-paper"
        payload["capability"] = scenario.capability.value

        try:
            payload["proof"] = dict(self._evidence.proof_for(scenario.capability))
        except ValueError:
            payload["proof"] = {}

        return ComplianceObservation(
            status=ComplianceStatus.PASS if passed else ComplianceStatus.FAIL,
            evidence_type=(
                ComplianceEvidenceType.PAPER
                if passed
                else ComplianceEvidenceType.DIAGNOSTIC
            ),
            payload=payload,
            reason=None if passed else "Retained real Alpaca PAPER evidence is insufficient.",
        )


def build_alpaca_capability_manifest() -> ProviderCapabilityManifest:
    """Map the frozen Alpaca PAPER runtime into the 0.8 capability manifest."""

    paper_equity = CapabilityConstraint(
        asset_classes=frozenset({AssetClass.EQUITY}),
        environments=frozenset({RuntimeEnvironment.PAPER}),
        account_modes=frozenset({"paper"}),
        notes=("US equities only.",),
    )
    market = CapabilityConstraint(
        asset_classes=paper_equity.asset_classes,
        order_types=frozenset({OrderType.MARKET}),
        time_in_force=frozenset({TimeInForce.DAY}),
        environments=paper_equity.environments,
        account_modes=paper_equity.account_modes,
        notes=paper_equity.notes,
    )
    limit_order = CapabilityConstraint(
        asset_classes=paper_equity.asset_classes,
        order_types=frozenset({OrderType.LIMIT}),
        time_in_force=frozenset({TimeInForce.DAY}),
        environments=paper_equity.environments,
        account_modes=paper_equity.account_modes,
        notes=paper_equity.notes,
    )
    cancel = CapabilityConstraint(
        asset_classes=paper_equity.asset_classes,
        order_types=frozenset({OrderType.MARKET, OrderType.LIMIT}),
        time_in_force=frozenset({TimeInForce.DAY}),
        environments=paper_equity.environments,
        account_modes=paper_equity.account_modes,
        notes=("Cancel request acknowledgement is not terminal cancellation.",),
    )
    latest_quote = CapabilityConstraint(
        asset_classes=paper_equity.asset_classes,
        environments=paper_equity.environments,
        account_modes=paper_equity.account_modes,
        required_settings=("market_data_feed=iex",),
        notes=("IEX latest quote only.",),
    )

    support_constraints: Mapping[BrokerCapability, CapabilityConstraint] = {
        BrokerCapability.MARKET_ORDER: market,
        BrokerCapability.LIMIT_ORDER: limit_order,
        BrokerCapability.CANCEL_ORDER: cancel,
        BrokerCapability.LATEST_QUOTE: latest_quote,
    }

    return ProviderCapabilityManifest(
        provider=ALPACA_PROVIDER_KEY,
        environment=RuntimeEnvironment.PAPER,
        adapter_version=ALPACA_COMPLIANCE_ADAPTER_VERSION,
        account_mode="paper",
        asset_classes=frozenset({AssetClass.EQUITY}),
        supported_order_types=frozenset({OrderType.MARKET, OrderType.LIMIT}),
        supported_time_in_force=frozenset({TimeInForce.DAY}),
        capabilities=tuple(
            CapabilitySupport(
                capability=capability,
                constraints=support_constraints.get(capability, paper_equity),
            )
            for capability in ALPACA_DECLARED_CAPABILITIES
        ),
        stream_model="private-trade-updates",
        session_model="rest-plus-websocket",
        sdk_name="alpaca-py",
        sdk_version=ALPACA_SDK_VERSION_TARGET,
        known_limitations=(
            "PAPER only.",
            "US equities only.",
            "MARKET and LIMIT submission with DAY time in force.",
            "REPLACE_ORDER is unsupported.",
            "LATEST_QUOTE is limited to the IEX feed.",
            (
                "PARTIAL_FILL is retained at C2 because the real 2026-10-22 "
                "PAPER proof did not trigger a partial fill."
            ),
            "LIVE qualification is unavailable.",
        ),
    )


def build_alpaca_compliance_requirements() -> tuple[ComplianceRequirement, ...]:
    """Build capability-specific deterministic and real PAPER requirements."""

    requirements: list[ComplianceRequirement] = []
    for capability in ALPACA_DECLARED_CAPABILITIES:
        requirements.append(
            ComplianceRequirement(
                requirement_id=f"ALPACA-{capability.value}-C2",
                capability=capability,
                level=CertificationLevel.C2_INTEGRATION_QUALIFIED,
                description=(
                    f"Alpaca {capability.value} passes retained deterministic "
                    "integration qualification."
                ),
                criticality=_criticality(capability),
                applicable=True,
                evidence_type=ComplianceEvidenceType.INTEGRATION,
            )
        )
        if capability in ALPACA_REAL_PAPER_C3_CAPABILITIES:
            requirements.append(
                ComplianceRequirement(
                    requirement_id=f"ALPACA-{capability.value}-C3",
                    capability=capability,
                    level=CertificationLevel.C3_PAPER_QUALIFIED,
                    description=(
                        f"Alpaca {capability.value} is backed by retained real PAPER evidence."
                    ),
                    criticality=_criticality(capability),
                    applicable=True,
                    evidence_type=ComplianceEvidenceType.PAPER,
                )
            )
    return tuple(requirements)


def build_alpaca_compliance_scenarios() -> tuple[ComplianceScenario, ...]:
    """Build the executable Alpaca qualification scenarios."""

    scenarios: list[ComplianceScenario] = []
    for capability in ALPACA_DECLARED_CAPABILITIES:
        scenarios.append(
            ComplianceScenario(
                scenario_id=f"ALPACA-{capability.value}-C2",
                capability=capability,
                preconditions=(
                    "frozen Alpaca adapter available",
                    "retained deterministic CI gate available",
                ),
                action=f"validate deterministic semantics for {capability.value}",
                expected_result="provider behavior remains compatible with canonical semantics",
                failure_semantics="deterministic mismatch prevents C2 and all higher levels",
                cleanup="no provider mutation in deterministic evidence replay",
                required_evidence=(ComplianceEvidenceType.INTEGRATION,),
                requirement_ids=(f"ALPACA-{capability.value}-C2",),
            )
        )
        if capability in ALPACA_REAL_PAPER_C3_CAPABILITIES:
            scenarios.append(
                ComplianceScenario(
                    scenario_id=f"ALPACA-{capability.value}-C3",
                    capability=capability,
                    preconditions=(
                        "retained sanitized real Alpaca PAPER evidence available",
                        "source release gate passed",
                    ),
                    action=f"validate retained PAPER proof for {capability.value}",
                    expected_result=(
                        "real provider behavior satisfies canonical capability semantics"
                    ),
                    failure_semantics="missing or contradictory provider proof prevents C3",
                    cleanup="source PAPER qualification restored its controlled baseline",
                    required_evidence=(ComplianceEvidenceType.PAPER,),
                    requirement_ids=(f"ALPACA-{capability.value}-C3",),
                )
            )
    return tuple(scenarios)


def build_alpaca_certification_run(
    evidence: AlpacaPaperEvidenceBundle,
) -> ComplianceRun:
    """Replay retained Alpaca evidence through the common 0.8 compliance harness."""

    manifest = build_alpaca_capability_manifest()
    fixture = AlpacaRetainedEvidenceFixture(manifest)
    requirements = build_alpaca_compliance_requirements()
    scenarios = build_alpaca_compliance_scenarios()
    executor = AlpacaComplianceScenarioExecutor(evidence)
    executors = {scenario.scenario_id: executor for scenario in scenarios}

    harness = ComplianceHarness(
        contract=BROKER_ADAPTER_CONTRACT_V1_CANDIDATE,
        requirements=requirements,
        scenarios=scenarios,
        executors=executors,
        sanitizer=EvidenceSanitizer(),
        report_generator=ComplianceReportGenerator(),
        clock=_CapturedAtClock(evidence.captured_at),
    )
    workflow_run_id = evidence.provenance.workflow_run_id
    run_suffix = (
        str(workflow_run_id)
        if workflow_run_id is not None
        else evidence.provenance.artifact_json_sha256[:12]
    )
    run = harness.run(
        fixture,
        run_id=f"alpaca-paper-{run_suffix}",
        commit_sha=evidence.provenance.qualified_commit,
        manifest_version=PROVIDER_CAPABILITY_MANIFEST_VERSION,
    )
    validate_alpaca_certification_run(run)
    return run


def validate_alpaca_certification_run(run: ComplianceRun) -> None:
    """Fail closed when the Alpaca certification matrix differs from LOT-03 target."""

    observed = {
        item.capability: item.certification_level
        for item in run.report.capability_results
    }
    if observed != dict(ALPACA_EXPECTED_CERTIFICATION_LEVELS):
        expected_text = ", ".join(
            f"{capability.value}={level.code}"
            for capability, level in ALPACA_EXPECTED_CERTIFICATION_LEVELS.items()
        )
        observed_text = ", ".join(
            f"{capability.value}={level.code}"
            for capability, level in sorted(
                observed.items(),
                key=lambda item: item[0].value,
            )
        )
        raise ValueError(
            "Alpaca certification matrix does not match LOT-03 target. "
            f"Expected [{expected_text}], observed [{observed_text}]."
        )
    if not run.report.complete:
        raise ValueError("Alpaca LOT-03 report contains failed or blocked scenarios.")


def _criticality(capability: BrokerCapability) -> ComplianceCriticality:
    if capability in {
        BrokerCapability.MARKET_ORDER,
        BrokerCapability.LIMIT_ORDER,
        BrokerCapability.CANCEL_ORDER,
        BrokerCapability.PARTIAL_FILL,
        BrokerCapability.CLIENT_ORDER_REFERENCE,
        BrokerCapability.EXECUTION_FACTS,
        BrokerCapability.RECONNECT_RECOVERY,
    }:
        return ComplianceCriticality.CRITICAL
    if capability in {
        BrokerCapability.ACCOUNT_QUERY,
        BrokerCapability.ORDER_QUERY,
        BrokerCapability.POSITION_QUERY,
        BrokerCapability.BALANCE_QUERY,
    }:
        return ComplianceCriticality.HIGH
    return ComplianceCriticality.MEDIUM


def _deterministic_capability_check(
    manifest: ProviderCapabilityManifest,
    capability: BrokerCapability,
) -> tuple[bool, dict[str, object]]:
    declared = manifest.supports(capability)
    detail: dict[str, object] = {
        "declared": declared,
        "provider": manifest.provider,
        "adapter_version": manifest.adapter_version,
    }
    if not declared:
        return False, detail

    if capability is BrokerCapability.ACCOUNT_QUERY:
        passed = callable(getattr(AlpacaMarketDataSnapshots, "get_account_snapshot", None))
    elif capability is BrokerCapability.ORDER_QUERY:
        passed = callable(getattr(AlpacaExecutionAdapter, "query_order", None))
    elif capability is BrokerCapability.MARKET_ORDER:
        passed = supports_order_contract(
            order_type=OrderType.MARKET,
            time_in_force=TimeInForce.DAY,
        )
    elif capability is BrokerCapability.LIMIT_ORDER:
        passed = supports_order_contract(
            order_type=OrderType.LIMIT,
            time_in_force=TimeInForce.DAY,
        )
    elif capability is BrokerCapability.CANCEL_ORDER:
        passed = callable(getattr(AlpacaExecutionAdapter, "cancel", None))
    elif capability is BrokerCapability.PARTIAL_FILL:
        order_rule = order_status_rule(AlpacaOrderStatus.PARTIALLY_FILLED)
        event_rule = trade_event_rule(AlpacaTradeEvent.PARTIAL_FILL)
        passed = (
            order_rule.canonical_status is ExecutionStatus.PARTIALLY_FILLED
            and event_rule.canonical_status is ExecutionStatus.PARTIALLY_FILLED
        )
        detail["order_status_mapping"] = (
            None if order_rule.canonical_status is None else order_rule.canonical_status.value
        )
        detail["trade_event_mapping"] = (
            None if event_rule.canonical_status is None else event_rule.canonical_status.value
        )
    elif capability is BrokerCapability.POSITION_QUERY:
        passed = callable(
            getattr(AlpacaMarketDataSnapshots, "get_position_snapshots", None)
        )
    elif capability is BrokerCapability.BALANCE_QUERY:
        passed = callable(getattr(AlpacaMarketDataSnapshots, "get_account_snapshot", None))
    elif capability is BrokerCapability.CLIENT_ORDER_REFERENCE:
        sample = "PTK-COMPLIANCE"
        passed = (
            validate_client_order_reference(sample) == sample
            and callable(getattr(AlpacaExecutionAdapter, "query_order", None))
        )
    elif capability is BrokerCapability.EXECUTION_FACTS:
        fill_rule = trade_event_rule(AlpacaTradeEvent.FILL)
        passed = fill_rule.canonical_status is ExecutionStatus.FILLED
        detail["fill_event_mapping"] = (
            None if fill_rule.canonical_status is None else fill_rule.canonical_status.value
        )
    elif capability is BrokerCapability.RECONNECT_RECOVERY:
        passed = (
            callable(getattr(AlpacaPaperRuntimeSystem, "start", None))
            and callable(getattr(AlpacaPaperRuntimeSystem, "stop", None))
        )
    elif capability is BrokerCapability.LATEST_QUOTE:
        passed = callable(getattr(AlpacaMarketDataSnapshots, "get_latest_quote", None))
    else:
        passed = False

    detail["passed"] = passed
    return passed, detail
