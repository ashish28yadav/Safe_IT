# Synthetic Incident: Database Pool Saturation

**Document ID:** ops-synthetic-db-incident
**Service:** postgres-database
**Incident category:** database
**Document type:** synthetic_incident

## Symptoms
Example symptom: payment and authentication requests timed out while database pool utilization reached its configured maximum.

## Root cause
Synthetic example only: a simulated workload held connections longer than expected, exhausting the application pool.

## Diagnostic steps
1. Capture the alert timestamp, affected service, and correlation ID; compare with the service's recent baseline.
2. Use service metrics and structured logs to distinguish local resource pressure from a dependency or configuration problem.
3. Follow scenario checks: The responder compared active connections, pool waits, transaction age, and service error timestamps to identify the affected workload.
4. Record observations and owners before proposing a change.

## Resolution procedure
The synthetic response was to restore caller health and request database-owner review; no sessions were automatically terminated and no real database was accessed.

## Verification steps
The simulated active connection count returned below the threshold and dependent-service errors cleared.

## Safety warnings
All actions here are human guidance. Confirm scope, authorization, and rollback plan before any state-changing operation. Never use these procedures to access real infrastructure from this simulator, expose credentials, delete data, or bypass security controls.
