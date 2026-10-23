# IBKR Real PAPER Certification Architecture

## Purpose

LOT-06.7 separates implementation qualification from real provider certification.

~~~text
deterministic CI
-> C2 baseline

real PAPER probe
-> sanitized provider facts
-> provenance + SHA-256
-> retained evidence
-> ComplianceHarness
-> C3 per proven capability
~~~

## No synthetic provider evidence

Deterministic tests may construct in-memory evidence objects to test certification logic.

They do not create retained evidence files and cannot become a provider qualification artifact.

## Provider path

The real probe uses the canonical IBKR execution adapter.

It does not call placeOrder or cancelOrder directly.

## Identity privacy

Provider account identity is masked.

permId, orderId, execId and orderRef values are reduced to boolean or count evidence before serialization.

## Provenance

The normalized retained record binds provider evidence to the exact qualified commit and to the successful deterministic CI run for that commit.

## Partial fill

PARTIAL_FILL remains C2 until an actual partial fill is captured.

## Release promotion

C3 target enforcement exists only in the manual real PAPER workflow.
