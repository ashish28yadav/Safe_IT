# PostgreSQL High CPU Triage

**Document ID:** ops-postgres-high-cpu
**Service:** postgres-database
**Incident category:** database
**Document type:** runbook

## Symptoms
Database CPU remains elevated and query latency rises across one or more dependent services.

## Root cause
A query plan regression, increased query volume, lock contention, or maintenance work may be responsible.

## Diagnostic steps
1. Capture the alert timestamp, affected service, and correlation ID; compare with the service's recent baseline.
2. Use service metrics and structured logs to distinguish local resource pressure from a dependency or configuration problem.
3. Follow scenario checks: Review query statistics and top normalized statements; inspect active queries and wait events; compare query volume and latency to the previous baseline; check for deploys or scheduled maintenance.
4. Record observations and owners before proposing a change.

## Resolution procedure
Capture query identifiers and plans for the database owner. Avoid terminating queries or changing indexes without review. Any query cancellation must follow the approved operational process.

## Verification steps
Verify database CPU and query latency trend down and dependent service latency recovers over a sustained observation period.

## Safety warnings
All actions here are human guidance. Confirm scope, authorization, and rollback plan before any state-changing operation. Never use these procedures to access real infrastructure from this simulator, expose credentials, delete data, or bypass security controls.
