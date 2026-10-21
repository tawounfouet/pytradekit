"""Strategy run lifecycle states."""

from enum import StrEnum


class StrategyRunStatus(StrEnum):
    """Canonical lifecycle states for one strategy execution."""

    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"
    CANCELLED = "cancelled"
