# Portfolio Guide

## Overview

The Portfolio bounded context turns canonical execution fills into account balances and positions.

Actual economic state is fill-driven.

## Account

An Account has:

- AccountId
- base Currency
- optional name

AccountId is internal and provider independent.

## Balance

Balance represents cash for one account and currency.

Milestone 0.3 uses:

- cash
- optional available amount
- optional reserved amount
- optional update timestamp

Cash may become negative. Margin policy is a Risk concern, not a Balance validation rule.

## Position

Position uses signed quantity semantics.

~~~text
+10 -> LONG 10
 -4 -> SHORT 4
  0 -> FLAT
~~~

Position stores:

- account
- instrument
- signed quantity
- average entry price
- cumulative realized PnL
- opened timestamp
- updated timestamp

## Applying fills

Use ApplyFillToPortfolio with repositories owned by Portfolio.

~~~python
service = ApplyFillToPortfolio(
    positions=positions,
    balances=balances,
    processed_fills=processed_fills,
)

result = service.execute(
    fill,
    account_id=account_id,
    instrument_id=instrument_id,
    side=OrderSide.BUY,
)
~~~

The service updates:

- Position
- Balance
- processed-fill registry

A duplicate fill returns applied=False and does not repeat the economic effect.

## Position accounting

Increasing a position in the same direction updates the weighted average entry price.

Closing quantity realizes PnL.

A fill larger than the open position closes the old side and opens the opposite side at the flip fill price.

## Portfolio snapshot

BuildPortfolioSnapshot creates an immutable PortfolioSnapshot from:

- Account
- PositionRepository
- BalanceRepository
- market prices
- ClockPort

The snapshot exposes:

- cash
- positions
- NAV
- gross exposure
- net exposure
- realized PnL
- unrealized PnL
- leverage

## Currency boundary

Milestone 0.3 uses same-currency valuation.

Portfolio balances, position accounting currency, and supplied market prices must match the Account base currency.

FX conversion is intentionally deferred.
