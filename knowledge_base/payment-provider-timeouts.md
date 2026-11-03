# Payment Provider Timeout Triage

**Document ID:** ops-payment-provider-timeouts
**Service:** payment-service
**Incident category:** dependency
**Document type:** runbook

## Symptoms
Payment requests exceed the configured upstream timeout while local CPU and memory remain near baseline.

## Root cause
Provider latency or a network path issue is more likely than local saturation. Retries can amplify load if they are not bounded.

## Diagnostic steps
1. Capture the alert timestamp, affected service, and correlation ID; compare with the service's recent baseline.
2. Use service metrics and structured logs to distinguish local resource pressure from a dependency or configuration problem.
3. Follow scenario checks: Break down timeouts by provider and endpoint; inspect retry counts and circuit-breaker transitions; compare request latency with upstream latency; check DNS and connection establishment timing.
4. Record observations and owners before proposing a change.

## Resolution procedure
Keep retry budgets bounded. Escalate to the provider owner with timestamps and correlation IDs. Do not increase retries or disable the circuit breaker without an approved change.

## Verification steps
Verify upstream latency and timeout rate fall, retry volume stays bounded, and payment success rate recovers.

## Safety warnings
All actions here are human guidance. Confirm scope, authorization, and rollback plan before any state-changing operation. Never use these procedures to access real infrastructure from this simulator, expose credentials, delete data, or bypass security controls.
