# Runbook - Database Unavailable

## Trigger

DATABASE health becomes UNHEALTHY or freshness expires to UNKNOWN.

## Expected containment

- operational_ready becomes false;
- new risk-increasing admission closes;
- process liveness may remain true;
- DATABASE_UNAVAILABLE alert remains OPEN;
- observation and recovery work remain available when safe.

## Operator actions

1. Verify PostgreSQL reachability and connection pool state.
2. Verify credentials by reference without printing secret values.
3. Verify migration state.
4. Restore database connectivity.
5. Run health checks again.
6. Verify operational readiness.
7. Verify trading readiness independently before new risk is admitted.

Do not mark the alert RESOLVED until the dependency is verified healthy.
