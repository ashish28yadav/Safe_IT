# HTTP 5xx Spike Investigation

**Document ID:** ops-http-5xx-spike
**Service:** payment-service
**Incident category:** availability
**Document type:** runbook

## Symptoms
HTTP 5xx rate rises above service alert thresholds or multiple routes fail together.

## Root cause
A dependency failure, application exception, resource saturation, or bad rollout may produce server errors.

## Diagnostic steps
1. Capture the alert timestamp, affected service, and correlation ID; compare with the service's recent baseline.
2. Use service metrics and structured logs to distinguish local resource pressure from a dependency or configuration problem.
3. Follow scenario checks: Break down by route and status code; inspect structured logs and correlation IDs; compare dependency metrics, resource use, and deployment timeline; separate client 4xx from 5xx.
4. Record observations and owners before proposing a change.

## Resolution procedure
Avoid retry storms and broad restarts. Apply only a reviewed rollback or service-specific mitigation after confirming blast radius.

## Verification steps
Verify 5xx rate falls below threshold, latency recovers, and a representative request succeeds for each affected route.

## Safety warnings
All actions here are human guidance. Confirm scope, authorization, and rollback plan before any state-changing operation. Never use these procedures to access real infrastructure from this simulator, expose credentials, delete data, or bypass security controls.
