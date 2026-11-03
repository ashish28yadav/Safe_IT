# PostgreSQL Disk Pressure Response

**Document ID:** ops-postgres-disk-pressure
**Service:** postgres-database
**Incident category:** capacity
**Document type:** runbook

## Symptoms
Free disk capacity falls toward the configured threshold or database writes become slow or fail.

## Root cause
WAL retention, oversized tables, temporary files, or backup retention may be consuming storage.

## Diagnostic steps
1. Capture the alert timestamp, affected service, and correlation ID; compare with the service's recent baseline.
2. Use service metrics and structured logs to distinguish local resource pressure from a dependency or configuration problem.
3. Follow scenario checks: Check filesystem free space, database and WAL growth, replication lag, and backup status; compare growth with recent write volume; inspect alert history.
4. Record observations and owners before proposing a change.

## Resolution procedure
Do not remove database files, WAL segments, or backups manually. Escalate to the database owner for approved capacity expansion or retention actions; preserve recovery points.

## Verification steps
Verify free capacity is above the operational threshold, WAL archiving is healthy, and write latency is normal.

## Safety warnings
All actions here are human guidance. Confirm scope, authorization, and rollback plan before any state-changing operation. Never use these procedures to access real infrastructure from this simulator, expose credentials, delete data, or bypass security controls.
