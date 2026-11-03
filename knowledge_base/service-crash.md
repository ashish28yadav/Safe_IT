# Service Process Crash Response

**Document ID:** ops-service-crash
**Service:** authentication-service
**Incident category:** availability
**Document type:** runbook

## Symptoms
Health checks fail because the service process is stopped or repeatedly exits.

## Root cause
A process crash, startup configuration error, or resource limit may have stopped the process.

## Diagnostic steps
1. Capture the alert timestamp, affected service, and correlation ID; compare with the service's recent baseline.
2. Use service metrics and structured logs to distinguish local resource pressure from a dependency or configuration problem.
3. Follow scenario checks: Check simulated status, exit/restart events, latest errors, resource pressure, and configuration version; distinguish process failure from a dependency outage.
4. Record observations and owners before proposing a change.

## Resolution procedure
Restart only through an authorized, simulator-scoped action. A restart does not clear resource or dependency faults; preserve logs before reset.

## Verification steps
Verify process health, active faults, readiness, and dependent request success; continue observing for repeated crash loops.

## Safety warnings
All actions here are human guidance. Confirm scope, authorization, and rollback plan before any state-changing operation. Never use these procedures to access real infrastructure from this simulator, expose credentials, delete data, or bypass security controls.
