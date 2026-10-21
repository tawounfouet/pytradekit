# Portfolio & Risk Architecture

## Purpose

PyTradeKit 0.3 adds two bounded contexts on top of the 0.2 OMS and Execution foundation:

- Portfolio turns canonical fills into economic state.
- Risk evaluates hypothetical order outcomes before broker submission.

The design keeps actual state and projected state separate.

## Core flows

Actual economic state:

~~~text
ExecutionReport
-> Fill
-> ProcessFill
-> Order
-> PortfolioEffectPort
-> ApplyFillToPortfolio
-> Position + Balance
-> PortfolioSnapshot
~~~

Pre-trade state:

~~~text
SubmitOrderCommand
-> Order
-> RiskEvaluationPort
-> EvaluateOrderRisk
-> ProjectedPortfolio
-> RiskPolicy
-> RiskLimit rules
-> ALLOW / WARN / REJECT / HALT
~~~

A REJECT decision returns before ExecutionPort.submit.

## Portfolio accounting model

Position quantity is signed:

~~~text
positive -> LONG
negative -> SHORT
zero     -> FLAT
~~~

The position model supports:

- increasing an existing position
- weighted average price
- partial close
- full close
- long-to-short flip
- short-to-long flip
- realized PnL on closed quantity

A flat position has no average price.

Portfolio accounting is fill-driven. An order request or risk projection never mutates actual Position or Balance state.

## Duplicate protection

Fill has a stable deduplication key.

ApplyFillToPortfolio uses ProcessedFillRegistry so one fill produces one portfolio economic effect.

This protects both:

- Position accounting
- Balance accounting

Order fill deduplication and Portfolio fill deduplication are separate safeguards because the bounded contexts own different effects.

## Portfolio valuation

BuildPortfolioSnapshot creates an immutable read model as of one ClockPort timestamp.

The milestone computes:

- cash
- signed market value
- NAV
- realized PnL
- unrealized PnL
- gross exposure
- net exposure
- gross leverage

Milestone 0.3 valuation is intentionally same-currency. Positions and market prices must use the account base currency.

Multi-currency conversion remains a later capability.

## Projected portfolio

Risk does not mutate Portfolio to evaluate an order.

Instead it builds ProjectedPortfolio from:

- current PortfolioSnapshot
- instrument
- side
- quantity
- reference price

The projection computes hypothetical:

- position quantity
- order notional
- cash
- NAV
- gross exposure
- net exposure
- leverage
- risk-increasing flag

This separation is a safety boundary.

## Risk policies

RiskPolicy is immutable and versioned.

A policy contains pure RiskLimit rules and applies at a RiskScope.

Supported milestone scopes are:

- GLOBAL
- PORTFOLIO
- ACCOUNT
- STRATEGY
- BROKER
- ASSET_CLASS
- INSTRUMENT

The milestone application layer resolves GLOBAL, ACCOUNT, STRATEGY, and INSTRUMENT policies.

## Risk decisions

Rules produce violations and a decision severity:

~~~text
ALLOW
WARN
REJECT
HALT
~~~

When multiple policies or rules apply, the most restrictive decision wins.

P0 rules are:

- MaxOrderSize
- MaxPositionSize
- MaxGrossExposure
- MaxLeverage
- DailyLoss

## Fail-safe pricing

Risk requires deterministic pricing context.

For LIMIT orders:

~~~text
reference price = order limit price
~~~

For MARKET orders:

~~~text
reference price = explicit market reference price
~~~

If required portfolio state or pricing is unavailable, risk-increasing activity is rejected rather than guessed.

## Trading halt

TradingHalt is explicit persisted state.

Supported halt scopes are:

- GLOBAL
- ACCOUNT
- STRATEGY

An active halt blocks risk-increasing activity.

Reduce-only activity may continue when the applicable RiskPolicy explicitly allows it.

Release is explicit through ReleaseTradingHalt.

## Port ownership

Ports are owned by the consumer that needs the behavior.

Orders owns:

- ExecutionPort
- OrderRepository
- RiskEvaluationPort
- PortfolioEffectPort

Risk owns:

- PortfolioViewPort
- RiskPolicyRepository
- TradingHaltRepository

Portfolio owns:

- PositionRepository
- BalanceRepository
- ProcessedFillRegistry

Adapters translate between bounded contexts without introducing domain-level dependencies.

## Architecture guarantees

CI mechanically protects the 0.3 boundaries.

Important invariants include:

- Portfolio domain does not depend on Risk
- Portfolio domain does not depend on brokers
- Risk domain does not depend on brokers
- Orders domain does not depend on Risk
- Portfolio and Risk domains do not depend on persistence frameworks
- the package import graph remains acyclic

## Explicit non-goals

Milestone 0.3 does not add:

- durable database persistence
- broker reconciliation
- real broker adapters
- multi-currency FX conversion
- strategy runtime
- backtest runtime
- distributed execution
- production operations
