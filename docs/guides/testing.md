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

## OMS qualification layers

Milestone 0.2 adds several complementary layers.

Unit tests verify aggregate transitions and value invariants.

Property tests verify fill and quantity invariants across generated inputs.

Contract tests verify OrderRepository and ExecutionPort implementations.

End-to-end tests verify complete application flows through:

~~~text
application use case
-> port
-> fake adapter
-> execution report
-> aggregate
-> repository
~~~

Fault tests qualify:

- duplicate fills
- submit timeout
- query convergence
- out-of-order acceptance
- cancel timeout
- cancel/fill races

Run the E2E and fault suite directly with:

~~~bash
pytest tests/e2e
~~~

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

This checks typography, lint, typing, architecture, unit tests, property tests, contracts, E2E tests, fault tests, and release artifact qualification.

## Release artifact qualification

Run:

~~~bash
make release-check
~~~

The release check:

1. builds exactly one wheel and one source distribution
2. calculates SHA-256 digests
3. creates a clean virtual environment
4. installs the wheel
5. verifies the installed package version
6. runs every executable example against the installed wheel
