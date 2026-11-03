# High Memory Utilization Response

**Document ID:** ops-high-memory
**Service:** notification-service
**Incident category:** capacity
**Document type:** runbook

## Symptoms
Memory usage remains above the service threshold, garbage collection or latency increases, or the process approaches its limit.

## Root cause
A workload increase, retained objects, unbounded queue growth, or leak may be responsible.

## Diagnostic steps
1. Capture the alert timestamp, affected service, and correlation ID; compare with the service's recent baseline.
2. Use service metrics and structured logs to distinguish local resource pressure from a dependency or configuration problem.
3. Follow scenario checks: Compare resident memory trend with request and queue volume; inspect heap/GC summaries if available; check deployment changes and worker concurrency.
4. Record observations and owners before proposing a change.

## Resolution procedure
Do not capture or upload memory dumps containing customer data. Do not raise container limits without checking host capacity and owner approval.

## Verification steps
Verify memory plateaus below threshold, queue age and latency improve, and no repeated growth appears during observation.

## Safety warnings
All actions here are human guidance. Confirm scope, authorization, and rollback plan before any state-changing operation. Never use these procedures to access real infrastructure from this simulator, expose credentials, delete data, or bypass security controls.
