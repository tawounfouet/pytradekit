"""Safety evidence derived from existing runtime and reconciliation state."""

from dataclasses import dataclass

from pytradekit.reconciliation.domain import (
    ConsistencyStatus,
    RecoveryState,
    StateConfidence,
)
from pytradekit.runtime.operations import RuntimeLifecycleState


@dataclass(frozen=True, slots=True)
class SafetyEvidence:
    """Current evidence required to derive SafetyState."""

    consistency_status: ConsistencyStatus | None
    state_confidence: StateConfidence | None
    recovery_state: RecoveryState | None
    runtime_lifecycle: RuntimeLifecycleState | None
    trading_ready: bool | None
    critical_health_healthy: bool | None = True
