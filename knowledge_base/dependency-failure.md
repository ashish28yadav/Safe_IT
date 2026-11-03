# Service Dependency Failure Isolation

**Document ID:** ops-dependency-failure
**Service:** general
**Incident category:** dependency
**Document type:** runbook

## Symptoms
A service is degraded while one or more downstream dependency checks fail.

## Root cause
The dependency itself, network path, or caller-side configuration may be responsible.

## Diagnostic steps
1. Capture the alert timestamp, affected service, and correlation ID; compare with the service's recent baseline.
2. Use service metrics and structured logs to distinguish local resource pressure from a dependency or configuration problem.
3. Follow scenario checks: Build a timestamped dependency map from service telemetry; compare failures across callers; inspect error codes and latency; identify first failing hop.
4. Record observations and owners before proposing a change.

## Resolution procedure
Do not apply a fix to a dependency based only on a caller symptom. Keep authentication and authorization controls intact; involve the owning team.

## Verification steps
Confirm the dependency and its callers pass readiness checks and error rates return to normal.

## Safety warnings
All actions here are human guidance. Confirm scope, authorization, and rollback plan before any state-changing operation. Never use these procedures to access real infrastructure from this simulator, expose credentials, delete data, or bypass security controls.
