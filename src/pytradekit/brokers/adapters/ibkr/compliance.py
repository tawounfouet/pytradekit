"""IBKR compliance certification from deterministic and retained PAPER evidence."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType

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

from .capability_manifest import IBKR_ACL_DECLARED_CAPABILITIES
from .compliance_evidence import IBKRPaperEvidenceBundle
from .discovery import IBKR_PROVIDER_KEY
from .execution import IBKRExecutionAdapter
from .execution_mapping import map_ibkr_execution_report
from .operations_runtime import IBKRReconnectRecoveryRuntime
from .order_callbacks import (
    IBKROrderStatus,
    ibkr_order_status_rule,
)
from .order_commands import map_ibkr_order_command
from .read_side import IBKRBrokerSnapshotPort
from .runtime import (
    IBKR_ASYNC_PACKAGE_NAME,
    IBKR_ASYNC_VERSION_TARGET,
)

IBKR_CERTIFICATION_ADAPTER_VERSION = "0.8.0b8-lot06.7"

IBKR_REAL_PAPER_C3_ELIGIBLE_CAPABILITIES: frozenset[
    BrokerCapability
] = frozenset(
    capability
    for capability in IBKR_ACL_DECLARED_CAPABILITIES
    if capability is not BrokerCapability.PARTIAL_FILL
)

IBKR_BASELINE_CERTIFICATION_LEVELS: Mapping[
    BrokerCapability,
    CertificationLevel,
] = MappingProxyType(
    {
        capability: CertificationLevel.C2_INTEGRATION_QUALIFIED
        for capability in IBKR_ACL_DECLARED_CAPABILITIES
    }
)


@dataclass(slots=True)
class IBKRRetainedEvidenceFixture:
    """Replay fixture for sanitized real IBKR PAPER evidence."""

    manifest: ProviderCapabilityManifest
    cleanup_calls: int = 0

    def provider_manifest(self) -> ProviderCapabilityManifest:
        return self.manifest

    def build_runtime(self) -> object:
        raise ComplianceBlockedError(
            "Retained evidence replay does not materialize an IBKR runtime."
        )

    def build_execution_adapter(self) -> ExecutionPort:
        raise ComplianceBlockedError(
            "Retained evidence replay does not materialize an execution adapter."
        )

    def build_snapshot_adapter(self) -> BrokerSnapshotPort:
        raise ComplianceBlockedError(
            "Retained evidence replay does not materialize a broker snapshot."
        )

    def paper_account_fixture(self) -> ProviderAccountIdentity:
        raise ComplianceBlockedError(
            "Retained evidence stores only masked IBKR PAPER account identity."
        )

    def cleanup(self) -> None:
        self.cleanup_calls += 1


@dataclass(frozen=True, slots=True)
class _CapturedAtClock:
    captured_at: datetime

    def now(self) -> datetime:
        return self.captured_at


class IBKRComplianceScenarioExecutor:
    """Execute IBKR compliance scenarios from retained evidence."""

    def __init__(self, evidence: IBKRPaperEvidenceBundle) -> None:
        self._evidence = evidence

    def __call__(
        self,
        fixture: ProviderFixture,
        scenario: ComplianceScenario,
    ) -> ComplianceObservation:
        manifest = fixture.provider_manifest()
        if manifest.provider != IBKR_PROVIDER_KEY:
            return ComplianceObservation(
                status=ComplianceStatus.FAIL,
                evidence_type=ComplianceEvidenceType.DIAGNOSTIC,
                payload={"observed_provider": manifest.provider},
                reason=(
                    "IBKR compliance executor received a non-IBKR fixture."
                ),
            )

        evidence_type = scenario.required_evidence[0]
        if evidence_type is ComplianceEvidenceType.INTEGRATION:
            return self._integration_observation(
                manifest,
                scenario,
            )
        if evidence_type is ComplianceEvidenceType.PAPER:
            return self._paper_observation(scenario)

        return ComplianceObservation(
            status=ComplianceStatus.FAIL,
            evidence_type=ComplianceEvidenceType.DIAGNOSTIC,
            payload={
                "required_evidence": evidence_type.value,
            },
            reason=(
                "IBKR LOT-06.7 supports only INTEGRATION and PAPER "
                "qualification."
            ),
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
        payload["deterministic_check"] = detail

        return ComplianceObservation(
            status=(
                ComplianceStatus.PASS
                if passed
                else ComplianceStatus.FAIL
            ),
            evidence_type=(
                ComplianceEvidenceType.INTEGRATION
                if passed
                else ComplianceEvidenceType.DIAGNOSTIC
            ),
            payload=payload,
            reason=(
                None
                if passed
                else "Deterministic IBKR capability evidence failed."
            ),
        )

    def _paper_observation(
        self,
        scenario: ComplianceScenario,
    ) -> ComplianceObservation:
        passed = self._evidence.paper_proof_passes(
            scenario.capability
        )
        payload = self._evidence.common_evidence_payload()
        payload["qualification_class"] = "real-paper"
        payload["capability"] = scenario.capability.value
        try:
            payload["proof"] = dict(
                self._evidence.proof_for(scenario.capability)
            )
        except ValueError:
            payload["proof"] = {}

        return ComplianceObservation(
            status=(
                ComplianceStatus.PASS
                if passed
                else ComplianceStatus.FAIL
            ),
            evidence_type=(
                ComplianceEvidenceType.PAPER
                if passed
                else ComplianceEvidenceType.DIAGNOSTIC
            ),
            payload=payload,
            reason=(
                None
                if passed
                else "Retained real IBKR PAPER evidence is insufficient."
            ),
        )


def build_ibkr_certification_manifest() -> ProviderCapabilityManifest:
    """Build the runtime-backed IBKR PAPER manifest for certification."""

    paper_equity = CapabilityConstraint(
        asset_classes=frozenset({AssetClass.EQUITY}),
        environments=frozenset({RuntimeEnvironment.PAPER}),
        account_modes=frozenset({"paper"}),
        required_settings=(
            "ib_gateway_port=4002",
            "paper_endpoint_verified=true",
        ),
        notes=("US equities only.",),
    )
    market = CapabilityConstraint(
        asset_classes=paper_equity.asset_classes,
        order_types=frozenset({OrderType.MARKET}),
        time_in_force=frozenset({TimeInForce.DAY}),
        environments=paper_equity.environments,
        account_modes=paper_equity.account_modes,
        required_settings=(
            "paper_endpoint_verified=true",
            "api_read_only=false",
            "economic_write_enabled=true",
        ),
        notes=("Regular-hours-only execution scope.",),
    )
    limit_order = CapabilityConstraint(
        asset_classes=paper_equity.asset_classes,
        order_types=frozenset({OrderType.LIMIT}),
        time_in_force=frozenset({TimeInForce.DAY}),
        environments=paper_equity.environments,
        account_modes=paper_equity.account_modes,
        required_settings=(
            "paper_endpoint_verified=true",
            "api_read_only=false",
            "economic_write_enabled=true",
        ),
        notes=(
            "Dynamic market-rule validation uses reqMarketRule.",
        ),
    )
    cancel = CapabilityConstraint(
        asset_classes=paper_equity.asset_classes,
        order_types=frozenset(
            {OrderType.MARKET, OrderType.LIMIT}
        ),
        time_in_force=frozenset({TimeInForce.DAY}),
        environments=paper_equity.environments,
        account_modes=paper_equity.account_modes,
        notes=(
            "Cancel acknowledgement is not terminal cancellation.",
        ),
    )
    reconnect = CapabilityConstraint(
        asset_classes=paper_equity.asset_classes,
        environments=paper_equity.environments,
        account_modes=paper_equity.account_modes,
        required_settings=(
            "maintainAndResubmitOrdersOnReconnect=false",
        ),
        notes=(
            "Reconnect never replays an economic write.",
            "Fresh reconciliation is required when prior evidence "
            "was invalidated.",
        ),
    )
    execution_facts = CapabilityConstraint(
        asset_classes=paper_equity.asset_classes,
        environments=paper_equity.environments,
        account_modes=paper_equity.account_modes,
        notes=(
            "execId is the provider execution identity.",
            "orderStatus never fabricates a Fill.",
        ),
    )
    scoped = {
        BrokerCapability.MARKET_ORDER: market,
        BrokerCapability.LIMIT_ORDER: limit_order,
        BrokerCapability.CANCEL_ORDER: cancel,
        BrokerCapability.RECONNECT_RECOVERY: reconnect,
        BrokerCapability.EXECUTION_FACTS: execution_facts,
    }

    return ProviderCapabilityManifest(
        provider=IBKR_PROVIDER_KEY,
        environment=RuntimeEnvironment.PAPER,
        adapter_version=IBKR_CERTIFICATION_ADAPTER_VERSION,
        account_mode="paper",
        asset_classes=frozenset({AssetClass.EQUITY}),
        supported_order_types=frozenset(
            {OrderType.MARKET, OrderType.LIMIT}
        ),
        supported_time_in_force=frozenset(
            {TimeInForce.DAY}
        ),
        capabilities=tuple(
            CapabilitySupport(
                capability=capability,
                constraints=scoped.get(
                    capability,
                    paper_equity,
                ),
            )
            for capability in IBKR_ACL_DECLARED_CAPABILITIES
        ),
        stream_model="ib_async-events",
        session_model="ib-gateway-socket",
        sdk_name=IBKR_ASYNC_PACKAGE_NAME,
        sdk_version=IBKR_ASYNC_VERSION_TARGET,
        known_limitations=(
            "PAPER only.",
            "US equities only.",
            "MARKET and LIMIT orders with DAY time in force.",
            "PARTIAL_FILL remains C2 until a real partial fill is observed.",
            "LATEST_QUOTE is not declared.",
            "REPLACE_ORDER is not declared.",
            "LIVE qualification is unavailable.",
        ),
    )


def build_ibkr_compliance_requirements() -> tuple[
    ComplianceRequirement,
    ...,
]:
    requirements: list[ComplianceRequirement] = []
    for capability in IBKR_ACL_DECLARED_CAPABILITIES:
        requirements.append(
            ComplianceRequirement(
                requirement_id=f"IBKR-{capability.value}-C2",
                capability=capability,
                level=CertificationLevel.C2_INTEGRATION_QUALIFIED,
                description=(
                    f"IBKR {capability.value} passes deterministic "
                    "integration qualification."
                ),
                criticality=_criticality(capability),
                applicable=True,
                evidence_type=ComplianceEvidenceType.INTEGRATION,
            )
        )
        if capability in IBKR_REAL_PAPER_C3_ELIGIBLE_CAPABILITIES:
            requirements.append(
                ComplianceRequirement(
                    requirement_id=f"IBKR-{capability.value}-C3",
                    capability=capability,
                    level=CertificationLevel.C3_PAPER_QUALIFIED,
                    description=(
                        f"IBKR {capability.value} is backed by retained "
                        "real PAPER evidence."
                    ),
                    criticality=_criticality(capability),
                    applicable=True,
                    evidence_type=ComplianceEvidenceType.PAPER,
                )
            )
    return tuple(requirements)


def build_ibkr_compliance_scenarios() -> tuple[
    ComplianceScenario,
    ...,
]:
    scenarios: list[ComplianceScenario] = []
    for capability in IBKR_ACL_DECLARED_CAPABILITIES:
        scenarios.append(
            ComplianceScenario(
                scenario_id=f"IBKR-{capability.value}-C2",
                capability=capability,
                preconditions=(
                    "qualified IBKR adapter implementation available",
                    "deterministic CI gate available",
                ),
                action=(
                    "validate deterministic semantics for "
                    f"{capability.value}"
                ),
                expected_result=(
                    "provider behavior remains compatible with "
                    "canonical semantics"
                ),
                failure_semantics=(
                    "deterministic mismatch prevents C2 and higher levels"
                ),
                cleanup=(
                    "no provider mutation in deterministic evidence replay"
                ),
                required_evidence=(
                    ComplianceEvidenceType.INTEGRATION,
                ),
                requirement_ids=(
                    f"IBKR-{capability.value}-C2",
                ),
            )
        )
        if capability in IBKR_REAL_PAPER_C3_ELIGIBLE_CAPABILITIES:
            scenarios.append(
                ComplianceScenario(
                    scenario_id=f"IBKR-{capability.value}-C3",
                    capability=capability,
                    preconditions=(
                        "retained sanitized real IBKR PAPER evidence available",
                        "controlled PAPER probe completed",
                    ),
                    action=(
                        "validate retained PAPER proof for "
                        f"{capability.value}"
                    ),
                    expected_result=(
                        "real provider behavior satisfies canonical "
                        "capability semantics"
                    ),
                    failure_semantics=(
                        "missing or contradictory provider proof prevents C3"
                    ),
                    cleanup=(
                        "source PAPER qualification restored its "
                        "controlled baseline"
                    ),
                    required_evidence=(
                        ComplianceEvidenceType.PAPER,
                    ),
                    requirement_ids=(
                        f"IBKR-{capability.value}-C3",
                    ),
                )
            )
    return tuple(scenarios)


def expected_ibkr_certification_levels(
    evidence: IBKRPaperEvidenceBundle,
) -> Mapping[BrokerCapability, CertificationLevel]:
    return MappingProxyType(
        {
            capability: (
                CertificationLevel.C3_PAPER_QUALIFIED
                if (
                    capability
                    in IBKR_REAL_PAPER_C3_ELIGIBLE_CAPABILITIES
                    and evidence.paper_proof_passes(capability)
                )
                else CertificationLevel.C2_INTEGRATION_QUALIFIED
            )
            for capability in IBKR_ACL_DECLARED_CAPABILITIES
        }
    )


def build_ibkr_certification_run(
    evidence: IBKRPaperEvidenceBundle,
) -> ComplianceRun:
    manifest = build_ibkr_certification_manifest()
    fixture = IBKRRetainedEvidenceFixture(manifest)
    requirements = build_ibkr_compliance_requirements()
    scenarios = build_ibkr_compliance_scenarios()
    executor = IBKRComplianceScenarioExecutor(evidence)
    executors = {
        scenario.scenario_id: executor
        for scenario in scenarios
    }

    harness = ComplianceHarness(
        contract=BROKER_ADAPTER_CONTRACT_V1_CANDIDATE,
        requirements=requirements,
        scenarios=scenarios,
        executors=executors,
        sanitizer=EvidenceSanitizer(),
        report_generator=ComplianceReportGenerator(),
        clock=_CapturedAtClock(evidence.captured_at),
    )
    run_suffix = (
        str(evidence.provenance.workflow_run_id)
        if evidence.provenance.workflow_run_id is not None
        else evidence.provenance.artifact_json_sha256[:12]
    )
    run = harness.run(
        fixture,
        run_id=f"ibkr-paper-{run_suffix}",
        commit_sha=evidence.provenance.qualified_commit,
        manifest_version=PROVIDER_CAPABILITY_MANIFEST_VERSION,
    )
    validate_ibkr_certification_run(
        run,
        evidence=evidence,
    )
    return run


def validate_ibkr_certification_run(
    run: ComplianceRun,
    *,
    evidence: IBKRPaperEvidenceBundle,
) -> None:
    observed = {
        item.capability: item.certification_level
        for item in run.report.capability_results
    }
    expected = dict(
        expected_ibkr_certification_levels(evidence)
    )
    if observed != expected:
        raise ValueError(
            "IBKR certification matrix does not match retained evidence."
        )
    if (
        evidence.controlled_probe_passed
        and evidence.cleanup_passed
        and evidence.real_provider_used
        and not run.report.complete
    ):
        raise ValueError(
            "IBKR certification report contains failed or blocked scenarios."
        )


def _criticality(
    capability: BrokerCapability,
) -> ComplianceCriticality:
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
        passed = callable(
            getattr(IBKRBrokerSnapshotPort, "capture", None)
        )
    elif capability is BrokerCapability.ORDER_QUERY:
        passed = callable(
            getattr(IBKRExecutionAdapter, "query_order", None)
        )
    elif capability in {
        BrokerCapability.MARKET_ORDER,
        BrokerCapability.LIMIT_ORDER,
    }:
        passed = (
            callable(map_ibkr_order_command)
            and callable(
                getattr(IBKRExecutionAdapter, "submit", None)
            )
        )
    elif capability is BrokerCapability.CANCEL_ORDER:
        passed = callable(
            getattr(IBKRExecutionAdapter, "cancel", None)
        )
    elif capability is BrokerCapability.PARTIAL_FILL:
        rule = ibkr_order_status_rule(
            IBKROrderStatus.SUBMITTED
        )
        passed = (
            rule.canonical_status
            is ExecutionStatus.ACCEPTED
            and callable(map_ibkr_execution_report)
        )
        detail["fill_source"] = "execDetails"
    elif capability in {
        BrokerCapability.POSITION_QUERY,
        BrokerCapability.BALANCE_QUERY,
    }:
        passed = callable(
            getattr(IBKRBrokerSnapshotPort, "capture", None)
        )
    elif capability is BrokerCapability.CLIENT_ORDER_REFERENCE:
        passed = callable(map_ibkr_order_command)
        detail["correlation_field"] = "orderRef"
    elif capability is BrokerCapability.EXECUTION_FACTS:
        passed = callable(map_ibkr_execution_report)
        detail["provider_execution_identity"] = "execId"
    elif capability is BrokerCapability.RECONNECT_RECOVERY:
        passed = callable(
            getattr(IBKRReconnectRecoveryRuntime, "recover", None)
        )
        detail["economic_replay"] = False
    else:
        passed = False

    detail["passed"] = passed
    return passed, detail
