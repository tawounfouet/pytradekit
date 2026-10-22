# Runbook - Startup Timeout

A startup timeout increments runtime_start_timeouts, sets trading_ready to 0, and leaves RuntimeAdmissionGate DEGRADED.

Inspect database, provider connectivity, DNS, and reference availability. Stop the timed-out process, correct the dependency failure, restart, and require fresh readiness plus reconciliation before trading admission.

A late startup result cannot reopen the gate.
