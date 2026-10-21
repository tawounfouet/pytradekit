# Fake Execution Guide

## Purpose

FakeExecutionAdapter is the deterministic execution adapter for milestone 0.2.

It enables qualification of OMS semantics without network access, credentials, a live broker, or a paper-trading account.

## Basic setup

~~~python
from pytradekit.brokers.adapters.fake import FakeExecutionAdapter, FakeExecutionScenario
from pytradekit.testing import FakeClock

execution = FakeExecutionAdapter(
    scenario=FakeExecutionScenario.accept_immediately(),
    clock=clock,
)
~~~

The adapter implements the consumer-owned ExecutionPort.

## Available scenarios

### Acceptance

~~~python
FakeExecutionScenario.accept_immediately()
~~~

### Rejection

~~~python
FakeExecutionScenario.reject_immediately(reason="venue rejected order")
~~~

### Immediate full fill

~~~python
FakeExecutionScenario.fill_immediately(price=price)
~~~

### Partial fills

~~~python
FakeExecutionScenario.partial_then_fill(
    price=price,
    partial_quantities=(q1, q2),
)
~~~

The fake fills the remaining quantity after the configured partial quantities.

### Submission timeout

~~~python
FakeExecutionScenario.submit_timeout(
    resolve_as=ExecutionStatus.ACCEPTED,
)
~~~

The immediate result is UNCERTAIN. query_order later returns the configured canonical resolution.

The resolution can be ACCEPTED or REJECTED.

### Cancellation rejection

~~~python
FakeExecutionScenario.cancel_rejected(reason="too late to cancel")
~~~

### Cancellation timeout

~~~python
FakeExecutionScenario.cancel_timeout()
~~~

The cancel call returns UNCERTAIN and does not synthesize a cancellation confirmation.

## Delivering reports

submit and cancel may queue execution reports.

Tests and examples explicitly deliver them:

~~~python
for report in execution.drain_reports(order_id):
    handle_execution_report.execute(report)
~~~

This keeps message ordering deterministic and lets tests inject delayed or duplicated facts.

## Injecting faults

Use inject_report to place a duplicate, stale, or out-of-order report in the fake queue.

~~~python
execution.inject_report(report)
~~~

The OMS, not the fake adapter, is responsible for protecting domain invariants.

## What the fake does not model

FakeExecutionAdapter is not a market simulator.

It does not model:

- order books
- latency distributions
- slippage
- fees unless supplied on Fill
- trading sessions
- exchange matching rules
- real broker protocol behavior
- durable recovery after process restart

Those concerns belong to later milestones or broker-specific qualification.
