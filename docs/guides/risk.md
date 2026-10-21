# Risk Guide

## Overview

The Risk bounded context evaluates hypothetical order outcomes before broker submission.

Risk operates on ProjectedPortfolio. It never mutates actual Portfolio state.

## Configure a policy

A RiskPolicy is immutable, scoped, enabled or disabled, and versioned.

Example:

~~~python
policy = RiskPolicy(
    id=RiskPolicyId.new(),
    name="global-default",
    scope=RiskScope.GLOBAL,
    limits=(
        MaxOrderSize(Money(Decimal("10000"), USD)),
        MaxLeverage(Decimal("2.0")),
    ),
    enabled=True,
    version=1,
)
~~~

## P0 limits

Milestone 0.3 includes:

- MaxOrderSize
- MaxPositionSize
- MaxGrossExposure
- MaxLeverage
- DailyLoss

Each rule is pure. It receives RiskContext and returns either:

- no violation
- one RiskViolation

## Evaluate an order

EvaluateOrderRisk requires:

- active risk policies
- current PortfolioSnapshot through PortfolioViewPort
- TradingHalt state
- ClockPort
- order facts
- deterministic pricing context

For a MARKET order, provide reference_price.

For a LIMIT order, the order limit price is used.

## Decision semantics

~~~text
ALLOW  -> submission may continue
WARN   -> submission may continue with a recorded warning
REJECT -> submission must not reach ExecutionPort
HALT   -> submission is rejected and an account halt is persisted
~~~

The most restrictive decision wins.

## Fail-safe behavior

Risk-increasing activity is rejected when required input is unavailable.

Examples:

- missing PortfolioSnapshot
- missing MARKET reference price
- portfolio projection cannot be computed
- no active risk policy for a risk-increasing order

## Trading halt

TradingHalt is persisted explicit state.

Supported scopes:

- GLOBAL
- ACCOUNT
- STRATEGY

An active halt rejects risk-increasing orders.

A reducing order may continue if the applicable policy allows reduce-only behavior.

Use TriggerTradingHalt and ReleaseTradingHalt for explicit lifecycle control.

## Orders integration

Orders owns RiskEvaluationPort.

Risk exposes OrdersRiskEvaluationAdapter to satisfy that consumer-owned port.

When SubmitOrder has a RiskEvaluationPort configured:

~~~text
create order
-> validate order
-> persist pre-submission state
-> evaluate risk
-> if rejected: return without broker call
-> if allowed: mark submitted
-> call ExecutionPort
~~~

This order of operations is a safety invariant.
