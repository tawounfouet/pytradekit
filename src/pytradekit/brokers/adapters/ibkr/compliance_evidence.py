"""Retained IBKR PAPER evidence normalization for broker compliance."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from types import MappingProxyType

from pytradekit.brokers.compliance import BrokerCapability
from pytradekit.shared import require_utc_datetime

from .discovery import IBKR_PROVIDER_KEY
from .runtime import IBKR_ASYNC_PACKAGE_NAME, IBKR_ASYNC_VERSION_TARGET


class IBKREvidenceError(ValueError):
    """Raised when retained IBKR PAPER qualification evidence is malformed."""


@dataclass(frozen=True, slots=True)
class IBKRPaperEvidenceProvenance:
    """Immutable source identity for retained real IBKR PAPER evidence."""

    source_release: str
    qualified_commit: str
    artifact_name: str
    artifact_json_sha256: str
    workflow_run_id: int | None = None
    artifact_id: int | None = None
    artifact_zip_sha256: str | None = None
    deterministic_ci_run_id: int | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "source_release",
            "qualified_commit",
            "artifact_name",
            "artifact_json_sha256",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise IBKREvidenceError(f"{field_name} must be non-empty.")
            object.__setattr__(self, field_name, value.strip())

        _require_sha256(
            self.artifact_json_sha256,
            field_name="artifact_json_sha256",
        )
        if self.artifact_zip_sha256 is not None:
            normalized = self.artifact_zip_sha256.strip()
            _require_sha256(
                normalized,
                field_name="artifact_zip_sha256",
            )
            object.__setattr__(
                self,
                "artifact_zip_sha256",
                normalized,
            )

        for field_name in (
            "workflow_run_id",
            "artifact_id",
            "deterministic_ci_run_id",
        ):
            value = getattr(self, field_name)
            if value is not None and (
                type(value) is not int or value <= 0
            ):
                raise IBKREvidenceError(
                    f"{field_name} must be a positive integer."
                )

    @property
    def source_ref(self) -> str:
        """Return a stable non-secret source artifact reference."""

        run = (
            f"run:{self.workflow_run_id}"
            if self.workflow_run_id is not None
            else "run:unknown"
        )
        artifact = (
            f"artifact:{self.artifact_id}"
            if self.artifact_id is not None
            else f"artifact-name:{self.artifact_name}"
        )
        return f"github-actions:{IBKR_PROVIDER_KEY}:{run}:{artifact}"

    def to_dict(self) -> dict[str, object]:
        return {
            "source_release": self.source_release,
            "qualified_commit": self.qualified_commit,
            "deterministic_ci_run_id": self.deterministic_ci_run_id,
            "workflow_run_id": self.workflow_run_id,
            "artifact_id": self.artifact_id,
            "artifact_name": self.artifact_name,
            "artifact_zip_sha256": self.artifact_zip_sha256,
            "artifact_json_sha256": self.artifact_json_sha256,
            "source_ref": self.source_ref,
        }

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, object],
    ) -> IBKRPaperEvidenceProvenance:
        return cls(
            source_release=_text(
                payload.get("source_release"),
                "source_release",
            ),
            qualified_commit=_text(
                payload.get("qualified_commit"),
                "qualified_commit",
            ),
            deterministic_ci_run_id=_optional_positive_int(
                payload.get("deterministic_ci_run_id"),
                "deterministic_ci_run_id",
            ),
            workflow_run_id=_optional_positive_int(
                payload.get("workflow_run_id"),
                "workflow_run_id",
            ),
            artifact_id=_optional_positive_int(
                payload.get("artifact_id"),
                "artifact_id",
            ),
            artifact_name=_text(
                payload.get("artifact_name"),
                "artifact_name",
            ),
            artifact_zip_sha256=_optional_text(
                payload.get("artifact_zip_sha256")
            ),
            artifact_json_sha256=_text(
                payload.get("artifact_json_sha256"),
                "artifact_json_sha256",
            ),
        )


_PAPER_GATE_REQUIREMENTS: Mapping[
    BrokerCapability,
    tuple[str, ...],
] = MappingProxyType(
    {
        BrokerCapability.ACCOUNT_QUERY: (
            "real_paper_preflight",
        ),
        BrokerCapability.ORDER_QUERY: (
            "real_paper_orders",
            "real_paper_callbacks",
        ),
        BrokerCapability.MARKET_ORDER: (
            "real_paper_orders",
            "real_paper_callbacks",
        ),
        BrokerCapability.LIMIT_ORDER: (
            "real_paper_orders",
        ),
        BrokerCapability.CANCEL_ORDER: (
            "real_paper_orders",
            "real_paper_callbacks",
        ),
        BrokerCapability.POSITION_QUERY: (
            "real_paper_preflight",
            "real_paper_cleanup",
        ),
        BrokerCapability.BALANCE_QUERY: (
            "real_paper_preflight",
        ),
        BrokerCapability.CLIENT_ORDER_REFERENCE: (
            "real_paper_orders",
            "real_paper_callbacks",
        ),
        BrokerCapability.EXECUTION_FACTS: (
            "real_paper_callbacks",
        ),
        BrokerCapability.RECONNECT_RECOVERY: (
            "real_paper_reconnect",
        ),
    }
)


@dataclass(frozen=True, slots=True)
class IBKRPaperEvidenceBundle:
    """Normalized capability evidence from one real IBKR PAPER run."""

    provenance: IBKRPaperEvidenceProvenance
    captured_at: datetime
    sdk_name: str
    sdk_version: str
    real_provider_used: bool
    controlled_probe_passed: bool
    cleanup_passed: bool
    gates: Mapping[str, str]
    proofs: Mapping[BrokerCapability, Mapping[str, object]]

    def __post_init__(self) -> None:
        if not isinstance(
            self.provenance,
            IBKRPaperEvidenceProvenance,
        ):
            raise IBKREvidenceError(
                "provenance must be an IBKRPaperEvidenceProvenance."
            )
        require_utc_datetime(
            self.captured_at,
            field_name="IBKRPaperEvidenceBundle captured_at",
        )
        if self.sdk_name.strip() != IBKR_ASYNC_PACKAGE_NAME:
            raise IBKREvidenceError(
                "Retained IBKR evidence must use ib_async."
            )
        if self.sdk_version.strip() != IBKR_ASYNC_VERSION_TARGET:
            raise IBKREvidenceError(
                "Retained IBKR evidence SDK version does not match "
                "the qualified runtime."
            )
        for field_name in (
            "real_provider_used",
            "controlled_probe_passed",
            "cleanup_passed",
        ):
            if type(getattr(self, field_name)) is not bool:
                raise IBKREvidenceError(
                    f"{field_name} must be a bool."
                )

        normalized_gates: dict[str, str] = {}
        for name, status in self.gates.items():
            clean_name = str(name).strip()
            clean_status = str(status).strip().upper()
            if not clean_name or not clean_status:
                raise IBKREvidenceError(
                    "Evidence gates must be non-empty."
                )
            normalized_gates[clean_name] = clean_status
        object.__setattr__(
            self,
            "gates",
            MappingProxyType(normalized_gates),
        )

        normalized_proofs: dict[
            BrokerCapability,
            Mapping[str, object],
        ] = {}
        for capability, proof in self.proofs.items():
            if not isinstance(capability, BrokerCapability):
                raise IBKREvidenceError(
                    "Evidence proof key must be BrokerCapability."
                )
            normalized_proofs[capability] = MappingProxyType(
                dict(proof)
            )
        object.__setattr__(
            self,
            "proofs",
            MappingProxyType(normalized_proofs),
        )

    @property
    def deterministic_qualified(self) -> bool:
        return self.gates.get("ci_quality_gate") == "PASS"

    def gate_passed(self, name: str) -> bool:
        return self.gates.get(name) == "PASS"

    def paper_proof_passes(
        self,
        capability: BrokerCapability,
    ) -> bool:
        """Return whether one capability has sufficient real PAPER proof."""

        if (
            not self.real_provider_used
            or not self.controlled_probe_passed
            or not self.cleanup_passed
        ):
            return False
        required_gates = _PAPER_GATE_REQUIREMENTS.get(capability)
        if required_gates is None:
            return False
        if not all(self.gate_passed(name) for name in required_gates):
            return False

        proof = self.proofs.get(capability)
        if proof is None:
            return False

        if capability is BrokerCapability.ACCOUNT_QUERY:
            return (
                _proof_bool(proof, "account_ready")
                and _proof_bool(proof, "managed_account_match")
                and _proof_bool(proof, "cash_present")
                and _proof_bool(proof, "equity_present")
                and _proof_bool(proof, "buying_power_present")
            )
        if capability is BrokerCapability.ORDER_QUERY:
            return (
                _proof_bool(proof, "query_observed")
                and _proof_bool(proof, "perm_id_present")
                and _proof_bool(proof, "status_observed")
            )
        if capability is BrokerCapability.MARKET_ORDER:
            return (
                _proof_bool(proof, "submitted")
                and _proof_int(proof, "submit_attempts") == 1
                and _proof_bool(proof, "filled")
                and _proof_bool(proof, "perm_id_present")
                and _proof_bool(proof, "exec_id_present")
            )
        if capability is BrokerCapability.LIMIT_ORDER:
            return (
                _proof_bool(proof, "submitted")
                and _proof_int(proof, "submit_attempts") == 1
                and _proof_bool(proof, "limit_price_present")
                and _proof_bool(proof, "market_rule_checked")
            )
        if capability is BrokerCapability.CANCEL_ORDER:
            return (
                _proof_bool(proof, "requested")
                and _proof_int(proof, "cancel_attempts") == 1
                and _proof_bool(proof, "terminal_cancelled")
            )
        if capability is BrokerCapability.POSITION_QUERY:
            return (
                _proof_bool(proof, "baseline_observed")
                and _proof_bool(proof, "baseline_restored")
            )
        if capability is BrokerCapability.BALANCE_QUERY:
            return (
                _proof_bool(proof, "cash_present")
                and _proof_bool(proof, "equity_present")
                and _proof_bool(proof, "buying_power_present")
            )
        if capability is BrokerCapability.CLIENT_ORDER_REFERENCE:
            return (
                _proof_bool(proof, "order_ref_present")
                and _proof_bool(proof, "round_trip_match")
                and _proof_int(proof, "submit_attempts") == 1
            )
        if capability is BrokerCapability.EXECUTION_FACTS:
            return (
                _proof_int(proof, "exec_details_count") > 0
                and _proof_bool(proof, "exec_id_present")
                and _proof_bool(proof, "perm_id_present")
                and _proof_bool(proof, "fill_quantity_positive")
            )
        if capability is BrokerCapability.RECONNECT_RECOVERY:
            return (
                _proof_bool(proof, "disconnect_observed")
                and _proof_bool(proof, "reconnect_observed")
                and _proof_bool(proof, "post_reconnect_account_query")
                and _proof_bool(proof, "economic_replay") is False
            )
        return False

    def proof_for(
        self,
        capability: BrokerCapability,
    ) -> Mapping[str, object]:
        proof = self.proofs.get(capability)
        if proof is None:
            raise IBKREvidenceError(
                f"No retained IBKR proof exists for {capability.value}."
            )
        return proof

    def common_evidence_payload(self) -> dict[str, object]:
        return {
            "source": self.provenance.to_dict(),
            "captured_at": self.captured_at.isoformat(),
            "sdk": {
                "name": self.sdk_name,
                "version": self.sdk_version,
            },
            "real_provider_used": self.real_provider_used,
            "controlled_probe_passed": self.controlled_probe_passed,
            "cleanup_passed": self.cleanup_passed,
        }

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": "1",
            "provider": IBKR_PROVIDER_KEY,
            "environment": "PAPER",
            "provenance": self.provenance.to_dict(),
            "captured_at": self.captured_at.isoformat(),
            "sdk": {
                "name": self.sdk_name,
                "version": self.sdk_version,
            },
            "real_provider_used": self.real_provider_used,
            "controlled_probe_passed": self.controlled_probe_passed,
            "cleanup_passed": self.cleanup_passed,
            "gates": dict(self.gates),
            "proofs": {
                capability.value: dict(proof)
                for capability, proof in sorted(
                    self.proofs.items(),
                    key=lambda item: item[0].value,
                )
            },
        }

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, object],
    ) -> IBKRPaperEvidenceBundle:
        if _text(payload.get("schema_version"), "schema_version") != "1":
            raise IBKREvidenceError(
                "Unsupported IBKR evidence schema version."
            )
        if _text(payload.get("provider"), "provider").lower() != (
            IBKR_PROVIDER_KEY
        ):
            raise IBKREvidenceError(
                "Evidence provider must be ibkr."
            )
        if _text(
            payload.get("environment"),
            "environment",
        ).upper() != "PAPER":
            raise IBKREvidenceError(
                "Evidence environment must be PAPER."
            )

        provenance = IBKRPaperEvidenceProvenance.from_dict(
            _mapping(payload.get("provenance"), "provenance")
        )
        sdk = _mapping(payload.get("sdk"), "sdk")
        gates = _mapping(payload.get("gates"), "gates")
        raw_proofs = _mapping(payload.get("proofs"), "proofs")
        proofs: dict[
            BrokerCapability,
            Mapping[str, object],
        ] = {}
        for capability_text, proof_payload in raw_proofs.items():
            try:
                capability = BrokerCapability(capability_text)
            except ValueError as exc:
                raise IBKREvidenceError(
                    "Unknown IBKR evidence capability "
                    f"{capability_text!r}."
                ) from exc
            proofs[capability] = _mapping(
                proof_payload,
                f"proofs.{capability_text}",
            )

        return cls(
            provenance=provenance,
            captured_at=_utc_datetime(
                payload.get("captured_at"),
                "captured_at",
            ),
            sdk_name=_text(sdk.get("name"), "sdk.name"),
            sdk_version=_text(sdk.get("version"), "sdk.version"),
            real_provider_used=_bool(
                payload.get("real_provider_used"),
                "real_provider_used",
            ),
            controlled_probe_passed=_bool(
                payload.get("controlled_probe_passed"),
                "controlled_probe_passed",
            ),
            cleanup_passed=_bool(
                payload.get("cleanup_passed"),
                "cleanup_passed",
            ),
            gates={
                str(name): str(status)
                for name, status in gates.items()
            },
            proofs=proofs,
        )

    @classmethod
    def from_probe_report(
        cls,
        payload: Mapping[str, object],
        *,
        provenance: IBKRPaperEvidenceProvenance,
    ) -> IBKRPaperEvidenceBundle:
        if _text(
            payload.get("environment"),
            "environment",
        ).upper() != "PAPER":
            raise IBKREvidenceError(
                "IBKR probe environment must be PAPER."
            )
        sdk = _mapping(payload.get("sdk"), "sdk")
        gates = _mapping(payload.get("gates"), "gates")
        raw_proofs = _mapping(payload.get("proofs"), "proofs")

        proofs: dict[
            BrokerCapability,
            Mapping[str, object],
        ] = {}
        for capability_text, proof_payload in raw_proofs.items():
            try:
                capability = BrokerCapability(capability_text)
            except ValueError as exc:
                raise IBKREvidenceError(
                    "Unknown IBKR probe capability "
                    f"{capability_text!r}."
                ) from exc
            proofs[capability] = _mapping(
                proof_payload,
                f"proofs.{capability_text}",
            )

        return cls(
            provenance=provenance,
            captured_at=_utc_datetime(
                payload.get("captured_at"),
                "captured_at",
            ),
            sdk_name=_text(sdk.get("name"), "sdk.name"),
            sdk_version=_text(sdk.get("version"), "sdk.version"),
            real_provider_used=_bool(
                payload.get("real_provider_used"),
                "real_provider_used",
            ),
            controlled_probe_passed=_bool(
                payload.get("controlled_probe_passed"),
                "controlled_probe_passed",
            ),
            cleanup_passed=_bool(
                payload.get("cleanup_passed"),
                "cleanup_passed",
            ),
            gates={
                str(name): str(status)
                for name, status in gates.items()
            },
            proofs=proofs,
        )


def _mapping(
    value: object,
    field_name: str,
) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise IBKREvidenceError(
            f"{field_name} must be a mapping."
        )
    return {
        str(key): item
        for key, item in value.items()
    }


def _text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise IBKREvidenceError(
            f"{field_name} must be non-empty text."
        )
    return value.strip()


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise IBKREvidenceError(
            "Optional text must be non-empty when set."
        )
    return value.strip()


def _bool(value: object, field_name: str) -> bool:
    if type(value) is not bool:
        raise IBKREvidenceError(
            f"{field_name} must be a bool."
        )
    return value


def _optional_positive_int(
    value: object,
    field_name: str,
) -> int | None:
    if value is None:
        return None
    if type(value) is not int or value <= 0:
        raise IBKREvidenceError(
            f"{field_name} must be a positive integer."
        )
    return value


def _proof_bool(
    proof: Mapping[str, object],
    field_name: str,
) -> bool:
    return proof.get(field_name) is True


def _proof_int(
    proof: Mapping[str, object],
    field_name: str,
) -> int:
    value = proof.get(field_name)
    return value if type(value) is int else -1


def _utc_datetime(
    value: object,
    field_name: str,
) -> datetime:
    text = _text(value, field_name)
    try:
        parsed = datetime.fromisoformat(
            text.replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise IBKREvidenceError(
            f"{field_name} must be ISO-8601 datetime."
        ) from exc
    if parsed.tzinfo is None:
        raise IBKREvidenceError(
            f"{field_name} must include a timezone."
        )
    return parsed.astimezone(UTC)


def _require_sha256(value: str, *, field_name: str) -> None:
    if len(value) != 64 or any(
        char not in "0123456789abcdefABCDEF"
        for char in value
    ):
        raise IBKREvidenceError(
            f"{field_name} must be a 64-character SHA-256 hex digest."
        )
