# Financial Value Objects

## Purpose

PyTradeKit uses explicit immutable Value Objects so financial meaning is carried by types rather than loose primitives.

## Currency

~~~python
from pytradekit.shared import Currency

usd = Currency("usd")
assert usd.code == "USD"
~~~

Currency currently accepts exactly three ASCII alphabetic characters and stores the canonical uppercase form.

## Money

~~~python
from decimal import Decimal
from pytradekit.shared import Currency, Money

eur = Currency("EUR")
cash = Money(Decimal("125.42"), eur)
~~~

Rules:

- amount must be a finite Decimal
- currency must be a Currency
- addition and subtraction require the same currency
- comparison requires the same currency
- negative amounts are valid
- NaN and Infinity are rejected

Cross-currency arithmetic is not performed implicitly.

## Price

Price must be a finite Decimal strictly greater than zero and carries an explicit currency.

A Price does not encode tick size globally.

## Quantity

Quantity accepts zero and fractional finite Decimal values. Negative values are rejected.

Lot size, quantity step, and minimum quantity belong to ContractSpecification.

## Percentage

Convention:

~~~text
0.05 == 5 percent
~~~

Percentages are not globally restricted to [0, 1] because returns can be negative and PnL percentages can exceed 100 percent.

## Price times Quantity

~~~python
from decimal import Decimal
from pytradekit.shared import Currency, Price, Quantity

usd = Currency("USD")
price = Price(Decimal("192.50"), usd)
quantity = Quantity(Decimal("10"))

notional = price * quantity
assert str(notional) == "Money(1925.00 USD)"
~~~

## Precision policy

PyTradeKit 0.1 deliberately does not define a global rounding mode or global decimal precision. Market-specific validation belongs to ContractSpecification.
