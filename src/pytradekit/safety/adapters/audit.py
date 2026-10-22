"""Safety audit adapter using the existing runtime observer."""

from pytradekit.runtime.observability import RuntimeObserver
from pytradekit.safety.domain import SafetyAuditEvent


class RuntimeSafetyAuditSink:
    """Emit sanitized governance events without a second audit subsystem."""

    def __init__(self, observer: RuntimeObserver) -> None:
        self._observer = observer

    def record(self, event: SafetyAuditEvent) -> None:
        self._observer.event(
            event.event_type,
            actor_id=str(event.actor_id),
            action=event.action,
            scope_reference=event.scope_reference,
            reason=event.reason,
            correlation_id=(
                str(event.correlation_id)
                if event.correlation_id is not None
                else None
            ),
        )
