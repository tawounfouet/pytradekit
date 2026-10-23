# IBKR Error Taxonomy, Readiness & Capability Manifest

## Scope

LOT-05.7 closes the SDK-free IBKR Anti-Corruption Layer contract before any provider-backed PAPER qualification.

It defines three distinct concerns:

1. provider error classification;
2. runtime admission readiness;
3. conservative capability declaration.

No provider network call is performed.

## Error taxonomy

The adapter classifies documented TWS API codes without assuming that every callback represents the same kind of failure.

Key rules:

- 100 maps to provider rate limiting;
- 200 maps to a rejected provider request;
- 201 and 202 remain owned by order callback normalization;
- 203 maps to provider authorization failure;
- 326, 502, 504 and 507 represent connection or session failures;
- 503 is a protocol compatibility failure;
- 1100 requires reconciliation after connectivity loss;
- 1101 means connectivity restored with provider data lost;
- 1102 means connectivity restored with provider data maintained;
- 1300 requires reconnect because the socket port changed;
- 2103 degrades market-data readiness only;
- 2104, 2106, 2107, 2108 and 2158 are informational notifications;
- 2110 requires reconciliation.

Unknown provider codes fail closed.

## Economic-write safety

A connectivity or unknown error observed while an economic write is in flight never becomes a retry instruction.

It maps to:

```text
ProviderUncertainOutcomeError
-> reconcile
-> prove broker state
-> only then admit another economic write
```

This preserves the existing PyTradeKit rule:

```text
timeout or disconnect != failure
unknown outcome != safe retry
```

## Readiness

IBKR readiness remains explicit and fact-based.

The frozen facts are:

```text
SOCKET_CONNECTED
PROTOCOL_NEGOTIATED
NEXT_VALID_ID_RECEIVED
ACCOUNT_VERIFIED
PAPER_ENDPOINT_VERIFIED
RECONCILIATION_COMPLETE
```

Additional admission inputs are:

```text
AccountReady
API read-only mode
market-data resubscription state
last connectivity system code
```

Read readiness and economic-write readiness are intentionally different.

A runtime can be ready for safe reads while still refusing new orders.

## 1101 vs 1102

Code 1101:

```text
connection restored
provider data lost
market-data subscriptions must be restored
reconciliation required before economic writes
```

Code 1102:

```text
connection restored
provider data maintained
no market-data resubscription requirement
reconciliation still gates new economic writes
```

The second rule is intentionally stricter than the provider notification because PyTradeKit must prove state convergence before reopening economic side effects.

## Market-data degradation

Code 2103 affects market-data readiness but does not automatically make account and order reads unavailable.

This prevents a market-data farm incident from being misrepresented as a total trading-session outage.

## Capability manifest

LOT-05.7 declares the broker-neutral capability envelope already represented by the ACL:

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

The manifest does not declare:

```text
LATEST_QUOTE
REPLACE_ORDER
```

LATEST_QUOTE remains blocked until transport, entitlement, and quote semantics are implemented.

REPLACE_ORDER remains outside the frozen scope.

## Certification boundary

The manifest is a declaration, not certification evidence.

LOT-05.7 therefore makes no C2 or C3 claim for IBKR.

No SDK is selected and no real PAPER account is contacted.

## Sources

Provider behavior was checked against Interactive Brokers documentation for:

- TWS API message codes and connectivity notifications;
- API socket connection behavior;
- API read-only configuration;
- error callback semantics.

## Next

The next milestone should leave the purely deterministic ACL and introduce the first provider-backed IBKR PAPER runtime and compliance qualification.
