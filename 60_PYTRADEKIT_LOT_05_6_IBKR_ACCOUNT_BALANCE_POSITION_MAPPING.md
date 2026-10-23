# 60 - PyTradeKit - LOT-05.6 IBKR Account, Balance & Position Mapping

**Projet :** PyTradeKit  
**Milestone :** 0.8.x - Broker Compliance + IBKR  
**Release :** 0.8.0b1  
**LOT :** LOT-05.6  
**Date :** 2026-10-23  

## 1. Objectif

LOT-05.6 normalise les valeurs de compte et de portefeuille IBKR sans reduire des metriques provider distinctes a un faux concept universel de balance.

Le sous-lot produit :

~~~text
ProviderAccountIdentity
ProviderAccountSnapshot
Balance
ProviderPositionSnapshot
~~~

a partir de records IBKR SDK-free.

## 2. Principe de separation semantique

IBKR expose notamment :

~~~text
TotalCashValue
CashBalance
AvailableFunds
BuyingPower
NetLiquidation
EquityWithLoanValue
ExcessLiquidity
InitMarginReq
MaintMarginReq
~~~

Ces valeurs ne sont pas synonymes.

LOT-05.6 interdit toute projection automatique du type :

~~~text
AvailableFunds == cash
BuyingPower == cash
CashBalance == TotalCashValue
NetLiquidation == portfolio_value
~~~

## 3. Mapping canonique du compte

Le mapping retenu est volontairement etroit :

~~~text
external account id
-> ProviderAccountIdentity.external_account_id

TotalCashValue
-> Balance.cash

NetLiquidation
-> ProviderAccountSnapshot.equity

BuyingPower
-> ProviderAccountSnapshot.buying_power
~~~

ProviderAccountSnapshot.portfolio_value reste None.

LOT-05.6 ne fabrique pas un equivalent IBKR de portfolio_value.

## 4. AvailableFunds

IBKR decrit AvailableFunds comme les fonds disponibles pour le trading, lies aux regles de marge.

Ce n'est pas necessairement du cash libre.

Donc :

~~~text
AvailableFunds
!=
Balance.available
~~~

LOT-05.6 conserve AvailableFunds dans IBKRAccountMappingResult.available_funds.

Balance.available reste None.

## 5. CashBalance

IBKR decrit CashBalance comme le cash reconnu au moment du trade plus futures PNL.

LOT-05.6 ne le confond pas avec TotalCashValue.

~~~text
TotalCashValue
-> canonical Balance.cash

CashBalance
-> retained provider metric only
~~~

Cette distinction reste valable meme lorsque les deux valeurs ont la meme devise.

## 6. NetLiquidation

NetLiquidation est conserve comme meilleure projection du concept canonique equity.

~~~text
NetLiquidation
-> ProviderAccountSnapshot.equity
~~~

EquityWithLoanValue reste une metrique provider distincte.

## 7. AccountReady

IBKR documente qu'un compte peut retourner :

~~~text
AccountReady = false
~~~

pendant un reset serveur.

Dans ce cas, les valeurs suivantes peuvent etre obsoletes ou incorrectes.

LOT-05.6 applique donc :

~~~text
AccountReady = false
-> ProviderProtocolError
-> no canonical snapshot
~~~

## 8. Restrictions de compte

Le contrat canonique ProviderAccountSnapshot exige :

~~~text
trading_blocked
account_blocked
~~~

Les metriques financieres TWS ne prouvent pas ces booleens.

LOT-05.6 exige donc un objet :

~~~text
IBKRAccountRestrictionsObservation
~~~

avec une source d'evidence explicite.

Aucune valeur False n'est inventee par defaut.

## 9. Multi-currency

IBKR peut fournir des valeurs par devise.

LOT-05.6 autorise plusieurs occurrences d'un meme tag uniquement si la devise differe.

Le snapshot canonique utilise uniquement les valeurs correspondant a :

~~~text
Account.base_currency
~~~

Les autres valeurs restent accessibles dans l'observation provider.

## 10. Position

Le record IBKRPortfolioPositionObservation conserve :

~~~text
account
conId
symbol
currency
signed quantity
average cost
market price
market value
unrealized PNL
realized PNL
observed_at
~~~

## 11. Signed quantity

La quantite provider reste signee :

~~~text
long  -> positive
short -> negative
~~~

Aucune recomposition via un enum side n'est necessaire.

## 12. Average cost et cost basis

Dans le scope STK fige, le cout moyen provider devient :

~~~text
averageCost
-> ProviderPositionSnapshot.average_price
~~~

Le cost basis canonique est calcule comme :

~~~text
abs(signed_quantity) * averageCost
~~~

Cette regle reste limitee au vertical slice STK, ou le multiplier est 1.

## 13. Market values

Lorsque disponibles :

~~~text
marketPrice
-> current_price

marketValue
-> market_value

unrealizedPNL
-> unrealized_pnl
~~~

Lorsque ces observations ne sont pas fournies par la source position courante :

~~~text
None remains None
~~~

Aucune mark-to-market n'est fabriquee.

## 14. Realized PNL

Le modele ProviderPositionSnapshot ne contient pas de realized PNL provider.

LOT-05.6 le conserve donc dans :

~~~text
IBKRPositionMappingResult.provider_realized_pnl
~~~

Il n'est pas injecte artificiellement dans la position canonique.

## 15. Available quantity

Les callbacks position/portfolio IBKR utilises ici ne fournissent pas une semantique equivalente a available_quantity.

Donc :

~~~text
ProviderPositionSnapshot.available_quantity = None
~~~

## 16. Identity checks

Avant emission d'un snapshot de position :

~~~text
external account id
conId
symbol
currency
~~~

doivent correspondre aux mappings canoniques attendus.

Un mismatch produit ProviderProtocolError.

## 17. Fitness functions

~~~text
FF-121 No IBKR SDK import in account mapper.
FF-122 TotalCashValue alone maps to canonical Balance.cash.
FF-123 AvailableFunds never maps to Balance.available.
FF-124 CashBalance never replaces TotalCashValue.
FF-125 NetLiquidation maps to equity but not portfolio_value.
FF-126 AccountReady false blocks snapshot emission.
FF-127 Account restriction flags require explicit evidence.
FF-128 Position signed quantity is preserved.
FF-129 Missing market observations remain None.
FF-130 Position available_quantity is never fabricated.
~~~

## 18. Sources provider

Official IBKR TWS API documentation consulted:

~~~text
https://www.interactivebrokers.com/docs/tws-api/sync-doc/account-summary
https://www.interactivebrokers.com/docs/tws-api/doc/account-portfolio-data/account-updates/account-value-keys
https://www.interactivebrokers.com/docs/tws-api/sync-doc/portfolio
https://www.interactivebrokers.com/docs/tws-api/sync-doc/positions
~~~

## 19. Next

~~~text
LOT-05.7
IBKR Error Taxonomy, Readiness & Capability Manifest
~~~
