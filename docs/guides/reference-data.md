# Reference Data Guide

## Canonical instrument identity

InstrumentId is the provider-independent identity of an instrument.

~~~python
from pytradekit.reference import AssetClass, Instrument
from pytradekit.shared import Currency, InstrumentId

instrument = Instrument(
    id=InstrumentId.new(),
    symbol="AAPL",
    asset_class=AssetClass.EQUITY,
    quote_currency=Currency("USD"),
)
~~~

The symbol is descriptive reference data, not a globally unique identity.

## AssetClass

Milestone 0.1 defines equity, ETF, FX, crypto, future, option, and CFD.

Asset-specific trading logic remains outside this foundational model.

## ContractSpecification

ContractSpecification owns contract and venue constraints such as tick size, quantity step, minimum quantity, maximum quantity, and minimum notional.

Validation never applies silent rounding.

~~~python
from decimal import Decimal
from pytradekit.reference import ContractSpecification
from pytradekit.shared import Quantity

specification = ContractSpecification(quantity_step=Decimal("0.25"))

assert specification.is_valid_quantity(Quantity(Decimal("1.25")))
assert not specification.is_valid_quantity(Quantity(Decimal("1.10")))
~~~

## InstrumentMapping

Provider-specific identifiers are mapped separately:

~~~python
from pytradekit.reference import InstrumentMapping

mapping = InstrumentMapping(
    instrument_id=instrument.id,
    provider="alpaca",
    external_symbol="AAPL",
)
~~~

This prevents Alpaca, IBKR, cTrader, or another provider from defining canonical domain identity.
