# IBKR Account, Balance & Position Mapping

LOT-05.6 maps IBKR account and portfolio observations without collapsing provider-specific financial semantics.

## Account mapping

~~~text
TotalCashValue -> Balance.cash
NetLiquidation -> ProviderAccountSnapshot.equity
BuyingPower    -> ProviderAccountSnapshot.buying_power
~~~

The following remain separate provider metrics:

~~~text
CashBalance
AvailableFunds
EquityWithLoanValue
ExcessLiquidity
InitMarginReq
MaintMarginReq
~~~

AvailableFunds does not become Balance.available.

CashBalance does not replace TotalCashValue.

NetLiquidation does not get duplicated into portfolio_value.

## Account readiness

If provider evidence says the account is not ready, no canonical account snapshot is emitted.

Restriction flags also require explicit evidence because financial account tags do not prove account blocking state.

## Position mapping

For the frozen STK scope:

~~~text
position      -> signed_quantity
averageCost   -> average_price
marketPrice   -> current_price
marketValue   -> market_value
unrealizedPNL -> unrealized_pnl
~~~

Cost basis is derived as:

~~~text
abs(position) * averageCost
~~~

This is limited to the STK scope where the contract multiplier is one.

Provider realized PNL is retained outside ProviderPositionSnapshot because the canonical snapshot does not define an equivalent field.

available_quantity remains unknown.

## SDK isolation

The mapper consumes only:

~~~text
IBKRAccountSummaryObservation
IBKRAccountMetric
IBKRPortfolioPositionObservation
~~~

No ibapi or ib_async type crosses the adapter boundary.
