# Redis or Cache Dependency Failure

**Document ID:** ops-redis-cache-failure
**Service:** general
**Incident category:** dependency
**Document type:** runbook

## Symptoms
Cache hit rate drops, cache calls time out, or dependent service latency rises.

## Root cause
Cache node unavailability, connection pool exhaustion, expiration churn, or incompatible client configuration may be responsible.

## Diagnostic steps
1. Capture the alert timestamp, affected service, and correlation ID; compare with the service's recent baseline.
2. Use service metrics and structured logs to distinguish local resource pressure from a dependency or configuration problem.
3. Follow scenario checks: Compare hit/miss ratio, connection errors, latency and key-space trends; distinguish cache failures from source-of-truth database failures; inspect client rollout timing.
4. Record observations and owners before proposing a change.

## Resolution procedure
Treat cache as disposable only when application semantics confirm it. Do not flush keys or change eviction policy without explicit owner approval.

## Verification steps
Verify cache connectivity and latency recover, source-of-truth load remains safe, and cache hit ratio stabilizes.

## Safety warnings
All actions here are human guidance. Confirm scope, authorization, and rollback plan before any state-changing operation. Never use these procedures to access real infrastructure from this simulator, expose credentials, delete data, or bypass security controls.
