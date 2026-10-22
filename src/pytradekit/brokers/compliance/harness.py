"""Provider-neutral executable broker compliance harness."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Protocol

from pytradekit.runtime.configuration import RuntimeEnvironment
from pytradekit.runtime.ports import ClockPort

from ._validation import required_text
from .certification import CertifiedCapability
from .certification_level import CertificationLevel
from .contract import BrokerAdapterContract
from .evidence import ComplianceEvidence
from .fixture import ProviderFixture
from .manifest import ProviderCapabilityManifest
from .registry import CertificationRegistry
from .report import ComplianceReport, ComplianceReportGenerator
from .requirement import (
    ComplianceCriticality,
    ComplianceEvidenceType,
    ComplianceRequirement,
)
from .result import ComplianceResult, ComplianceStatus
from .sanitization import EvidenceSanitizer
from .scenario import ComplianceScenario


class ComplianceBlockedError(RuntimeError):
    """Scenario precondition or external dependency prevents execution."""


class ComplianceScenarioFailure(RuntimeError):
    """Scenario executed and observed behavior violated the requirement."""


@dataclass(frozen=True, slots=True)
class ComplianceObservation:
    """Provider-specific executor output consumed by the common harness."""

    status: ComplianceStatus
    evidence_type: ComplianceEvidenceType
    payload: Mapping[str, object]
    reason: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, ComplianceStatus):
            raise ValueError("status must be a ComplianceStatus.")
        if not isinstance(self.evidence_type, ComplianceEvidenceType):
            raise ValueError("evidence_type must be a ComplianceEvidenceType.")
        if self.status is not ComplianceStatus.PASS and self.reason is None:
            raise ValueError("Non-PASS observations require a reason.")
        if self.reason is not None:
            object.__setattr__(
                self,
                "reason",
                required_text(self.reason, field_name="reason"),
            )
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))


class ComplianceScenarioExecutor(Protocol):
    """Callable provider-specific scenario implementation."""

    def __call__(
        self,
        fixture: ProviderFixture,
        scenario: ComplianceScenario,
    ) -> ComplianceObservation:
        """Execute one scenario against the supplied provider fixture."""

        ...


@dataclass(frozen=True, slots=True)
class ComplianceRun:
    """Report, evidence, and generated registry emitted by one harness run."""

    report: ComplianceReport
    evidence: tuple[ComplianceEvidence, ...]
    registry: CertificationRegistry

    @property
    def evidence_by_ref(self) -> Mapping[str, ComplianceEvidence]:
        """Return evidence indexed by stable evidence reference."""

        return MappingProxyType({item.evidence_id: item for item in self.evidence})

    def to_dict(self) -> dict[str, object]:
        """Return a complete JSON-ready qualification artifact."""

        return {
            "report": self.report.to_dict(),
            "evidence": [item.to_dict() for item in self.evidence],
            "registry": self.registry.to_dict(),
        }

    def to_json(self) -> str:
        """Serialize the qualification artifact deterministically."""

        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )


class ComplianceHarness:
    """Run the same compliance model against any ProviderFixture implementation."""

    def __init__(
        self,
        *,
        contract: BrokerAdapterContract,
        requirements: tuple[ComplianceRequirement, ...],
        scenarios: tuple[ComplianceScenario, ...],
        executors: Mapping[str, ComplianceScenarioExecutor],
        sanitizer: EvidenceSanitizer,
        report_generator: ComplianceReportGenerator,
        clock: ClockPort,
    ) -> None:
        self._contract = contract
        self._requirements = requirements
        self._scenarios = scenarios
        self._executors = dict(executors)
        self._sanitizer = sanitizer
        self._report_generator = report_generator
        self._clock = clock
        self._validate_suite()

    def run(
        self,
        fixture: ProviderFixture,
        *,
        run_id: str,
        commit_sha: str,
        manifest_version: str,
        sensitive_values: Iterable[str] = (),
        waivers: tuple[str, ...] = (),
    ) -> ComplianceRun:
        """Run qualification and emit deterministic secret-safe evidence."""

        normalized_run_id = required_text(run_id, field_name="run_id")
        normalized_commit = required_text(commit_sha, field_name="commit_sha")
        normalized_manifest_version = required_text(
            manifest_version,
            field_name="manifest_version",
        )
        secrets = tuple(sensitive_values)

        manifest = fixture.provider_manifest()
        self._contract.validate_manifest(manifest)

        results: list[ComplianceResult] = []
        evidence: list[ComplianceEvidence] = []
        for scenario in self._scenarios:
            result, item = self._run_scenario(
                fixture,
                scenario=scenario,
                manifest=manifest,
                run_id=normalized_run_id,
                commit_sha=normalized_commit,
                sensitive_values=secrets,
            )
            results.append(result)
            if item is not None:
                evidence.append(item)

        generated_at = self._clock.now()
        certifications = self._certify(
            manifest=manifest,
            commit_sha=normalized_commit,
            results=tuple(results),
            evidence=tuple(evidence),
            qualified_at=generated_at,
        )
        report = self._report_generator.generate(
            manifest=manifest,
            commit_sha=normalized_commit,
            manifest_version=normalized_manifest_version,
            contract_version=self._contract.version,
            scenario_results=tuple(results),
            capability_results=certifications,
            evidence=tuple(evidence),
            generated_at=generated_at,
            waivers=waivers,
        )
        artifact = ComplianceRun(
            report=report,
            evidence=tuple(evidence),
            registry=CertificationRegistry.from_report(report),
        )
        self._sanitizer.assert_safe(
            artifact.to_dict(),
            sensitive_values=secrets,
        )
        return artifact

    def _validate_suite(self) -> None:
        requirement_by_id: dict[str, ComplianceRequirement] = {}
        for requirement in self._requirements:
            if requirement.requirement_id in requirement_by_id:
                raise ValueError("Compliance requirement IDs must be unique.")
            requirement_by_id[requirement.requirement_id] = requirement

        scenario_ids: set[str] = set()
        for scenario in self._scenarios:
            if scenario.scenario_id in scenario_ids:
                raise ValueError("Compliance scenario IDs must be unique.")
            scenario_ids.add(scenario.scenario_id)
            for requirement_id in scenario.requirement_ids:
                requirement = requirement_by_id.get(requirement_id)
                if requirement is None:
                    raise ValueError(
                        f"Scenario {scenario.scenario_id} references unknown requirement "
                        f"{requirement_id}."
                    )
                if requirement.capability is not scenario.capability:
                    raise ValueError(
                        f"Scenario {scenario.scenario_id} capability does not match "
                        f"requirement {requirement_id}."
                    )

        unknown_executors = set(self._executors) - scenario_ids
        if unknown_executors:
            raise ValueError("Executors reference unknown compliance scenarios.")

    def _run_scenario(
        self,
        fixture: ProviderFixture,
        *,
        scenario: ComplianceScenario,
        manifest: ProviderCapabilityManifest,
        run_id: str,
        commit_sha: str,
        sensitive_values: tuple[str, ...],
    ) -> tuple[ComplianceResult, ComplianceEvidence | None]:
        started_at = self._clock.now()
        requirements = self._requirements_for_scenario(scenario)

        if not any(requirement.applicable for requirement in requirements):
            completed_at = self._clock.now()
            return (
                ComplianceResult(
                    scenario_id=scenario.scenario_id,
                    status=ComplianceStatus.NOT_APPLICABLE,
                    started_at=started_at,
                    completed_at=completed_at,
                    provider=manifest.provider,
                    environment=manifest.environment,
                    reason="No applicable compliance requirement for this scenario.",
                ),
                None,
            )

        if not manifest.supports(scenario.capability):
            return self._finalize_observation(
                scenario=scenario,
                manifest=manifest,
                observation=ComplianceObservation(
                    status=ComplianceStatus.FAIL,
                    evidence_type=ComplianceEvidenceType.DIAGNOSTIC,
                    payload={"manifest_support": False},
                    reason="Manifest does not declare the required capability.",
                ),
                run_id=run_id,
                commit_sha=commit_sha,
                started_at=started_at,
                sensitive_values=sensitive_values,
            )

        executor = self._executors.get(scenario.scenario_id)
        if executor is None:
            return self._finalize_observation(
                scenario=scenario,
                manifest=manifest,
                observation=ComplianceObservation(
                    status=ComplianceStatus.BLOCKED,
                    evidence_type=ComplianceEvidenceType.DIAGNOSTIC,
                    payload={"executor_available": False},
                    reason="Scenario executor is unavailable.",
                ),
                run_id=run_id,
                commit_sha=commit_sha,
                started_at=started_at,
                sensitive_values=sensitive_values,
            )

        try:
            observation = executor(fixture, scenario)
        except ComplianceBlockedError:
            observation = ComplianceObservation(
                status=ComplianceStatus.BLOCKED,
                evidence_type=ComplianceEvidenceType.DIAGNOSTIC,
                payload={"exception_type": "ComplianceBlockedError"},
                reason="Scenario was blocked by a declared precondition.",
            )
        except ComplianceScenarioFailure:
            observation = ComplianceObservation(
                status=ComplianceStatus.FAIL,
                evidence_type=ComplianceEvidenceType.DIAGNOSTIC,
                payload={"exception_type": "ComplianceScenarioFailure"},
                reason="Observed provider behavior violated the compliance scenario.",
            )
        except Exception as exc:
            observation = ComplianceObservation(
                status=ComplianceStatus.FAIL,
                evidence_type=ComplianceEvidenceType.DIAGNOSTIC,
                payload={"exception_type": type(exc).__name__},
                reason="Scenario raised an unexpected provider qualification error.",
            )

        try:
            fixture.cleanup()
        except Exception as exc:
            observation = ComplianceObservation(
                status=ComplianceStatus.BLOCKED,
                evidence_type=ComplianceEvidenceType.DIAGNOSTIC,
                payload={
                    "cleanup": "failed",
                    "cleanup_exception_type": type(exc).__name__,
                    "prior_status": observation.status.value,
                },
                reason="Provider fixture cleanup failed; qualification is blocked.",
            )

        if (
            observation.status is ComplianceStatus.PASS
            and observation.evidence_type not in scenario.required_evidence
        ):
            observation = ComplianceObservation(
                status=ComplianceStatus.FAIL,
                evidence_type=ComplianceEvidenceType.DIAGNOSTIC,
                payload={
                    "observed_evidence_type": observation.evidence_type.value,
                    "required_evidence_types": [
                        value.value for value in scenario.required_evidence
                    ],
                },
                reason="Scenario passed without an accepted evidence type.",
            )

        return self._finalize_observation(
            scenario=scenario,
            manifest=manifest,
            observation=observation,
            run_id=run_id,
            commit_sha=commit_sha,
            started_at=started_at,
            sensitive_values=sensitive_values,
        )

    def _finalize_observation(
        self,
        *,
        scenario: ComplianceScenario,
        manifest: ProviderCapabilityManifest,
        observation: ComplianceObservation,
        run_id: str,
        commit_sha: str,
        started_at: datetime,
        sensitive_values: tuple[str, ...],
    ) -> tuple[ComplianceResult, ComplianceEvidence]:
        completed_at = self._clock.now()
        evidence_id = f"{run_id}:{scenario.scenario_id}"
        sanitized_payload = self._sanitizer.sanitize(
            {
                "run_id": run_id,
                "scenario_id": scenario.scenario_id,
                "capability": scenario.capability.value,
                "status": observation.status.value,
                "reason": observation.reason,
                "observation": dict(observation.payload),
            },
            sensitive_values=sensitive_values,
        )
        evidence = ComplianceEvidence(
            evidence_id=evidence_id,
            scenario_id=scenario.scenario_id,
            provider=manifest.provider,
            environment=manifest.environment,
            commit_sha=commit_sha,
            adapter_version=manifest.adapter_version,
            contract_version=self._contract.version,
            evidence_type=observation.evidence_type,
            captured_at=completed_at,
            payload=sanitized_payload,
            sdk_name=manifest.sdk_name,
            sdk_version=manifest.sdk_version,
            artifact_ref=(
                "artifacts/qualification/brokers/"
                f"{manifest.provider}/{run_id}.json#{scenario.scenario_id}"
            ),
        )
        return (
            ComplianceResult(
                scenario_id=scenario.scenario_id,
                status=observation.status,
                started_at=started_at,
                completed_at=completed_at,
                provider=manifest.provider,
                environment=manifest.environment,
                evidence_refs=(evidence.evidence_id,),
                reason=observation.reason,
            ),
            evidence,
        )

    def _requirements_for_scenario(
        self,
        scenario: ComplianceScenario,
    ) -> tuple[ComplianceRequirement, ...]:
        requirement_ids = frozenset(scenario.requirement_ids)
        return tuple(
            requirement
            for requirement in self._requirements
            if requirement.requirement_id in requirement_ids
        )

    def _certify(
        self,
        *,
        manifest: ProviderCapabilityManifest,
        commit_sha: str,
        results: tuple[ComplianceResult, ...],
        evidence: tuple[ComplianceEvidence, ...],
        qualified_at: datetime,
    ) -> tuple[CertifiedCapability, ...]:
        result_by_scenario = {result.scenario_id: result for result in results}
        evidence_by_scenario = {item.scenario_id: item for item in evidence}
        certifications: list[CertifiedCapability] = []

        for support in manifest.capabilities:
            requirements = tuple(
                requirement
                for requirement in self._requirements
                if requirement.capability is support.capability and requirement.applicable
            )
            level = CertificationLevel.C0_DEFINED
            evidence_refs: set[str] = set()

            for target in (
                CertificationLevel.C1_IMPLEMENTED,
                CertificationLevel.C2_INTEGRATION_QUALIFIED,
                CertificationLevel.C3_PAPER_QUALIFIED,
                CertificationLevel.C4_LIVE_LIMITED,
                CertificationLevel.C5_LIVE_QUALIFIED,
            ):
                exact_requirements = tuple(
                    requirement
                    for requirement in requirements
                    if requirement.level is target
                )
                if not exact_requirements:
                    continue
                cumulative = tuple(
                    requirement
                    for requirement in requirements
                    if requirement.level <= target
                )
                if not all(
                    self._requirement_passed(
                        requirement,
                        result_by_scenario=result_by_scenario,
                        evidence_by_scenario=evidence_by_scenario,
                    )
                    for requirement in cumulative
                ):
                    break
                if target is CertificationLevel.C3_PAPER_QUALIFIED:
                    if manifest.environment is not RuntimeEnvironment.PAPER:
                        break
                if target >= CertificationLevel.C4_LIVE_LIMITED:
                    break

                level = target
                for requirement in cumulative:
                    for scenario in self._scenarios_for_requirement(requirement):
                        result = result_by_scenario.get(scenario.scenario_id)
                        if result is not None:
                            evidence_refs.update(result.evidence_refs)

            if (
                level >= CertificationLevel.C3_PAPER_QUALIFIED
                and self._has_critical_failure(
                    requirements,
                    result_by_scenario=result_by_scenario,
                    evidence_by_scenario=evidence_by_scenario,
                )
            ):
                level = CertificationLevel.C2_INTEGRATION_QUALIFIED

            certifications.append(
                CertifiedCapability(
                    provider=manifest.provider,
                    environment=manifest.environment,
                    capability=support.capability,
                    certification_level=level,
                    contract_version=self._contract.version,
                    qualified_at=qualified_at,
                    evidence_refs=tuple(sorted(evidence_refs)),
                    known_limitations=manifest.known_limitations,
                    constraints=support.constraints,
                    qualified_commit=commit_sha,
                    adapter_version=manifest.adapter_version,
                    sdk_name=manifest.sdk_name,
                    sdk_version=manifest.sdk_version,
                )
            )

        return tuple(certifications)

    def _has_critical_failure(
        self,
        requirements: tuple[ComplianceRequirement, ...],
        *,
        result_by_scenario: Mapping[str, ComplianceResult],
        evidence_by_scenario: Mapping[str, ComplianceEvidence],
    ) -> bool:
        return any(
            requirement.criticality is ComplianceCriticality.CRITICAL
            and not self._requirement_passed(
                requirement,
                result_by_scenario=result_by_scenario,
                evidence_by_scenario=evidence_by_scenario,
            )
            for requirement in requirements
        )

    def _requirement_passed(
        self,
        requirement: ComplianceRequirement,
        *,
        result_by_scenario: Mapping[str, ComplianceResult],
        evidence_by_scenario: Mapping[str, ComplianceEvidence],
    ) -> bool:
        scenarios = self._scenarios_for_requirement(requirement)
        if not scenarios:
            return False
        for scenario in scenarios:
            result = result_by_scenario.get(scenario.scenario_id)
            item = evidence_by_scenario.get(scenario.scenario_id)
            if result is None or result.status is not ComplianceStatus.PASS:
                return False
            if item is None or item.evidence_type is not requirement.evidence_type:
                return False
        return True

    def _scenarios_for_requirement(
        self,
        requirement: ComplianceRequirement,
    ) -> tuple[ComplianceScenario, ...]:
        return tuple(
            scenario
            for scenario in self._scenarios
            if requirement.requirement_id in scenario.requirement_ids
        )
