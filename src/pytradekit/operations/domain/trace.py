"""Business trace context and export records."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType

from pytradekit.shared import (
    CausationId,
    CorrelationId,
    DomainValidationError,
    require_utc_datetime,
)

_SECRET_MARKERS = (
    "bearer ",
    "password=",
    "secret=",
    "api_key=",
    "apikey=",
    "token=",
    "credential=",
)
_FORBIDDEN_KEYS = (
    "secret",
    "password",
    "api_key",
    "apikey",
    "token",
    "credential",
)


@dataclass(frozen=True, slots=True)
class TraceContext:
    """Business identifiers propagated independently from trace/span IDs."""

    correlation_id: CorrelationId | None = None
    causation_id: CausationId | None = None
    attributes: Mapping[str, str | int | bool | None] = field(default_factory=dict)

    def __post_init__(self) -> None:
        sanitized = dict(self.attributes)
        for key, value in sanitized.items():
            lowered_key = key.lower()
            if any(fragment in lowered_key for fragment in _FORBIDDEN_KEYS):
                raise DomainValidationError(
                    f"Trace attribute {key!r} may expose secret material."
                )
            if isinstance(value, str):
                lowered_value = value.lower()
                if any(marker in lowered_value for marker in _SECRET_MARKERS):
                    raise DomainValidationError(
                        "Trace attribute value may expose secret material."
                    )
        object.__setattr__(self, "attributes", MappingProxyType(sanitized))


@dataclass(frozen=True, slots=True)
class TraceRecord:
    """Completed trace span record for an exporter adapter."""

    name: str
    context: TraceContext
    started_at: datetime
    finished_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise DomainValidationError("TraceRecord name must be non-empty.")
        require_utc_datetime(self.started_at, field_name="TraceRecord started_at")
        require_utc_datetime(self.finished_at, field_name="TraceRecord finished_at")
        if self.finished_at < self.started_at:
            raise DomainValidationError(
                "TraceRecord finished_at cannot precede started_at."
            )
