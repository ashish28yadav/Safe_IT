# Authentication Service Failure Runbook

**Document ID:** ops-authentication-failures
**Service:** authentication-service
**Incident category:** availability
**Document type:** runbook

## Symptoms
Token validation failures or login errors increase across clients.

## Root cause
The authentication process, key/configuration rollout, or identity dependency may be unhealthy.

## Diagnostic steps
1. Capture the alert timestamp, affected service, and correlation ID; compare with the service's recent baseline.
2. Use service metrics and structured logs to distinguish local resource pressure from a dependency or configuration problem.
3. Follow scenario checks: Separate invalid-credential responses from 5xx/timeouts; inspect service health and dependency latency; compare key/configuration version and deployment history; sample correlation IDs.
4. Record observations and owners before proposing a change.

## Resolution procedure
Do not disable authentication checks, lower validation requirements, or expose tokens. Escalate key or identity-provider changes to the security owner.

## Verification steps
Validate synthetic valid and invalid authentication flows, error rates, dependency health, and audit logging.

## Safety warnings
All actions here are human guidance. Confirm scope, authorization, and rollback plan before any state-changing operation. Never use these procedures to access real infrastructure from this simulator, expose credentials, delete data, or bypass security controls.
