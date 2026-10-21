"""Immutable reproducibility manifest for one backtest."""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256

from pytradekit.shared import DomainValidationError, require_utc_datetime


def deterministic_config_hash(config: Mapping[str, object]) -> str:
    """Return a stable hash for JSON-compatible configuration values."""
    payload = json.dumps(config, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class RunManifest:
    """Full semantic context required to reproduce one run."""

    pytradekit_version: str
    strategy_id: str
    strategy_version: str
    strategy_config_hash: str
    dataset_id: str
    dataset_version: str
    dataset_checksum: str
    risk_policy_id: str
    risk_policy_version: int
    execution_model: str
    cost_model: str
    slippage_model: str
    latency_model: str
    random_seed: int
    runtime_profile: str
    started_at: datetime

    def __post_init__(self) -> None:
        string_fields = (
            self.pytradekit_version,
            self.strategy_id,
            self.strategy_version,
            self.strategy_config_hash,
            self.dataset_id,
            self.dataset_version,
            self.dataset_checksum,
            self.risk_policy_id,
            self.execution_model,
            self.cost_model,
            self.slippage_model,
            self.latency_model,
            self.runtime_profile,
        )
        if any(not isinstance(value, str) or not value.strip() for value in string_fields):
            raise DomainValidationError("RunManifest string fields must be non-empty.")
        if type(self.risk_policy_version) is not int or self.risk_policy_version < 1:
            raise DomainValidationError("RunManifest risk_policy_version must be positive.")
        if type(self.random_seed) is not int:
            raise DomainValidationError("RunManifest random_seed must be an integer.")
        require_utc_datetime(self.started_at, field_name="RunManifest started_at")

    @property
    def fingerprint(self) -> str:
        fields = (
            self.pytradekit_version,
            self.strategy_id,
            self.strategy_version,
            self.strategy_config_hash,
            self.dataset_id,
            self.dataset_version,
            self.dataset_checksum,
            self.risk_policy_id,
            str(self.risk_policy_version),
            self.execution_model,
            self.cost_model,
            self.slippage_model,
            self.latency_model,
            str(self.random_seed),
            self.runtime_profile,
            self.started_at.isoformat(),
        )
        return sha256("|".join(fields).encode("utf-8")).hexdigest()
