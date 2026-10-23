"""Retained IBKR PAPER evidence normalization for broker compliance."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from json import dumps
from types import MappingProxyType

from pytradekit.brokers.compliance import BrokerCapability
from pytradekit.shared import require_utc_datetime

from .discovery import IBKR_PROVIDER_KEY
from .runtime import IBKR_ASYNC_PACKAGE_NAME, IBKR_ASYNC_VERSION_TARGET

IBKR_PAPER_EVIDENCE_SCHEMA_VERSION = "1"


class IBKREvidenceError(ValueError):
    """Raised when retained IBKR PAPER evidence is malformed or overclaims proof."""


@dataclass(frozen=True, slots=True)
class IBKRPaperEvidenceProvenance:
    """Immutable provenance for one retained real IBKR PAPER artifact."""

    qualified_commit: str
    artifact_name: str
    artifact_json_sha256: str
    source_ref: str
    workflow_run_id: int | None = None
    deterministic_ci_run_id: int | None = None
    artifact_id: int | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "qualified_commit",
            "artifact_name",
            "source_ref",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise IBKREvidenceError(f"{field_name} must be non-empty.")
            object.__setattr__(self, field_name, value.strip())

        normalized_hash = self.artifact_json_sha256.strip().lower()
        _require_sha256(normalized_hash, field_name="artifact_json_sha256")
        object.__setattr__(self, "artifact_json_sha256", normalized_hash)

        for field_name in (
            "workflow_run_id",
            "deterministic_ci_run_id",
            "artifact_id",
        ):
            value = getattr(self, field_name)
            if value is not None and (type(value) is not int or value <= 0):
                raise IBKREvidenceError(
                    f"{field_name} must be a positive integer or None."
                )

    def to_dict(self) -> dict[str, object]:
        return {
            "qualified_commit": self.qualified_commit,
            "artifact_name": self.artifact_name,
            "artifact_json_sha256": self.artifact_json_sha256,
            "source_ref": self.source_ref,
            "workflow_run_id": self.workflow_run_id,
            "deterministic_ci_run_id": self.deterministic_ci_run_id,
            "artifact_id": self.artifact_id,
        }

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, object],
    ) -> IBKRPaperEvidenceProvenance:
        return cls(
            qualified_commit=_text(
                payload.get("qualified_commit"),
                "qualified_commit",
            ),
            artifact_name=_text(payload.get("artifact_name"), "artifact_name"),
            artifact_json_sha256=_text(
                payload.get("artifact_json_sha256"),
                "artifact_json_sha256",
            ),
            source_ref=_text(payload.get("source_ref"), "source_ref"),
            workflow_run_id=_optional_positive_int(
                payload.get("workflow_run_id"),
                "workflow_run_id",
            ),
            deterministic_ci_run_id=_optional_positive_int(
                payload.get("deterministic_ci_run_id"),
                "deterministic_ci_run_id",
            ),
            artifact_id=_optional_positive_int(
                payload.get("artifact_id"),
                "artifact_id",
            ),
        )


_PAPER_GATE_REQUIREMENTS: Mapping[
    BrokerCapability,
    tuple[str, ...],
] = MappingProxyType(
    {
        BrokerCapability.ACCOUNT_QUERY: (
            "paper_startup",
            "paper_account_snapshot",
        ),
        BrokerCapability.ORDER_QUERY: (
            "paper_order_callbacks",
        ),
        BrokerCapability.MARKET_ORDER: (
            "paper_market_order",
            "paper_execution_details",
        ),
        BrokerCapability.LIMIT_ORDER: (
            "paper_limit_order",
        ),
        BrokerCapability.CANCEL_ORDER: (
            "paper_cancel_order",
        ),
        BrokerCapability.PARTIAL_FILL: (
            "paper_partial_fill",
        ),
        BrokerCapability.POSITION_QUERY: (
            "paper_account_snapshot",
            "paper_cleanup",
        ),
        BrokerCapability.BALANCE_QUERY: (
            "paper_account_snapshot",
        ),
        BrokerCapability.CLIENT_ORDER_REFERENCE: (
            "paper_order_identity",
        ),
        BrokerCapability.EXECUTION_FACTS: (
            "paper_execution_details",
        ),
        BrokerCapability.RECONNECT_RECOVERY: (
            "paper_reconnect_recovery",
        ),
    }
)


@dataclass(frozen=True, slots=True)
class IBKRPaperEvidenceBundle:
    """Sanitized retained evidence from one real IBKR PAPER qualification run."""

    provenance: IBKRPaperEvidenceProvenance
    captured_at: datetime
    sdk_name: str
    sdk_version: str
    account_mask: str
    release_ready: bool
    controlled_probe_passed: bool
    gates: Mapping[str, str]
    c3_capabilities: tuple[BrokerCapability, ...]
    proofs: Mapping[BrokerCapability, Mapping[str, object]]

    def __post_init__(self) -> None:
        require_utc_datetime(
            self.captured_at,
            field_name="IBKRPaperEvidenceBundle captured_at",
        )
        if self.sdk_name.strip() != IBKR_ASYNC_PACKAGE_NAME:
            raise IBKREvidenceError(
                "Retained IBKR evidence must use the frozen ib_async package."
            )
        if self.sdk_version.strip() != IBKR_ASYNC_VERSION_TARGET:
            raise IBKREvidenceError(
                "Retained IBKR evidence SDK version does not match the frozen runtime."
            )
        masked = self.account_mask.strip()
        if not masked or not masked.startswith("***"):
            raise IBKREvidenceError(
                "account_mask must contain only a sanitized masked account identity."
            )
        object.__setattr__(self, "account_mask", masked)

        if type(self.release_ready) is not bool:
            raise IBKREvidenceError("release_ready must be a bool.")
        if type(self.controlled_probe_passed) is not bool:
            raise IBKREvidenceError("controlled_probe_passed must be a bool.")

        normalized_gates: dict[str, str] = {}
        for name, status in self.gates.items():
            clean_name = str(name).strip()
            clean_status = str(status).strip().upper()
            if not clean_name or clean_status not in {
                "PASS",
                "FAIL",
                "BLOCKED",
                "PENDING",
            }:
                raise IBKREvidenceError(
                    "Evidence gates must use PASS, FAIL, BLOCKED, or PENDING."
                )
            normalized_gates[clean_name] = clean_status
        object.__setattr__(
            self,
            "gates",
            MappingProxyType(normalized_gates),
        )

        if any(
            not isinstance(capability, BrokerCapability)
            for capability in self.c3_capabilities
        ):
            raise IBKREvidenceError(
                "c3_capabilities must contain BrokerCapability values."
            )
        if len(set(self.c3_capabilities)) != len(self.c3_capabilities):
            raise IBKREvidenceError("c3_capabilities must be unique.")
        if self.c3_capabilities and (
            self.provenance.workflow_run_id is None
            or self.provenance.deterministic_ci_run_id is None
            or self.provenance.artifact_id is None
        ):
            raise IBKREvidenceError(
                "C3 evidence requires a retained provider artifact, PAPER workflow "
                "run ID, and deterministic CI run ID."
            )

        normalized_proofs: dict[
            BrokerCapability,
            Mapping[str, object],
        ] = {}
        for capability, proof in self.proofs.items():
            if not isinstance(capability, BrokerCapability):
                raise IBKREvidenceError(
                    "Evidence proof keys must be BrokerCapability values."
                )
            normalized_proofs[capability] = MappingProxyType(dict(proof))
        object.__setattr__(
            self,
            "proofs",
            MappingProxyType(normalized_proofs),
        )

        for capability in self.c3_capabilities:
            if not self.paper_proof_passes(capability):
                raise IBKREvidenceError(
                    "IBKR evidence claims C3 for "
                    f"{capability.value} without sufficient retained proof."
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
        if not self.release_ready or not self.controlled_probe_passed:
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
                _proof_bool(proof, "account_verified")
                and _proof_bool(proof, "account_ready")
                and _proof_bool(proof, "restrictions_explicit")
            )
        if capability is BrokerCapability.ORDER_QUERY:
            return (
                _proof_bool(proof, "query_observed")
                and _proof_bool(proof, "perm_id_present")
                and _proof_bool(proof, "order_status_observed")
            )
        if capability is BrokerCapability.MARKET_ORDER:
            return (
                _proof_int(proof, "submit_attempts") == 1
                and _proof_bool(proof, "perm_id_present")
                and _proof_text(proof, "terminal_status") == "Filled"
                and _proof_bool(proof, "exec_id_present")
            )
        if capability is BrokerCapability.LIMIT_ORDER:
            return (
                _proof_int(proof, "submit_attempts") == 1
                and _proof_bool(proof, "accepted")
                and _proof_bool(proof, "limit_price_present")
                and _proof_bool(proof, "price_rule_validated")
            )
        if capability is BrokerCapability.CANCEL_ORDER:
            return (
                _proof_int(proof, "cancel_attempts") == 1
                and _proof_bool(proof, "requested")
                and _proof_text(proof, "final_status")
                in {"Cancelled", "ApiCancelled"}
            )
        if capability is BrokerCapability.PARTIAL_FILL:
            return (
                _proof_bool(proof, "partial_fill_observed")
                and _proof_int(proof, "partial_exec_count") >= 1
                and _proof_bool(proof, "distinct_exec_ids")
            )
        if capability is BrokerCapability.POSITION_QUERY:
            return (
                _proof_bool(proof, "position_query_observed")
                and _proof_bool(proof, "baseline_restored")
            )
        if capability is BrokerCapability.BALANCE_QUERY:
            return (
                _proof_bool(proof, "cash_present")
                and _proof_bool(proof, "equity_present")
                and _proof_text(proof, "currency") == "USD"
            )
        if capability is BrokerCapability.CLIENT_ORDER_REFERENCE:
            return (
                _proof_bool(proof, "order_ref_round_trip")
                and _proof_int(proof, "submit_attempts") == 1
                and _proof_bool(proof, "resubmitted") is False
            )
        if capability is BrokerCapability.EXECUTION_FACTS:
            return (
                _proof_int(proof, "exec_details_count") >= 1
                and _proof_bool(proof, "exec_ids_present")
                and _proof_bool(proof, "fill_mapping_observed")
            )
        if capability is BrokerCapability.RECONNECT_RECOVERY:
            return (
                _proof_int(proof, "reconnect_cycles") >= 1
                and _proof_bool(proof, "fresh_reconciliation")
                and _proof_bool(proof, "no_economic_replay")
                and _proof_bool(proof, "write_readmission_observed")
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
            "account": self.account_mask,
            "release_ready": self.release_ready,
            "controlled_probe_passed": self.controlled_probe_passed,
        }

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": IBKR_PAPER_EVIDENCE_SCHEMA_VERSION,
            "provider": IBKR_PROVIDER_KEY,
            "environment": "PAPER",
            "provenance": self.provenance.to_dict(),
            "captured_at": self.captured_at.isoformat(),
            "sdk": {
                "name": self.sdk_name,
                "version": self.sdk_version,
            },
            "account": self.account_mask,
            "release_ready": self.release_ready,
            "controlled_probe_passed": self.controlled_probe_passed,
            "gates": dict(self.gates),
            "c3_capabilities": [
                capability.value
                for capability in self.c3_capabilities
            ],
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
        verify_ibkr_evidence_integrity(payload)
        if _text(payload.get("schema_version"), "schema_version") != (
            IBKR_PAPER_EVIDENCE_SCHEMA_VERSION
        ):
            raise IBKREvidenceError(
                "Unsupported IBKR PAPER evidence schema version."
            )
        if _text(payload.get("provider"), "provider").lower() != (
            IBKR_PROVIDER_KEY
        ):
            raise IBKREvidenceError("Evidence provider must be ibkr.")
        if _text(payload.get("environment"), "environment").upper() != "PAPER":
            raise IBKREvidenceError("Evidence environment must be PAPER.")

        provenance = IBKRPaperEvidenceProvenance.from_dict(
            _mapping(payload.get("provenance"), "provenance")
        )
        sdk = _mapping(payload.get("sdk"), "sdk")
        gates = _mapping(payload.get("gates"), "gates")
        raw_proofs = _mapping(payload.get("proofs"), "proofs")
        raw_c3 = payload.get("c3_capabilities")
        if not isinstance(raw_c3, list | tuple):
            raise IBKREvidenceError(
                "c3_capabilities must be a list."
            )

        c3_capabilities: list[BrokerCapability] = []
        for raw in raw_c3:
            if not isinstance(raw, str):
                raise IBKREvidenceError(
                    "c3_capabilities values must be strings."
                )
            try:
                c3_capabilities.append(BrokerCapability(raw))
            except ValueError as exc:
                raise IBKREvidenceError(
                    f"Unknown IBKR C3 capability {raw!r}."
                ) from exc

        proofs: dict[
            BrokerCapability,
            Mapping[str, object],
        ] = {}
        for capability_text, proof_payload in raw_proofs.items():
            try:
                capability = BrokerCapability(str(capability_text))
            except ValueError as exc:
                raise IBKREvidenceError(
                    f"Unknown IBKR evidence capability {capability_text!r}."
                ) from exc
            proofs[capability] = _mapping(
                proof_payload,
                f"proofs.{capability.value}",
            )

        return cls(
            provenance=provenance,
            captured_at=_utc_datetime(
                payload.get("captured_at"),
                "captured_at",
            ),
            sdk_name=_text(sdk.get("name"), "sdk.name"),
            sdk_version=_text(sdk.get("version"), "sdk.version"),
            account_mask=_text(payload.get("account"), "account"),
            release_ready=_bool(
                payload.get("release_ready"),
                "release_ready",
            ),
            controlled_probe_passed=_bool(
                payload.get("controlled_probe_passed"),
                "controlled_probe_passed",
            ),
            gates={
                str(name): str(status)
                for name, status in gates.items()
            },
            c3_capabilities=tuple(c3_capabilities),
            proofs=proofs,
        )


def canonical_ibkr_evidence_sha256(
    payload: Mapping[str, object],
) -> str:
    """Return stable SHA-256 excluding only the self-referential hash field."""

    normalized = _integrity_payload(payload)
    encoded = dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def verify_ibkr_evidence_integrity(
    payload: Mapping[str, object],
) -> None:
    """Reject retained PAPER evidence whose canonical artifact hash changed."""

    provenance = _mapping(payload.get("provenance"), "provenance")
    expected = _text(
        provenance.get("artifact_json_sha256"),
        "provenance.artifact_json_sha256",
    ).lower()
    _require_sha256(
        expected,
        field_name="provenance.artifact_json_sha256",
    )
    observed = canonical_ibkr_evidence_sha256(payload)
    if observed != expected:
        raise IBKREvidenceError(
            "Retained IBKR PAPER evidence SHA-256 does not match its content."
        )


def _integrity_payload(
    payload: Mapping[str, object],
) -> dict[str, object]:
    copied = _copy_json_value(payload)
    if not isinstance(copied, dict):
        raise IBKREvidenceError(
            "IBKR evidence payload must normalize to a JSON object."
        )
    raw_provenance = copied.get("provenance")
    if raw_provenance is None:
        return copied
    if not isinstance(raw_provenance, dict):
        raise IBKREvidenceError(
            "provenance must be a mapping."
        )
    provenance = dict(raw_provenance)
    provenance.pop("artifact_json_sha256", None)
    copied["provenance"] = provenance
    return copied


def _copy_json_value(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            str(key): _copy_json_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list | tuple):
        return [_copy_json_value(item) for item in value]
    return value


def _mapping(value: object, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise IBKREvidenceError(f"{field_name} must be a mapping.")
    return {str(key): item for key, item in value.items()}


def _text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise IBKREvidenceError(f"{field_name} must be non-empty text.")
    return value.strip()


def _bool(value: object, field_name: str) -> bool:
    if type(value) is not bool:
        raise IBKREvidenceError(f"{field_name} must be a bool.")
    return value


def _optional_positive_int(
    value: object,
    field_name: str,
) -> int | None:
    if value is None:
        return None
    if type(value) is not int or value <= 0:
        raise IBKREvidenceError(
            f"{field_name} must be a positive integer or None."
        )
    return value


def _utc_datetime(value: object, field_name: str) -> datetime:
    text = _text(value, field_name)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise IBKREvidenceError(
            f"{field_name} must be an ISO-8601 datetime."
        ) from exc
    if parsed.tzinfo is None:
        raise IBKREvidenceError(
            f"{field_name} must include a timezone."
        )
    return parsed.astimezone(UTC)


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


def _proof_text(
    proof: Mapping[str, object],
    field_name: str,
) -> str:
    value = proof.get(field_name)
    return value if isinstance(value, str) else ""


def _require_sha256(value: str, *, field_name: str) -> None:
    if len(value) != 64:
        raise IBKREvidenceError(
            f"{field_name} must be a 64-character SHA-256 hex digest."
        )
    try:
        int(value, 16)
    except ValueError as exc:
        raise IBKREvidenceError(
            f"{field_name} must contain hexadecimal characters only."
        ) from exc
