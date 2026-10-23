"""IBKR capability compliance and optional real PAPER certification."""

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
from pytradekit.orders.ports import ExecutionPort
from pytradekit.reconciliation.ports import BrokerSnapshotPort

from .capability_manifest import (
    IBKR_ACL_DECLARED_CAPABILITIES,
    build_ibkr_capability_manifest,
)
from .discovery import IBKR_PROVIDER_KEY
from .execution import IBKRExecutionAdapter
from .execution_mapping import map_ibkr_execution_report
from .market_rules import IBKRMarketRuleResolver
from .operations_runtime import IBKRReconnectRecoveryRuntime
from .order_callbacks import map_ibkr_order_status_report
from .order_commands import map_ibkr_order_command
from .order_session import IBKROrderSessionRuntime
from .paper_evidence import IBKRPaperEvidenceBundle
from .read_side import IBKRBrokerSnapshotPort
from .runtime import IBKR_ASYNC_PACKAGE_NAME, IBKR_ASYNC_VERSION_TARGET

IBKR_COMPLIANCE_ADAPTER_VERSION = "0.8.0b8-lot06.7"

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
    """Evidence-replay fixture used by the common compliance harness."""

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
            "Retained evidence replay does not materialize a snapshot adapter."
        )

    def paper_account_fixture(self) -> ProviderAccountIdentity:
        raise ComplianceBlockedError(
            "Retained evidence exposes only a masked PAPER account identity."
        )

    def cleanup(self) -> None:
        self.cleanup_calls += 1


@dataclass(frozen=True, slots=True)
class _CapturedAtClock:
    captured_at: datetime

    def now(self) -> datetime:
        return self.captured_at


class IBKRComplianceScenarioExecutor:
    """Execute deterministic checks and retained PAPER proof replay."""

    def __init__(
        self,
        evidence: IBKRPaperEvidenceBundle | None,
    ) -> None:
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
                reason="IBKR compliance executor received a non-IBKR fixture.",
            )

        required = scenario.required_evidence[0]
        if required is ComplianceEvidenceType.INTEGRATION:
            return self._integration_observation(manifest, scenario)
        if required is ComplianceEvidenceType.PAPER:
            return self._paper_observation(scenario)

        return ComplianceObservation(
            status=ComplianceStatus.FAIL,
            evidence_type=ComplianceEvidenceType.DIAGNOSTIC,
            payload={"required_evidence": required.value},
            reason="IBKR LOT-06.7 supports INTEGRATION and PAPER evidence only.",
        )

    def _integration_observation(
        self,
        manifest: ProviderCapabilityManifest,
        scenario: ComplianceScenario,
    ) -> ComplianceObservation:
        passed, detail = _deterministic_capability_check(
            manifest,
            scenario.capability,
        )
        payload: dict[str, object] = {
            "qualification_class": "deterministic",
            "capability": scenario.capability.value,
            "deterministic_check": detail,
        }
        return ComplianceObservation(
            status=ComplianceStatus.PASS if passed else ComplianceStatus.FAIL,
            evidence_type=(
                ComplianceEvidenceType.INTEGRATION
                if passed
                else ComplianceEvidenceType.DIAGNOSTIC
            ),
            payload=payload,
            reason=None if passed else (
                "Deterministic IBKR capability qualification failed."
            ),
        )

    def _paper_observation(
        self,
        scenario: ComplianceScenario,
    ) -> ComplianceObservation:
        evidence = self._evidence
        if evidence is None:
            return ComplianceObservation(
                status=ComplianceStatus.BLOCKED,
                evidence_type=ComplianceEvidenceType.DIAGNOSTIC,
                payload={"real_paper_evidence_available": False},
                reason="No retained real IBKR PAPER evidence is available.",
            )

        claimed = scenario.capability in evidence.c3_capabilities
        passed = claimed and evidence.paper_proof_passes(
            scenario.capability
        )
        payload = evidence.common_evidence_payload()
        payload["qualification_class"] = "real-paper"
        payload["capability"] = scenario.capability.value
        payload["c3_claimed"] = claimed
        try:
            payload["proof"] = dict(
                evidence.proof_for(scenario.capability)
            )
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
            reason=None if passed else (
                "Retained real IBKR PAPER evidence is insufficient."
            ),
        )


