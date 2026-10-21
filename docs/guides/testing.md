# Testing Guide

## FakeClock

Use FakeClock whenever a test depends on current time.

~~~python
from datetime import UTC, datetime, timedelta
from pytradekit.testing import FakeClock

clock = FakeClock.at(datetime(2026, 1, 1, 12, 0, tzinfo=UTC))
clock.advance(timedelta(minutes=5))

assert clock.now() == datetime(2026, 1, 1, 12, 5, tzinfo=UTC)
~~~

FakeClock rejects naive and non-UTC datetimes.

## InstrumentBuilder

~~~python
from pytradekit.testing import InstrumentBuilder

instrument = InstrumentBuilder.equity(symbol="MSFT", currency="USD")
~~~

Builders are testing-only helpers and do not belong to the Domain.

## Hypothesis finance strategies

Reusable strategies are available from pytradekit.testing.strategies:

- finite_decimals
- currencies
- money_values
- quantities
- prices

Default strategies exclude NaN and Infinity.

## Architecture checks

Run:

~~~bash
make architecture
~~~

This executes both import-linter contracts and architecture/public import tests.

## Full local qualification

Run:

~~~bash
make check
~~~

This checks typography, lint, typing, architecture, tests, and release artifact qualification.
