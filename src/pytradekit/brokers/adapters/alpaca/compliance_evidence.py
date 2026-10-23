"""Retained Alpaca PAPER evidence normalization for broker compliance."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from types import MappingProxyType

from pytradekit.brokers.compliance import BrokerCapability
from pytradekit.shared import require_utc_datetime

from .contract import ALPACA_PROVIDER_KEY, ALPACA_SDK_VERSION_TARGET


class AlpacaEvidenceError(ValueError):
    """Raised when retained Alpaca qualification evidence is malformed."""


@dataclass(frozen=True, slots=True)
class AlpacaPaperEvidenceProvenance:
    """Immutable source identity for retained real Alpaca PAPER evidence."""

    source_release: str
    qualified_commit: str
    artifact_name: str
    artifact_json_sha256: str
    workflow_run_id: int | None = None
    artifact_id: int | None = None
    artifact_zip_sha256: str | None = None
    deterministic_ci_run_id: int | None = None
    release_commit: str | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "source_release",
            "qualified_commit",
            "artifact_name",
            "artifact_json_sha256",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise AlpacaEvidenceError(f"{field_name} must be non-empty.")
            object.__setattr__(self, field_name, value.strip())

        _require_sha256(self.artifact_json_sha256, field_name="artifact_json_sha256")
        if self.artifact_zip_sha256 is not None:
            normalized = self.artifact_zip_sha256.strip()
            _require_sha256(normalized, field_name="artifact_zip_sha256")
            object.__setattr__(self, "artifact_zip_sha256", normalized)

        for field_name in ("workflow_run_id", "artifact_id", "deterministic_ci_run_id"):
            value = getattr(self, field_name)
            if value is not None and (type(value) is not int or value <= 0):
                raise AlpacaEvidenceError(f"{field_name} must be a positive integer.")

        if self.release_commit is not None:
            normalized_release = self.release_commit.strip()
            if not normalized_release:
                raise AlpacaEvidenceError("release_commit must be non-empty when set.")
            object.__setattr__(self, "release_commit", normalized_release)

    @property
    def source_ref(self) -> str:
        """Return a stable non-secret reference to the source qualification artifact."""

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
        return f"github-actions:{ALPACA_PROVIDER_KEY}:{run}:{artifact}"

    def to_dict(self) -> dict[str, object]:
        """Return JSON-safe provenance content."""

        return {
            "source_release": self.source_release,
            "qualified_commit": self.qualified_commit,
            "release_commit": self.release_commit,
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
    ) -> AlpacaPaperEvidenceProvenance:
        """Parse provenance from one normalized evidence record."""

        return cls(
            source_release=_text(payload.get("source_release"), "source_release"),
            qualified_commit=_text(payload.get("qualified_commit"), "qualified_commit"),
            release_commit=_optional_text(payload.get("release_commit")),
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
            artifact_name=_text(payload.get("artifact_name"), "artifact_name"),
            artifact_zip_sha256=_optional_text(payload.get("artifact_zip_sha256")),
            artifact_json_sha256=_text(
                payload.get("artifact_json_sha256"),
                "artifact_json_sha256",
            ),
        )


_PAPER_GATE_REQUIREMENTS: Mapping[BrokerCapability, tuple[str, ...]] = MappingProxyType(
    {
        BrokerCapability.ACCOUNT_QUERY: ("real_paper_runtime_start_restart",),
        BrokerCapability.ORDER_QUERY: ("real_paper_uncertain_recovery",),
        BrokerCapability.MARKET_ORDER: ("real_paper_market_limit_cancel",),
        BrokerCapability.LIMIT_ORDER: ("real_paper_market_limit_cancel",),
        BrokerCapability.CANCEL_ORDER: ("real_paper_market_limit_cancel",),
        BrokerCapability.POSITION_QUERY: (
            "real_paper_runtime_start_restart",
            "real_paper_cleanup",
        ),
        BrokerCapability.BALANCE_QUERY: ("real_paper_runtime_start_restart",),
        BrokerCapability.CLIENT_ORDER_REFERENCE: ("real_paper_uncertain_recovery",),
        BrokerCapability.EXECUTION_FACTS: ("real_paper_trade_updates",),
        BrokerCapability.RECONNECT_RECOVERY: ("real_paper_runtime_start_restart",),
        BrokerCapability.LATEST_QUOTE: ("real_paper_market_limit_cancel",),
    }
)


@dataclass(frozen=True, slots=True)
class AlpacaPaperEvidenceBundle:
    """Normalized capability evidence extracted from a real PAPER qualification."""

    provenance: AlpacaPaperEvidenceProvenance
    captured_at: datetime
    sdk_name: str
    sdk_version: str
    release_ready: bool
    controlled_probe_passed: bool
    gates: Mapping[str, str]
    proofs: Mapping[BrokerCapability, Mapping[str, object]]

    def __post_init__(self) -> None:
        require_utc_datetime(
            self.captured_at,
            field_name="AlpacaPaperEvidenceBundle captured_at",
        )
        if self.sdk_name.strip() != "alpaca-py":
            raise AlpacaEvidenceError("Retained Alpaca evidence must use alpaca-py.")
        if self.sdk_version.strip() != ALPACA_SDK_VERSION_TARGET:
            raise AlpacaEvidenceError(
                "Retained Alpaca evidence SDK version does not match the frozen adapter."
            )
        if type(self.release_ready) is not bool:
            raise AlpacaEvidenceError("release_ready must be a bool.")
        if type(self.controlled_probe_passed) is not bool:
            raise AlpacaEvidenceError("controlled_probe_passed must be a bool.")

        normalized_gates: dict[str, str] = {}
        for name, status in self.gates.items():
            clean_name = str(name).strip()
            clean_status = str(status).strip().upper()
            if not clean_name or not clean_status:
                raise AlpacaEvidenceError("Evidence gates must be non-empty.")
            normalized_gates[clean_name] = clean_status
        object.__setattr__(self, "gates", MappingProxyType(normalized_gates))

        normalized_proofs: dict[BrokerCapability, Mapping[str, object]] = {}
        for capability, proof in self.proofs.items():
            if not isinstance(capability, BrokerCapability):
                raise AlpacaEvidenceError("Evidence proof key must be BrokerCapability.")
            normalized_proofs[capability] = MappingProxyType(dict(proof))
        object.__setattr__(self, "proofs", MappingProxyType(normalized_proofs))

    @property
    def deterministic_qualified(self) -> bool:
        """Return whether the retained deterministic CI gate passed."""

        return self.gates.get("ci_quality_gate") == "PASS"

    def gate_passed(self, name: str) -> bool:
        """Return whether one named retained qualification gate passed."""

        return self.gates.get(name) == "PASS"

    def paper_proof_passes(self, capability: BrokerCapability) -> bool:
        """Validate real PAPER proof for one capability."""

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
                _proof_text(proof, "status") == "ACTIVE"
                and _proof_bool(proof, "account_blocked") is False
                and _proof_bool(proof, "trading_blocked") is False
            )
        if capability is BrokerCapability.ORDER_QUERY:
            return (
                _proof_int(proof, "recovery_queries") >= 1
                and _proof_bool(proof, "recovered_order_id_present")
            )
        if capability is BrokerCapability.MARKET_ORDER:
            return (
                _proof_text(proof, "type") == "market"
                and _proof_text(proof, "status") == "filled"
                and _proof_bool(proof, "filled_quantity_positive")
                and _proof_int(proof, "submit_attempts") == 1
            )
        if capability is BrokerCapability.LIMIT_ORDER:
            return (
                _proof_text(proof, "type") == "limit"
                and _proof_bool(proof, "limit_price_present")
                and _proof_int(proof, "submit_attempts") == 1
            )
        if capability is BrokerCapability.CANCEL_ORDER:
            return (
                _proof_bool(proof, "requested")
                and _proof_text(proof, "final_status") == "canceled"
                and _proof_int(proof, "cancel_attempts") == 1
            )
        if capability is BrokerCapability.POSITION_QUERY:
            return _proof_bool(proof, "baseline_restored")
        if capability is BrokerCapability.BALANCE_QUERY:
            return (
                _proof_bool(proof, "cash_present")
                and _proof_text(proof, "currency") == "USD"
            )
        if capability is BrokerCapability.CLIENT_ORDER_REFERENCE:
            return (
                _proof_bool(proof, "client_order_id_present")
                and _proof_bool(proof, "resubmitted") is False
                and _proof_int(proof, "submit_attempts") == 1
            )
        if capability is BrokerCapability.EXECUTION_FACTS:
            return (
                _proof_int(proof, "event_count") > 0
                and _proof_int(proof, "fill_event_count") > 0
                and _proof_bool(proof, "fill_execution_ids_present")
            )
        if capability is BrokerCapability.RECONNECT_RECOVERY:
            return (
                _proof_int(proof, "runtime_cycles") >= 2
                and _proof_bool(proof, "all_trading_ready")
                and _proof_bool(proof, "all_shutdown_drained")
                and _proof_bool(proof, "all_readiness_checks_passed")
            )
        if capability is BrokerCapability.LATEST_QUOTE:
            return (
                _proof_text(proof, "feed") == "iex"
                and _proof_bool(proof, "bid_present")
                and _proof_bool(proof, "ask_present")
                and _proof_bool(proof, "market_open")
            )
        return False

    def proof_for(self, capability: BrokerCapability) -> Mapping[str, object]:
        """Return one sanitized normalized capability proof."""

        proof = self.proofs.get(capability)
        if proof is None:
            raise AlpacaEvidenceError(
                f"No retained Alpaca proof exists for {capability.value}."
            )
        return proof

    def common_evidence_payload(self) -> dict[str, object]:
        """Return provenance fields shared by every generated compliance evidence item."""

        return {
            "source": self.provenance.to_dict(),
            "captured_at": self.captured_at.isoformat(),
            "sdk": {"name": self.sdk_name, "version": self.sdk_version},
            "release_ready": self.release_ready,
            "controlled_probe_passed": self.controlled_probe_passed,
        }

    def to_dict(self) -> dict[str, object]:
        """Return the normalized retained evidence record."""

        return {
            "schema_version": "1",
            "provider": ALPACA_PROVIDER_KEY,
            "environment": "PAPER",
            "provenance": self.provenance.to_dict(),
            "captured_at": self.captured_at.isoformat(),
            "sdk": {"name": self.sdk_name, "version": self.sdk_version},
            "release_ready": self.release_ready,
            "controlled_probe_passed": self.controlled_probe_passed,
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
    def from_dict(cls, payload: Mapping[str, object]) -> AlpacaPaperEvidenceBundle:
        """Parse one normalized retained evidence record."""

        if _text(payload.get("schema_version"), "schema_version") != "1":
            raise AlpacaEvidenceError("Unsupported Alpaca evidence schema version.")
        if _text(payload.get("provider"), "provider").lower() != ALPACA_PROVIDER_KEY:
            raise AlpacaEvidenceError("Evidence provider must be alpaca.")
        if _text(payload.get("environment"), "environment").upper() != "PAPER":
            raise AlpacaEvidenceError("Evidence environment must be PAPER.")

        provenance = AlpacaPaperEvidenceProvenance.from_dict(
            _mapping(payload.get("provenance"), "provenance")
        )
        sdk = _mapping(payload.get("sdk"), "sdk")
        gates = _mapping(payload.get("gates"), "gates")
        raw_proofs = _mapping(payload.get("proofs"), "proofs")

        proofs: dict[BrokerCapability, Mapping[str, object]] = {}
        for capability_text, proof_payload in raw_proofs.items():
            try:
                capability = BrokerCapability(capability_text)
            except ValueError as exc:
                raise AlpacaEvidenceError(
                    f"Unknown Alpaca evidence capability {capability_text!r}."
                ) from exc
            proofs[capability] = _mapping(
                proof_payload,
                f"proofs.{capability_text}",
            )

        return cls(
            provenance=provenance,
            captured_at=_utc_datetime(payload.get("captured_at"), "captured_at"),
            sdk_name=_text(sdk.get("name"), "sdk.name"),
            sdk_version=_text(sdk.get("version"), "sdk.version"),
            release_ready=_bool(payload.get("release_ready"), "release_ready"),
            controlled_probe_passed=_bool(
                payload.get("controlled_probe_passed"),
                "controlled_probe_passed",
            ),
            gates={str(name): str(status) for name, status in gates.items()},
            proofs=proofs,
        )

    @classmethod
    def from_v050_report(
        cls,
        payload: Mapping[str, object],
        *,
        provenance: AlpacaPaperEvidenceProvenance,
    ) -> AlpacaPaperEvidenceBundle:
        """Normalize the retained v0.5 real PAPER report into 0.8 evidence."""

        if _text(payload.get("environment"), "environment").upper() != "PAPER":
            raise AlpacaEvidenceError("v0.5 evidence environment must be PAPER.")

        release_gate = _mapping(payload.get("release_gate"), "release_gate")
        raw_gates = _sequence(release_gate.get("gates"), "release_gate.gates")
        gates: dict[str, str] = {}
        for index, raw_gate in enumerate(raw_gates):
            gate = _mapping(raw_gate, f"release_gate.gates[{index}]")
            name = _text(gate.get("name"), f"release_gate.gates[{index}].name")
            status = _text(
                gate.get("status"),
                f"release_gate.gates[{index}].status",
            ).upper()
            gates[name] = status

        controlled = _mapping(
            payload.get("controlled_order_probe"),
            "controlled_order_probe",
        )
        sdk_target = _text(
            controlled.get("sdk_version_target"),
            "controlled_order_probe.sdk_version_target",
        )
        sdk_name, sdk_version = _parse_sdk_target(sdk_target)
        runtime_runs = _sequence(payload.get("runtime_runs"), "runtime_runs")

        return cls(
            provenance=provenance,
            captured_at=_utc_datetime(
                controlled.get("generated_at"),
                "controlled_order_probe.generated_at",
            ),
            sdk_name=sdk_name,
            sdk_version=sdk_version,
            release_ready=_bool(
                release_gate.get("release_ready"),
                "release_gate.release_ready",
            ),
            controlled_probe_passed=(
                _text(controlled.get("result"), "controlled_order_probe.result").upper()
                == "PASS"
            ),
            gates=gates,
            proofs=_build_capability_proofs(controlled, runtime_runs),
        )


def _build_capability_proofs(
    controlled: Mapping[str, object],
    runtime_runs: Sequence[object],
) -> Mapping[BrokerCapability, Mapping[str, object]]:
    account = _mapping(controlled.get("account"), "controlled_order_probe.account")
    market = _mapping(
        controlled.get("market_order"),
        "controlled_order_probe.market_order",
    )
    limit_order = _mapping(
        controlled.get("limit_order"),
        "controlled_order_probe.limit_order",
    )
    cancel = _mapping(controlled.get("cancel"), "controlled_order_probe.cancel")
    recovery = _mapping(
        controlled.get("uncertain_recovery"),
        "controlled_order_probe.uncertain_recovery",
    )
    preflight = _mapping(
        controlled.get("preflight"),
        "controlled_order_probe.preflight",
    )
    stream = _mapping(controlled.get("stream"), "controlled_order_probe.stream")
    transport = _mapping(
        controlled.get("transport_safety"),
        "controlled_order_probe.transport_safety",
    )
    updates = _sequence(
        controlled.get("trade_updates"),
        "controlled_order_probe.trade_updates",
    )

    fill_updates: list[Mapping[str, object]] = []
    for index, update_payload in enumerate(updates):
        update = _mapping(
            update_payload,
            f"controlled_order_probe.trade_updates[{index}]",
        )
        if _optional_text(update.get("event")) == "fill":
            fill_updates.append(update)

    normalized_runtime_runs = tuple(
        _mapping(run, f"runtime_runs[{index}]")
        for index, run in enumerate(runtime_runs)
    )
    all_readiness_checks_passed = True
    for index, run in enumerate(normalized_runtime_runs):
        readiness = _mapping(run.get("readiness"), f"runtime_runs[{index}].readiness")
        checks = _sequence(
            readiness.get("checks"),
            f"runtime_runs[{index}].readiness.checks",
        )
        if not checks:
            all_readiness_checks_passed = False
            continue
        for check_index, check_payload in enumerate(checks):
            check = _mapping(
                check_payload,
                f"runtime_runs[{index}].readiness.checks[{check_index}]",
            )
            if _optional_text(check.get("status")) != "PASS":
                all_readiness_checks_passed = False

    baseline = _text(
        controlled.get("baseline_position_qty"),
        "controlled_order_probe.baseline_position_qty",
    )
    final = _text(
        controlled.get("final_position_qty"),
        "controlled_order_probe.final_position_qty",
    )

    proofs: dict[BrokerCapability, Mapping[str, object]] = {
        BrokerCapability.ACCOUNT_QUERY: {
            "status": _optional_text(account.get("status")),
            "account_blocked": _optional_bool(account.get("account_blocked")),
            "trading_blocked": _optional_bool(account.get("trading_blocked")),
        },
        BrokerCapability.ORDER_QUERY: {
            "recovery_queries": _optional_int(recovery.get("recovery_queries")),
            "recovered_order_id_present": bool(
                _optional_text(recovery.get("recovered_order_id"))
            ),
            "recovered_status": _optional_text(recovery.get("recovered_status")),
        },
        BrokerCapability.MARKET_ORDER: {
            "type": _optional_text(market.get("type")),
            "status": _optional_text(market.get("status")),
            "filled_quantity_positive": _positive_decimal(market.get("filled_qty")),
            "submit_attempts": _optional_int(transport.get("market_submit_attempts")),
        },
        BrokerCapability.LIMIT_ORDER: {
            "type": _optional_text(limit_order.get("type")),
            "status": _optional_text(limit_order.get("status")),
            "limit_price_present": bool(_optional_text(limit_order.get("limit_price"))),
            "submit_attempts": _optional_int(transport.get("limit_submit_attempts")),
        },
        BrokerCapability.CANCEL_ORDER: {
            "requested": _optional_bool(cancel.get("requested")),
            "transport_result": _optional_text(cancel.get("transport_result")),
            "final_status": _optional_text(limit_order.get("status")),
            "cancel_attempts": _optional_int(transport.get("cancel_attempts")),
        },
        BrokerCapability.POSITION_QUERY: {
            "baseline_position_qty": baseline,
            "final_position_qty": final,
            "baseline_restored": baseline == final,
        },
        BrokerCapability.BALANCE_QUERY: {
            "cash_present": bool(_optional_text(account.get("cash"))),
            "currency": _optional_text(account.get("currency")),
        },
        BrokerCapability.CLIENT_ORDER_REFERENCE: {
            "client_order_id_present": bool(
                _optional_text(recovery.get("client_order_id"))
            ),
            "recovery_queries": _optional_int(recovery.get("recovery_queries")),
            "resubmitted": _optional_bool(recovery.get("resubmitted")),
            "submit_attempts": _optional_int(recovery.get("submit_attempts")),
        },
        BrokerCapability.EXECUTION_FACTS: {
            "event_count": _optional_int(stream.get("event_count")),
            "fill_event_count": len(fill_updates),
            "fill_execution_ids_present": bool(fill_updates)
            and all(
                bool(_optional_text(update.get("execution_id")))
                for update in fill_updates
            ),
        },
        BrokerCapability.RECONNECT_RECOVERY: {
            "runtime_cycles": len(normalized_runtime_runs),
            "all_trading_ready": bool(normalized_runtime_runs)
            and all(_optional_bool(run.get("trading_ready")) for run in normalized_runtime_runs),
            "all_shutdown_drained": bool(normalized_runtime_runs)
            and all(
                _optional_bool(run.get("shutdown_drained"))
                for run in normalized_runtime_runs
            ),
            "all_readiness_checks_passed": all_readiness_checks_passed,
        },
        BrokerCapability.LATEST_QUOTE: {
            "feed": _optional_text(preflight.get("feed")),
            "bid_present": bool(_optional_text(preflight.get("quote_bid"))),
            "ask_present": bool(_optional_text(preflight.get("quote_ask"))),
            "market_open": _optional_bool(preflight.get("market_open")),
        },
    }
    return MappingProxyType(proofs)


def _mapping(value: object, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise AlpacaEvidenceError(f"{field_name} must be an object.")
    result: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise AlpacaEvidenceError(f"{field_name} keys must be strings.")
        result[key] = item
    return MappingProxyType(result)


def _sequence(value: object, field_name: str) -> tuple[object, ...]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
        raise AlpacaEvidenceError(f"{field_name} must be an array.")
    return tuple(value)


def _text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AlpacaEvidenceError(f"{field_name} must be non-empty text.")
    return value.strip()


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return str(value)
    normalized = value.strip()
    return normalized or None


def _bool(value: object, field_name: str) -> bool:
    if type(value) is not bool:
        raise AlpacaEvidenceError(f"{field_name} must be a bool.")
    return value


def _optional_bool(value: object) -> bool:
    return value if type(value) is bool else False


def _optional_int(value: object) -> int:
    return value if type(value) is int else 0


def _optional_positive_int(value: object, field_name: str) -> int | None:
    if value is None:
        return None
    if type(value) is not int or value <= 0:
        raise AlpacaEvidenceError(f"{field_name} must be a positive integer.")
    return value


def _utc_datetime(value: object, field_name: str) -> datetime:
    text = _text(value, field_name)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AlpacaEvidenceError(f"{field_name} must be ISO-8601 datetime text.") from exc
    return require_utc_datetime(parsed, field_name=field_name)


def _parse_sdk_target(value: str) -> tuple[str, str]:
    parts = value.split("==", maxsplit=1)
    if len(parts) != 2 or not all(part.strip() for part in parts):
        raise AlpacaEvidenceError("sdk_version_target must use '<name>==<version>'.")
    return parts[0].strip(), parts[1].strip()


def _positive_decimal(value: object) -> bool:
    text = _optional_text(value)
    if text is None:
        return False
    try:
        return Decimal(text) > 0
    except InvalidOperation:
        return False


def _proof_bool(proof: Mapping[str, object], name: str) -> bool:
    return _optional_bool(proof.get(name))


def _proof_int(proof: Mapping[str, object], name: str) -> int:
    return _optional_int(proof.get(name))


def _proof_text(proof: Mapping[str, object], name: str) -> str | None:
    return _optional_text(proof.get(name))


def _require_sha256(value: str, *, field_name: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise AlpacaEvidenceError(f"{field_name} must be a lowercase SHA-256 digest.")
