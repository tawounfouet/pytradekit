# Runbook - External Activity

## Trigger

Use this runbook when provider state contains an order, Fill, position change, or cash change without proven PyTradeKit intent lineage.

## Classification

Supported origin values include:

- INTERNAL
- EXTERNAL_MANUAL
- EXTERNAL_SYSTEM
- BROKER_ADJUSTMENT
- UNKNOWN_EXTERNAL
- IMPORTED

## Rules

An unknown provider order must not silently become an internal strategy order.

A proven Fill may be imported only when its economic identity and canonical order relationship are safe.

If origin cannot be proven, preserve UNKNOWN_EXTERNAL and block or require manual review.

## Procedure

1. Capture provider evidence.
2. Attempt canonical identity mapping.
3. Record external activity classification.
4. Reconcile downstream position and balance effects.
5. Apply only safe import resolutions.
6. Verify with fresh evidence.
7. Re-evaluate consistency, confidence and risk admission.
