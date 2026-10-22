"""Safety audit adapter using the existing runtime observer."""

from pytradekit.runtime.observability import RuntimeObserver
from pytradekit.safety.domain import SafetyAuditEvent


class RuntimeSafetyAuditSink:
    """Emit sanitized governance events without a second audit subsystem."""

    def __init__(self, observer: RuntimeObserver) -> None:
        self._observer = observer

    def record(self, event: SafetyAuditEvent) -> None:
        metric_by_event = {
            "KILL_SWITCH_ACTIVATED": "kill_switch_activations_total",
            "KILL_SWITCH_RELEASED": "kill_switch_releases_total",
            "RISK_OVERRIDE_CREATED": "risk_overrides_created_total",
            "RISK_OVERRIDE_APPROVED": "risk_overrides_created_total",
            "DANGEROUS_ACTION_CONFIRMED": "dangerous_action_confirmations_total",
        }
        metric = metric_by_event.get(event.event_type)
        if metric is not None:
            self._observer.increment(metric)
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
