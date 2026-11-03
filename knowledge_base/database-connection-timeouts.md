# Database Connection Timeout Troubleshooting

**Document ID:** ops-database-connection-timeouts
**Service:** postgres-database
**Incident category:** database
**Document type:** runbook

## Symptoms
Applications fail to establish database sessions within their connection timeout.

## Root cause
Pool saturation, DNS/network delay, server connection limits, or database unavailability may cause connection establishment failures.

## Diagnostic steps
1. Capture the alert timestamp, affected service, and correlation ID; compare with the service's recent baseline.
2. Use service metrics and structured logs to distinguish local resource pressure from a dependency or configuration problem.
3. Follow scenario checks: Separate pool wait from TCP/connect time; inspect active/max connections, database readiness, resolver results, and connection errors; correlate across affected services.
4. Record observations and owners before proposing a change.

## Resolution procedure
Do not expose database ports or credentials for diagnosis. Escalate network or database changes through the service owner; avoid blindly increasing connection limits.

## Verification steps
Verify connection establishment latency and pool wait return to baseline and application health checks pass.

## Safety warnings
All actions here are human guidance. Confirm scope, authorization, and rollback plan before any state-changing operation. Never use these procedures to access real infrastructure from this simulator, expose credentials, delete data, or bypass security controls.
