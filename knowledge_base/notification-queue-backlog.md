# Notification Queue Backlog Runbook

**Document ID:** ops-notification-queue-backlog
**Service:** notification-service
**Incident category:** queue
**Document type:** runbook

## Symptoms
Queue depth grows faster than delivery throughput and notification delay increases.

## Root cause
Consumer workers may be unhealthy, a dependency may be slow, or rate limits may have reduced throughput.

## Diagnostic steps
1. Capture the alert timestamp, affected service, and correlation ID; compare with the service's recent baseline.
2. Use service metrics and structured logs to distinguish local resource pressure from a dependency or configuration problem.
3. Follow scenario checks: Measure enqueue and consume rates, oldest-message age, retry/dead-letter counts, consumer health, and downstream response codes; compare provider rate limits.
4. Record observations and owners before proposing a change.

## Resolution procedure
Restore consumer health and confirm downstream capacity before any drain. Do not purge messages or bypass rate limits; obtain owner approval for throughput changes.

## Verification steps
Verify queue depth and oldest-message age trend down, delivery success recovers, and duplicate delivery remains within policy.

## Safety warnings
All actions here are human guidance. Confirm scope, authorization, and rollback plan before any state-changing operation. Never use these procedures to access real infrastructure from this simulator, expose credentials, delete data, or bypass security controls.
