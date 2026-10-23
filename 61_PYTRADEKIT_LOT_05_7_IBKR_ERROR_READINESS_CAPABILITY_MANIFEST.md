# 61 - PyTradeKit - LOT-05.7 IBKR Error Taxonomy, Readiness & Capability Manifest

**Projet :** PyTradeKit  
**Milestone :** 0.8.x - Broker Compliance + IBKR  
**Release :** 0.8.0b1  
**LOT :** LOT-05.7  
**Date :** 2026-10-23  

## 1. Objectif

LOT-05.7 termine le contrat deterministic de l'ACL IBKR avant toute qualification PAPER reelle.

Il fige :

```text
error taxonomy
readiness policy
capability manifest
```

## 2. Error taxonomy

La taxonomy distingue :

```text
INFORMATION
CONNECTIVITY
PACING
REQUEST_REJECTED
ORDER_REJECTED
ORDER_STATE
AUTHORIZATION
PROTOCOL
UNKNOWN
```

Chaque code possede egalement une disposition provider-local :

```text
IGNORE
DEGRADE
RECONNECT
RECONCILE
RATE_LIMIT
REJECT_OPERATION
ORDER_CALLBACK
FAIL_CLOSED
```

## 3. Connectivity safety

Codes majeurs :

```text
1100 -> connectivity lost
1101 -> restored, data lost
1102 -> restored, data maintained
1300 -> socket port reset
2110 -> server connectivity broken
```

Une perte de connexion pendant une ecriture economique produit :

```text
ProviderUncertainOutcomeError
```

et jamais un retry automatique.

## 4. Informational messages

Les notifications suivantes ne deviennent pas des erreurs canoniques :

```text
2104
2106
2107
2108
2158
```

## 5. Readiness

Les faits de readiness proviennent du contract freeze LOT-04 :

```text
SOCKET_CONNECTED
PROTOCOL_NEGOTIATED
NEXT_VALID_ID_RECEIVED
ACCOUNT_VERIFIED
PAPER_ENDPOINT_VERIFIED
RECONCILIATION_COMPLETE
```

S'ajoutent :

```text
AccountReady
api_read_only
market_data_resubscribed
last_connectivity_code
```

## 6. Read vs write admission

Les lectures peuvent rester autorisees alors que les ecritures economiques sont bloquees.

Exemples :

```text
nextValidId absent
-> reads possible
-> writes blocked

API read-only
-> reads possible
-> writes blocked

reconciliation incomplete
-> reads possible
-> writes blocked
```

## 7. Code 1101

Apres 1101 :

```text
market data subscriptions lost
-> resubscribe
-> reconcile
-> only then resume economic writes
```

## 8. Code 2103

Une market data farm deconnectee :

```text
market data readiness = false
account/order read readiness can remain true
economic write readiness can remain true
```

si les autres faits de readiness restent prouves.

## 9. Capability Manifest

Le manifest LOT-05.7 declare :

```text
ACCOUNT_QUERY
ORDER_QUERY
MARKET_ORDER
LIMIT_ORDER
CANCEL_ORDER
PARTIAL_FILL
POSITION_QUERY
BALANCE_QUERY
CLIENT_ORDER_REFERENCE
EXECUTION_FACTS
RECONNECT_RECOVERY
```

Il ne declare pas :

```text
LATEST_QUOTE
REPLACE_ORDER
```

## 10. Non-certification

Le manifest ne signifie pas :

```text
C2 Integration Qualified
C3 Paper Qualified
```

LOT-05.7 ne realise aucun appel provider.

## 11. SDK policy

Aucun SDK n'est selectionne :

```text
sdk_name = None
sdk_version = None
```

Le choix entre transport officiel, transport alternatif ou implementation protocolaire reste separe du contrat canonique.

## 12. Fitness functions

```text
FF-131 Documented informational codes do not become canonical failures.
FF-132 Code 100 maps to ProviderRateLimitError.
FF-133 Code 1100 requires reconciliation.
FF-134 Connectivity loss during an economic write becomes uncertain outcome.
FF-135 Code 1101 requires market-data resubscription.
FF-136 Code 1102 does not require market-data resubscription.
FF-137 API read-only mode blocks economic writes.
FF-138 Missing nextValidId blocks writes but not safe reads.
FF-139 Market-data farm loss does not imply total broker outage.
FF-140 Unknown provider codes fail closed.
FF-141 IBKR manifest is PAPER only.
FF-142 LATEST_QUOTE and REPLACE_ORDER are not overclaimed.
FF-143 LOT-05.7 introduces no provider SDK dependency.
FF-144 LOT-05.7 introduces no broker-specific core change.
```

## 13. Sources provider

Official IBKR documentation consulted for TWS API message codes, socket connectivity, read-only API configuration, and error callback behavior.

## 14. Next

```text
LOT-06
IBKR PAPER Transport, Runtime Integration & Compliance Qualification
```

The exact sub-lot split should preserve the same rule used so far:

```text
narrow scope
+
retained qualification evidence
+
no certification without real provider proof
```
