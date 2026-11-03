# Payment Service Outage Runbook

**Document ID:** ops-payment-outage
**Service:** payment-service
**Incident category:** availability
**Document type:** runbook

## Symptoms
Elevated authorization failures, gateway timeout responses, or a sharp drop in successful payment requests.

## Root cause
A provider dependency may be unavailable, the local worker may be unhealthy, or a recent configuration rollout may have changed timeout behavior.

## Diagnostic steps
1. Capture the alert timestamp, affected service, and correlation ID; compare with the service's recent baseline.
2. Use service metrics and structured logs to distinguish local resource pressure from a dependency or configuration problem.
3. Follow scenario checks: Compare 5xx and timeout rates by route and provider; inspect payment-service logs by correlation ID; compare dependency health and latency; check the last deployment and circuit-breaker state.
4. Record observations and owners before proposing a change.

## Resolution procedure
If a recent deployment correlates, follow the rollback runbook with the release owner. If a provider is degraded, use only the documented approved failover procedure. Escalate before changing routing or restarting workers.

## Verification steps
Confirm successful synthetic simulator requests, error rate returns to baseline, and provider latency and circuit-breaker metrics stabilize for at least 10 minutes.

## Safety warnings
All actions here are human guidance. Confirm scope, authorization, and rollback plan before any state-changing operation. Never use these procedures to access real infrastructure from this simulator, expose credentials, delete data, or bypass security controls.
