# Operations Guide

## Health

Use HealthRegistry to retain the latest component observations and apply freshness rules.

Use CallableHealthCheck for read-only probes such as:

~~~text
DATABASE
BROKER_READ
BROKER_COMMAND
BROKER_STREAM
MARKET_DATA
OUTBOX
INBOX
RECONCILIATION
RUNTIME
~~~

## Liveness and readiness

Use:

~~~text
GetLiveness
GetHealthReport
GetReadinessReport
ApplyOperationalReadiness
~~~

Do not infer trading readiness from liveness.

## Metrics

Use the existing RuntimeObserver and RuntimeMetrics.

Prefer bounded labels such as:

~~~text
permission
decision
environment
component
status
severity
alert_type
~~~

Never use actor, account, order, alert, mismatch, or other UUID identifiers as metric labels.

## Tracing

Create a TraceContext with the business CorrelationId and optional CausationId.

Wrap an application operation with TraceRecorder.observe.

Exporter failures are recorded through telemetry_export_failures_total and do not change the operation result.

## Alerts

Use:

~~~text
RaiseAlert
ListOpenAlerts
AcknowledgeAlert
ResolveAlert
OperationalAlertEvaluator
~~~

Resolution requires verified_clear=True.

A delivery sink is not the source of alert truth. Alert state is stored before routing.

LIVE remains unavailable.
