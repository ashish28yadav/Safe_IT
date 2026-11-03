# Slow PostgreSQL Query Investigation

**Document ID:** ops-postgres-slow-query
**Service:** postgres-database
**Incident category:** performance
**Document type:** runbook

## Symptoms
A small set of requests shows high database time while general service health may remain normal.

## Root cause
A query plan change, missing selectivity, lock wait, or increased data volume can increase execution time.

## Diagnostic steps
1. Capture the alert timestamp, affected service, and correlation ID; compare with the service's recent baseline.
2. Use service metrics and structured logs to distinguish local resource pressure from a dependency or configuration problem.
3. Follow scenario checks: Use query fingerprints and normalized statistics; inspect query plan with safe read-only explain where permitted; check lock and I/O waits; compare parameter distributions and release timing.
4. Record observations and owners before proposing a change.

## Resolution procedure
Keep diagnostic queries read-only and bounded. Have the database owner approve plan or schema changes; do not run unreviewed DDL in response to an alert.

## Verification steps
Compare the same query fingerprint after an approved change and verify p95 latency, database CPU, and lock waits return to baseline.

## Safety warnings
All actions here are human guidance. Confirm scope, authorization, and rollback plan before any state-changing operation. Never use these procedures to access real infrastructure from this simulator, expose credentials, delete data, or bypass security controls.
