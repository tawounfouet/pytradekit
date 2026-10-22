# Runbook - Secret Rotation

PyTradeKit 0.7 does not qualify hot credential reload.

Rotate the external credential, keep the same SecretRef where possible, restart the process, resolve all references, run migrations, recompute operational readiness, reconnect provider streams, run fresh reconciliation, and restore economic admission only after safety and trading readiness are valid.

If the rotated reference cannot be resolved, startup remains not ready.