def build_ibkr_compliance_manifest() -> ProviderCapabilityManifest:
    """Return the runtime-aware 0.8.0b8 IBKR PAPER capability declaration."""

    base = build_ibkr_capability_manifest()
    return ProviderCapabilityManifest(
        provider=base.provider,
        environment=base.environment,
        adapter_version=IBKR_COMPLIANCE_ADAPTER_VERSION,
        account_mode=base.account_mode,
        asset_classes=base.asset_classes,
        supported_order_types=base.supported_order_types,
        supported_time_in_force=base.supported_time_in_force,
        capabilities=base.capabilities,
        stream_model=base.stream_model,
        session_model=base.session_model,
        sdk_name=IBKR_ASYNC_PACKAGE_NAME,
        sdk_version=IBKR_ASYNC_VERSION_TARGET,
        known_limitations=(
            "PAPER only.",
            "US equities only.",
            "MARKET and LIMIT submission with DAY time in force.",
            "LATEST_QUOTE is not declared.",
            "REPLACE_ORDER is not declared.",
            (
                "PARTIAL_FILL remains C2 unless a retained PAPER artifact "
                "contains an observed partial execution."
            ),
            (
                "C3 claims require retained real PAPER evidence linked to "
                "the qualified commit and exact ib_async version."
            ),
            "LIVE qualification is unavailable.",
        ),
    )


def build_ibkr_compliance_requirements(
    evidence: IBKRPaperEvidenceBundle | None = None,
) -> tuple[ComplianceRequirement, ...]:
    """Build C2 requirements and only evidence-backed C3 requirements."""

    requirements: list[ComplianceRequirement] = []
    c3 = (
        frozenset()
        if evidence is None
        else frozenset(evidence.c3_capabilities)
    )
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
        if capability in c3:
            requirements.append(
                ComplianceRequirement(
                    requirement_id=f"IBKR-{capability.value}-C3",
                    capability=capability,
                    level=CertificationLevel.C3_PAPER_QUALIFIED,
                    description=(
                        f"IBKR {capability.value} is backed by retained "
                        "real PAPER provider evidence."
                    ),
                    criticality=_criticality(capability),
                    applicable=True,
                    evidence_type=ComplianceEvidenceType.PAPER,
                )
            )
    return tuple(requirements)


def build_ibkr_compliance_scenarios(
    evidence: IBKRPaperEvidenceBundle | None = None,
) -> tuple[ComplianceScenario, ...]:
    """Build deterministic scenarios and explicit evidence-backed C3 scenarios."""

    scenarios: list[ComplianceScenario] = []
    c3 = (
        frozenset()
        if evidence is None
        else frozenset(evidence.c3_capabilities)
    )
    for capability in IBKR_ACL_DECLARED_CAPABILITIES:
        scenarios.append(
            ComplianceScenario(
                scenario_id=f"IBKR-{capability.value}-C2",
                capability=capability,
                preconditions=(
                    "qualified IBKR adapter code available",
                    "deterministic CI gate available",
                ),
                action=(
                    f"validate deterministic semantics for {capability.value}"
                ),
                expected_result=(
                    "adapter behavior remains compatible with canonical semantics"
                ),
                failure_semantics=(
                    "deterministic mismatch prevents C2 and all higher levels"
                ),
                cleanup="no provider mutation in deterministic qualification",
                required_evidence=(ComplianceEvidenceType.INTEGRATION,),
                requirement_ids=(f"IBKR-{capability.value}-C2",),
            )
        )
        if capability in c3:
            scenarios.append(
                ComplianceScenario(
                    scenario_id=f"IBKR-{capability.value}-C3",
                    capability=capability,
                    preconditions=(
                        "retained sanitized real IBKR PAPER evidence available",
                        "artifact provenance and SHA-256 validated",
                    ),
                    action=(
                        f"validate retained PAPER proof for {capability.value}"
                    ),
                    expected_result=(
                        "real provider behavior satisfies canonical semantics"
                    ),
                    failure_semantics=(
                        "missing or contradictory provider proof prevents C3"
                    ),
                    cleanup=(
                        "controlled PAPER probe restored its declared baseline"
                    ),
                    required_evidence=(ComplianceEvidenceType.PAPER,),
                    requirement_ids=(f"IBKR-{capability.value}-C3",),
                )
            )
    return tuple(scenarios)


