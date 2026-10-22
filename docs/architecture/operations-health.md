# Operations Health and Observability Architecture

## Purpose

PyTradeKit 0.7 separates Security, Safety, and Operations.

Operations answers:

- Is the process live?
- Are critical dependencies fresh and healthy?
- Is the runtime operationally ready?
- Is the existing trading readiness still true?
- What operator alert is currently open?
- Can metrics and traces explain the transition?

Operations does not own Orders, Portfolio, Risk, Reconciliation, or broker economic truth.

## Layered readiness

The model keeps three different concepts:

~~~text
PROCESS_LIVE
OPERATIONALLY_READY
TRADING_READY
~~~

TradingReadinessReport from the qualified 0.5/0.6 runtime remains authoritative for economic admission.

OperationalReadinessReport aggregates that result with process lifecycle and freshness-aware dependency health.

## Health freshness

Each HealthComponent has a TTL policy.

A stale HEALTHY observation is converted to UNKNOWN. It never remains green indefinitely.

Critical default components are:

~~~text
DATABASE
BROKER_COMMAND
RUNTIME
~~~

If one becomes missing, stale, degraded, or unhealthy, operational readiness closes.

## Metrics

LOT-06 extends the existing RuntimeMetrics registry with bounded labels.

Allowed labels are intentionally low-cardinality. UUID-like values are rejected from labels.

## Tracing

TraceContext carries business identifiers:

~~~text
CorrelationId
CausationId
~~~

These remain distinct from OpenTelemetry trace and span identifiers.

OpenTelemetryTraceAdapter is an adapter over an injected tracer. Core packages do not import OpenTelemetry.

## Alerts

Alerts are state, not log lines.

The lifecycle is:

~~~text
OPEN
-> ACKNOWLEDGED
-> RESOLVED
~~~

Repeated conditions use a deduplication key and reuse the unresolved alert.

The alert is saved before sink routing. A sink failure therefore cannot erase the operator-visible condition.

## Failure isolation

Telemetry and alert delivery failures are observable failures, not economic state transitions.

They cannot:

- submit an order;
- change a portfolio;
- change broker truth;
- mark reconciliation consistent;
- erase an unresolved alert;
- turn unsafe readiness into safe readiness.

LIVE remains unavailable.
