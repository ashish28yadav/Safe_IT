# Authentication Validation Latency

**Document ID:** ops-authentication-latency
**Service:** authentication-service
**Incident category:** performance
**Document type:** runbook

## Symptoms
Token validation p95/p99 latency rises and dependent services begin timing out.

## Root cause
Identity-provider slowness, resolver/network delay, or local CPU/memory pressure may contribute.

## Diagnostic steps
1. Capture the alert timestamp, affected service, and correlation ID; compare with the service's recent baseline.
2. Use service metrics and structured logs to distinguish local resource pressure from a dependency or configuration problem.
3. Follow scenario checks: Compare local validation time with upstream identity calls; inspect DNS/connect/response timing, thread or request queues, and service resource metrics.
4. Record observations and owners before proposing a change.

## Resolution procedure
Do not increase timeouts broadly or bypass authentication. Coordinate any timeout or cache changes with security and service owners.

## Verification steps
Confirm p95 and p99 latency recover, downstream timeout rates decline, and authentication controls remain enabled.

## Safety warnings
All actions here are human guidance. Confirm scope, authorization, and rollback plan before any state-changing operation. Never use these procedures to access real infrastructure from this simulator, expose credentials, delete data, or bypass security controls.
