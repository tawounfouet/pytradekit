# Runbook - Secret Provider Unavailable

A missing env://, file://, or external:// reference makes deployment readiness false and fails startup closed before broker infrastructure construction.

Verify the SecretRef scheme and locator, restore provider or file access without printing the sensitive value, restart the process, recompute readiness, and run reconciliation before restoring trading admission.

Never bypass the outage by hard-coding a credential in configuration.