def build_ibkr_certification_run(
    *,
    commit_sha: str,
    captured_at: datetime,
    evidence: IBKRPaperEvidenceBundle | None = None,
) -> ComplianceRun:
    """Run deterministic IBKR certification plus optional retained PAPER replay."""

    if not isinstance(commit_sha, str) or not commit_sha.strip():
        raise ValueError("commit_sha must be non-empty.")
    manifest = build_ibkr_compliance_manifest()
    fixture = IBKRRetainedEvidenceFixture(manifest)
    requirements = build_ibkr_compliance_requirements(evidence)
    scenarios = build_ibkr_compliance_scenarios(evidence)
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
        clock=_CapturedAtClock(captured_at),
    )
    run_id = (
        f"ibkr-paper-{evidence.provenance.artifact_json_sha256[:12]}"
        if evidence is not None
        else f"ibkr-deterministic-{commit_sha[:12]}"
    )
    qualified_commit = (
        evidence.provenance.qualified_commit
        if evidence is not None
        else commit_sha.strip()
    )
    if evidence is not None and commit_sha.strip() != qualified_commit:
        raise ValueError(
            "Retained IBKR PAPER evidence commit does not match "
            "the certification target commit."
        )

    run = harness.run(
        fixture,
        run_id=run_id,
        commit_sha=qualified_commit,
        manifest_version=PROVIDER_CAPABILITY_MANIFEST_VERSION,
    )
    validate_ibkr_certification_run(
        run,
        c3_capabilities=(
            ()
            if evidence is None
            else evidence.c3_capabilities
        ),
    )
    return run


def validate_ibkr_certification_run(
    run: ComplianceRun,
    *,
    c3_capabilities: tuple[BrokerCapability, ...],
) -> None:
    """Fail closed if the generated matrix exceeds retained proof."""

    expected = dict(IBKR_BASELINE_CERTIFICATION_LEVELS)
    for capability in c3_capabilities:
        expected[capability] = CertificationLevel.C3_PAPER_QUALIFIED

    observed = {
        item.capability: item.certification_level
        for item in run.report.capability_results
    }
    if observed != expected:
        raise ValueError(
            "IBKR certification matrix does not match the evidence-backed target."
        )
    if not run.report.complete:
        raise ValueError(
            "IBKR compliance report contains failed or blocked scenarios."
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
        "sdk": {
            "name": manifest.sdk_name,
            "version": manifest.sdk_version,
        },
    }
    if not declared:
        return False, detail

    if capability is BrokerCapability.ACCOUNT_QUERY:
        passed = callable(getattr(IBKRBrokerSnapshotPort, "capture", None))
    elif capability is BrokerCapability.ORDER_QUERY:
        passed = callable(getattr(IBKRExecutionAdapter, "query_order", None))
    elif capability is BrokerCapability.MARKET_ORDER:
        passed = (
            callable(getattr(IBKRExecutionAdapter, "submit", None))
            and callable(map_ibkr_order_command)
        )
    elif capability is BrokerCapability.LIMIT_ORDER:
        passed = (
            callable(getattr(IBKRExecutionAdapter, "submit", None))
            and callable(IBKRMarketRuleResolver.validate_limit_price)
        )
    elif capability is BrokerCapability.CANCEL_ORDER:
        passed = callable(getattr(IBKRExecutionAdapter, "cancel", None))
    elif capability is BrokerCapability.PARTIAL_FILL:
        passed = callable(map_ibkr_execution_report)
    elif capability in {
        BrokerCapability.POSITION_QUERY,
        BrokerCapability.BALANCE_QUERY,
    }:
        passed = callable(getattr(IBKRBrokerSnapshotPort, "capture", None))
    elif capability is BrokerCapability.CLIENT_ORDER_REFERENCE:
        passed = callable(getattr(IBKROrderSessionRuntime, "reserve", None))
    elif capability is BrokerCapability.EXECUTION_FACTS:
        passed = callable(map_ibkr_execution_report)
    elif capability is BrokerCapability.RECONNECT_RECOVERY:
        passed = callable(getattr(IBKRReconnectRecoveryRuntime, "recover", None))
    else:
        passed = False

    detail["passed"] = passed
    detail["order_status_mapping"] = callable(map_ibkr_order_status_report)
    return passed, detail
