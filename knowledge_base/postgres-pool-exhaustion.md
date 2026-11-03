# PostgreSQL Connection Pool Exhaustion

**Document ID:** ops-postgres-pool-exhaustion
**Service:** postgres-database
**Incident category:** database
**Document type:** runbook

## Symptoms
Pool utilization approaches 100%, new connections wait or time out, and dependent services report database errors.

## Root cause
Long-lived transactions, leaked application sessions, or a sudden increase in concurrency can consume the pool.

## Diagnostic steps
1. Capture the alert timestamp, affected service, and correlation ID; compare with the service's recent baseline.
2. Use service metrics and structured logs to distinguish local resource pressure from a dependency or configuration problem.
3. Follow scenario checks: Compare active connections with configured pool and database limits; group sessions by application and state; inspect transaction age and wait events; correlate with recent traffic or deploys.
4. Record observations and owners before proposing a change.

## Resolution procedure
Identify the owning workload before recycling connections. Ask the database owner to review long transactions. Change pool limits only after checking the database connection budget; do not terminate sessions automatically.

## Verification steps
Confirm active connections return below the alert threshold, pool wait time falls, and dependent service errors recover.

## Safety warnings
All actions here are human guidance. Confirm scope, authorization, and rollback plan before any state-changing operation. Never use these procedures to access real infrastructure from this simulator, expose credentials, delete data, or bypass security controls.
